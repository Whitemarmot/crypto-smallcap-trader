"""
Copy Engine - Core copy-trading logic and execution.
"""
import asyncio
import random
import logging
from typing import Optional, List, Dict, Any, Callable
from datetime import datetime
from dataclasses import dataclass
from enum import Enum

from .models import TrackedWallet, DetectedTrade, CopyConfig, CopyResult, TradeType
from .filters import TradeFilter, FilterResult
from .trade_detector import TradeDetector
from .influencer_monitor import InfluencerMonitor

logger = logging.getLogger(__name__)


class CopyDecision(Enum):
    COPY = "copy"
    SKIP = "skip"
    QUEUE = "queue"


@dataclass
class PendingCopy:
    """A trade queued for copying."""
    trade: DetectedTrade
    filter_result: FilterResult
    execute_at: datetime
    size_multiplier: float
    status: str = "pending"


class CopyTrader:
    """
    Main copy-trading engine.
    Manages wallets, processes trades, and executes copies.
    """
    
    def __init__(
        self,
        etherscan_api_key: str,
        private_key: Optional[str] = None,
        config: Optional[CopyConfig] = None,
        chain: str = "ethereum"
    ):
        self.etherscan_api_key = etherscan_api_key
        self.private_key = private_key
        self.config = config or CopyConfig()
        self.chain = chain
        
        # Components
        self.trade_filter = TradeFilter(self.config)
        self.trade_detector = TradeDetector(etherscan_api_key, chain)
        self.influencer_monitor = InfluencerMonitor()
        
        # State
        self._wallets: Dict[str, TrackedWallet] = {}
        self._pending_copies: List[PendingCopy] = []
        self._executed_copies: List[CopyResult] = []
        self._active_copies = 0
        
        # Callbacks
        self._on_copy_callbacks: List[Callable[[CopyResult], None]] = []
        
        # Running state
        self._running = False
        self._executor_task: Optional[asyncio.Task] = None
        
        # Register trade callback
        self.trade_detector.on_trade(self._on_trade_detected)
    
    def add_wallet_to_follow(
        self,
        address: str,
        name: str,
        weight: float = 0.7,
        tags: Optional[List[str]] = None
    ) -> TrackedWallet:
        """
        Add a wallet to follow for copy-trading.
        
        Args:
            address: Wallet address (0x...)
            name: Human-readable name
            weight: Influence weight (0.0-1.0)
            tags: Optional tags for categorization
        
        Returns:
            The created TrackedWallet
        """
        from .models import WalletType
        
        wallet = TrackedWallet(
            address=address,
            name=name,
            wallet_type=WalletType.CUSTOM,
            weight=min(1.0, max(0.0, weight)),
            tags=tags or []
        )
        
        self._wallets[address.lower()] = wallet
        self.trade_detector.add_wallet(wallet)
        
        logger.info(f"Now following: {name} ({address[:10]}...) weight={weight}")
        return wallet
    
    def remove_wallet(self, address: str) -> bool:
        """Remove a wallet from following."""
        address = address.lower()
        if address in self._wallets:
            del self._wallets[address]
            self.trade_detector.remove_wallet(address)
            logger.info(f"Stopped following: {address[:10]}...")
            return True
        return False
    
    def load_influencers(self):
        """Load known influencers to follow."""
        self.influencer_monitor.load_known_influencers()
        for wallet in self.influencer_monitor.get_all_wallets():
            self._wallets[wallet.address] = wallet
            self.trade_detector.add_wallet(wallet)
        
        logger.info(f"Loaded {len(self._wallets)} wallets to follow")
    
    async def _on_trade_detected(self, trade: DetectedTrade):
        """
        Called when a trade is detected from a followed wallet.
        Decides whether to copy and queues if appropriate.
        """
        logger.info(
            f"📊 Trade detected: {trade.wallet_name} "
            f"{trade.trade_type.value} {trade.token_out_symbol} "
            f"${trade.amount_usd:.2f}"
        )
        
        # Apply filters
        filter_result = self.trade_filter.apply_filters(trade)
        
        if not filter_result.should_copy:
            logger.info(f"⏭️ Skipping trade: {filter_result.reason}")
            return
        
        # Check concurrent copy limit
        if self._active_copies >= self.config.max_concurrent_copies:
            logger.warning("Max concurrent copies reached, skipping")
            return
        
        # Queue the copy with delay
        execute_at = datetime.utcnow()
        delay_seconds = filter_result.delay_seconds
        
        # Add random jitter to avoid detection
        jitter = random.uniform(-1.0, 2.0)
        delay_seconds += jitter
        delay_seconds = max(self.config.min_delay_seconds, delay_seconds)
        
        pending = PendingCopy(
            trade=trade,
            filter_result=filter_result,
            execute_at=datetime.utcnow(),
            size_multiplier=filter_result.adjusted_size
        )
        
        self._pending_copies.append(pending)
        self.trade_filter.record_copy(trade)
        
        logger.info(
            f"⏰ Queued copy: {trade.token_out_symbol} "
            f"delay={delay_seconds:.1f}s size={filter_result.adjusted_size:.2%}"
        )
        
        # Schedule execution after delay
        asyncio.create_task(self._delayed_execute(pending, delay_seconds))
    
    async def _delayed_execute(self, pending: PendingCopy, delay: float):
        """Execute a copy after delay."""
        await asyncio.sleep(delay)
        
        if pending.status != "pending":
            return  # Already cancelled or executed
        
        await self.execute_copy(
            pending.trade,
            self.private_key,
            pending.size_multiplier
        )
    
    async def on_trade_detected(self, trade: DetectedTrade) -> CopyDecision:
        """
        Public method to process a detected trade.
        Returns the decision made.
        """
        filter_result = self.trade_filter.apply_filters(trade)
        
        if not filter_result.should_copy:
            return CopyDecision.SKIP
        
        if self._active_copies >= self.config.max_concurrent_copies:
            return CopyDecision.QUEUE
        
        await self._on_trade_detected(trade)
        return CopyDecision.COPY
    
    async def execute_copy(
        self,
        trade: DetectedTrade,
        wallet_private_key: Optional[str],
        size_multiplier: float
    ) -> CopyResult:
        """
        Execute a copy trade.
        
        Args:
            trade: The original trade to copy
            wallet_private_key: Private key for signing (None for dry run)
            size_multiplier: Size relative to original (0.1 = 10%)
        
        Returns:
            CopyResult with execution details
        """
        self._active_copies += 1
        
        try:
            # Calculate trade size
            our_trade_size = trade.amount_usd * size_multiplier
            our_trade_size = min(our_trade_size, self.config.max_trade_size_usd)
            our_trade_size = max(our_trade_size, self.config.min_trade_size_usd)
            
            logger.info(
                f"🔄 Executing copy: {trade.trade_type.value} "
                f"{trade.token_out_symbol} ${our_trade_size:.2f}"
            )
            
            if self.config.dry_run:
                # Simulate the trade
                result = await self._simulate_trade(trade, our_trade_size)
            else:
                # Execute real trade
                result = await self._execute_real_trade(
                    trade, 
                    our_trade_size,
                    wallet_private_key
                )
            
            self._executed_copies.append(result)
            
            # Update wallet stats
            wallet = self._wallets.get(trade.wallet_address)
            if wallet:
                self.influencer_monitor.update_stats(
                    trade.wallet_address,
                    result.success
                )
            
            # Notify callbacks
            for callback in self._on_copy_callbacks:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        await callback(result)
                    else:
                        callback(result)
                except Exception as e:
                    logger.error(f"Callback error: {e}")
            
            return result
        
        finally:
            self._active_copies -= 1
    
    async def _simulate_trade(
        self,
        trade: DetectedTrade,
        size_usd: float
    ) -> CopyResult:
        """Simulate a trade (dry run mode)."""
        # Add realistic delay
        await asyncio.sleep(random.uniform(0.5, 2.0))
        
        # Simulate success with some randomness
        success = random.random() > 0.1  # 90% success rate
        
        if success:
            # Simulate some slippage
            slippage = random.uniform(0.001, 0.02)
            amount_received = size_usd * (1 - slippage)
            
            logger.info(f"✅ [DRY RUN] Trade simulated: ${size_usd:.2f} -> {amount_received:.4f}")
            
            return CopyResult(
                success=True,
                original_trade=trade,
                tx_hash="0x" + "0" * 64,  # Fake hash
                amount_spent=size_usd,
                amount_received=amount_received,
                gas_used=0.005  # Simulated gas
            )
        else:
            logger.warning(f"❌ [DRY RUN] Trade simulation failed")
            
            return CopyResult(
                success=False,
                original_trade=trade,
                error_message="Simulated failure"
            )
    
    async def _execute_real_trade(
        self,
        trade: DetectedTrade,
        size_usd: float,
        private_key: str
    ) -> CopyResult:
        """
        Execute a real trade on-chain.
        Uses DEX aggregator for best execution.
        """
        try:
            # This would integrate with web3.py and DEX router
            # For now, return a placeholder
            
            logger.warning("Real trade execution not implemented - using dry run")
            return await self._simulate_trade(trade, size_usd)
            
            # Real implementation would:
            # 1. Get quote from DEX aggregator (1inch, 0x, etc.)
            # 2. Check slippage is acceptable
            # 3. Build and sign transaction
            # 4. Submit to mempool (possibly with flashbots for MEV protection)
            # 5. Wait for confirmation
            # 6. Return result
        
        except Exception as e:
            logger.error(f"Trade execution error: {e}")
            return CopyResult(
                success=False,
                original_trade=trade,
                error_message=str(e)
            )
    
    def on_copy_executed(self, callback: Callable[[CopyResult], None]):
        """Register callback for when copies are executed."""
        self._on_copy_callbacks.append(callback)
    
    async def start(self):
        """Start the copy-trading engine."""
        if self._running:
            logger.warning("Copy trader already running")
            return
        
        self._running = True
        
        logger.info("🚀 Starting copy trader")
        logger.info(f"   Dry run: {self.config.dry_run}")
        logger.info(f"   Following: {len(self._wallets)} wallets")
        logger.info(f"   Max size: ${self.config.max_trade_size_usd}")
        logger.info(f"   Delay: {self.config.min_delay_seconds}-{self.config.max_delay_seconds}s")
        
        await self.trade_detector.start()
    
    async def stop(self):
        """Stop the copy-trading engine."""
        self._running = False
        
        # Cancel pending copies
        for pending in self._pending_copies:
            pending.status = "cancelled"
        
        await self.trade_detector.stop()
        
        logger.info("Copy trader stopped")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get copy-trading statistics."""
        successful = [r for r in self._executed_copies if r.success]
        failed = [r for r in self._executed_copies if not r.success]
        
        total_spent = sum(r.amount_spent for r in successful)
        total_received = sum(r.amount_received for r in successful)
        
        return {
            "total_copies": len(self._executed_copies),
            "successful": len(successful),
            "failed": len(failed),
            "success_rate": len(successful) / len(self._executed_copies) if self._executed_copies else 0,
            "total_spent_usd": total_spent,
            "total_received": total_received,
            "pending_copies": len([p for p in self._pending_copies if p.status == "pending"]),
            "active_copies": self._active_copies,
            "wallets_followed": len(self._wallets)
        }
    
    def get_recent_copies(self, limit: int = 20) -> List[CopyResult]:
        """Get recent copy results."""
        return self._executed_copies[-limit:]
    
    def update_config(self, **kwargs):
        """Update configuration parameters."""
        for key, value in kwargs.items():
            if hasattr(self.config, key):
                setattr(self.config, key, value)
                logger.info(f"Config updated: {key}={value}")
        
        # Recreate filter with new config
        self.trade_filter = TradeFilter(self.config)
    
    def set_dry_run(self, enabled: bool):
        """Enable or disable dry run mode."""
        self.config.dry_run = enabled
        logger.info(f"Dry run mode: {'enabled' if enabled else 'disabled'}")
    
    def get_followed_wallets(self) -> List[TrackedWallet]:
        """Get list of followed wallets."""
        return list(self._wallets.values())


# Convenience function for quick setup
async def create_copy_trader(
    etherscan_api_key: str,
    private_key: Optional[str] = None,
    dry_run: bool = True,
    load_influencers: bool = True
) -> CopyTrader:
    """
    Create and configure a CopyTrader instance.
    
    Args:
        etherscan_api_key: API key for Etherscan
        private_key: Wallet private key (optional, needed for real trades)
        dry_run: If True, simulate trades without executing
        load_influencers: If True, load known influencer wallets
    
    Returns:
        Configured CopyTrader instance
    """
    config = CopyConfig(
        dry_run=dry_run,
        enabled=True,
        min_delay_seconds=5.0,
        max_delay_seconds=30.0
    )
    
    trader = CopyTrader(
        etherscan_api_key=etherscan_api_key,
        private_key=private_key,
        config=config
    )
    
    if load_influencers:
        trader.load_influencers()
    
    return trader
