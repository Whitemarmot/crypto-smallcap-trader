"""
Trade Detector - Real-time detection of trades from tracked wallets.
Uses WebSocket connections and polling for comprehensive coverage.
"""
import asyncio
import aiohttp
import logging
from typing import Optional, List, Dict, Any, Callable, Set
from datetime import datetime
from collections import deque

from .models import TrackedWallet, DetectedTrade, TradeType
from .whale_tracker import WhaleTracker, EtherscanClient, DexScreenerClient

logger = logging.getLogger(__name__)


class TradeDetector:
    """
    Real-time trade detection system.
    Monitors tracked wallets for swap transactions.
    """
    
    def __init__(
        self,
        etherscan_api_key: str,
        chain: str = "ethereum",
        polling_interval: float = 12.0,  # ~1 block time
        ws_endpoint: Optional[str] = None  # For WebSocket monitoring
    ):
        self.etherscan_api_key = etherscan_api_key
        self.chain = chain
        self.polling_interval = polling_interval
        self.ws_endpoint = ws_endpoint
        
        self.whale_tracker = WhaleTracker(etherscan_api_key, chain)
        self.dexscreener = DexScreenerClient()
        
        # Tracked wallets
        self._wallets: Dict[str, TrackedWallet] = {}
        
        # Trade callbacks
        self._callbacks: List[Callable[[DetectedTrade], None]] = []
        
        # Recent trades cache (for deduplication)
        self._recent_trades: deque = deque(maxlen=1000)
        self._seen_tx_hashes: Set[str] = set()
        
        # Running state
        self._running = False
        self._tasks: List[asyncio.Task] = []
    
    def add_wallet(self, wallet: TrackedWallet):
        """Add a wallet to monitor."""
        self._wallets[wallet.address.lower()] = wallet
        self.whale_tracker.add_wallet(wallet)
        logger.info(f"Monitoring wallet: {wallet.name}")
    
    def remove_wallet(self, address: str):
        """Remove a wallet from monitoring."""
        address = address.lower()
        if address in self._wallets:
            del self._wallets[address]
            self.whale_tracker.remove_wallet(address)
    
    def add_wallets(self, wallets: List[TrackedWallet]):
        """Add multiple wallets."""
        for wallet in wallets:
            self.add_wallet(wallet)
    
    def on_trade(self, callback: Callable[[DetectedTrade], None]):
        """Register a callback for when trades are detected."""
        self._callbacks.append(callback)
    
    async def _notify_callbacks(self, trade: DetectedTrade):
        """Notify all registered callbacks of a new trade."""
        for callback in self._callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(trade)
                else:
                    callback(trade)
            except Exception as e:
                logger.error(f"Error in trade callback: {e}")
    
    def _is_duplicate(self, tx_hash: str) -> bool:
        """Check if we've already processed this transaction."""
        if tx_hash in self._seen_tx_hashes:
            return True
        self._seen_tx_hashes.add(tx_hash)
        
        # Cleanup old hashes (keep last 1000)
        if len(self._seen_tx_hashes) > 1000:
            self._seen_tx_hashes = set(list(self._seen_tx_hashes)[-500:])
        
        return False
    
    async def _poll_wallets(self):
        """Poll wallets for new trades."""
        logger.info("Starting wallet polling...")
        
        while self._running:
            try:
                trades = await self.whale_tracker.scan_all_wallets()
                
                for trade in trades:
                    if self._is_duplicate(trade.tx_hash):
                        continue
                    
                    logger.info(
                        f"🔔 Trade detected: {trade.wallet_name} "
                        f"{trade.trade_type.value} {trade.token_out_symbol} "
                        f"(${trade.amount_usd:.2f})"
                    )
                    
                    self._recent_trades.append(trade)
                    await self._notify_callbacks(trade)
                
            except Exception as e:
                logger.error(f"Error polling wallets: {e}")
            
            await asyncio.sleep(self.polling_interval)
    
    async def _ws_monitor(self):
        """
        Monitor pending transactions via WebSocket.
        Provides faster detection than polling.
        """
        if not self.ws_endpoint:
            logger.warning("No WebSocket endpoint configured")
            return
        
        logger.info("Starting WebSocket monitor...")
        
        while self._running:
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.ws_connect(self.ws_endpoint) as ws:
                        # Subscribe to pending transactions
                        subscribe_msg = {
                            "jsonrpc": "2.0",
                            "id": 1,
                            "method": "eth_subscribe",
                            "params": ["newPendingTransactions"]
                        }
                        await ws.send_json(subscribe_msg)
                        
                        async for msg in ws:
                            if msg.type == aiohttp.WSMsgType.TEXT:
                                await self._handle_ws_message(msg.data)
                            elif msg.type == aiohttp.WSMsgType.ERROR:
                                logger.error(f"WebSocket error: {ws.exception()}")
                                break
            
            except Exception as e:
                logger.error(f"WebSocket connection error: {e}")
                await asyncio.sleep(5)  # Reconnect delay
    
    async def _handle_ws_message(self, data: str):
        """Handle incoming WebSocket message."""
        import json
        
        try:
            msg = json.loads(data)
            
            if "params" in msg and "result" in msg["params"]:
                tx_hash = msg["params"]["result"]
                
                # Get transaction details
                tx = await self._get_pending_tx(tx_hash)
                if tx:
                    await self._check_pending_tx(tx)
        
        except Exception as e:
            logger.debug(f"Error handling WS message: {e}")
    
    async def _get_pending_tx(self, tx_hash: str) -> Optional[Dict[str, Any]]:
        """Get pending transaction details from node."""
        # This would use eth_getTransactionByHash
        # Implementation depends on your node provider
        return None
    
    async def _check_pending_tx(self, tx: Dict[str, Any]):
        """Check if pending transaction is from a tracked wallet."""
        from_addr = tx.get("from", "").lower()
        
        if from_addr not in self._wallets:
            return
        
        wallet = self._wallets[from_addr]
        logger.debug(f"Pending tx from tracked wallet: {wallet.name}")
        
        # Analyze the transaction (similar to whale_tracker)
        # This gives us early detection before confirmation
    
    async def start(self):
        """Start the trade detector."""
        if self._running:
            logger.warning("Trade detector already running")
            return
        
        self._running = True
        logger.info(f"Starting trade detector with {len(self._wallets)} wallets")
        
        # Start polling task
        poll_task = asyncio.create_task(self._poll_wallets())
        self._tasks.append(poll_task)
        
        # Start WebSocket monitor if configured
        if self.ws_endpoint:
            ws_task = asyncio.create_task(self._ws_monitor())
            self._tasks.append(ws_task)
    
    async def stop(self):
        """Stop the trade detector."""
        self._running = False
        
        for task in self._tasks:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        
        self._tasks.clear()
        await self.whale_tracker.close()
        await self.dexscreener.close()
        
        logger.info("Trade detector stopped")
    
    def get_recent_trades(self, limit: int = 50) -> List[DetectedTrade]:
        """Get recent detected trades."""
        trades = list(self._recent_trades)
        trades.sort(key=lambda t: t.timestamp, reverse=True)
        return trades[:limit]
    
    def get_trades_by_wallet(self, address: str) -> List[DetectedTrade]:
        """Get trades for a specific wallet."""
        address = address.lower()
        return [t for t in self._recent_trades if t.wallet_address == address]
    
    def get_trades_by_token(self, token_address: str) -> List[DetectedTrade]:
        """Get trades involving a specific token."""
        token_address = token_address.lower()
        return [
            t for t in self._recent_trades 
            if t.token_in.lower() == token_address or t.token_out.lower() == token_address
        ]


class MemPoolMonitor:
    """
    Monitor the mempool for pending transactions from tracked wallets.
    Provides the fastest possible detection but requires node access.
    """
    
    def __init__(self, ws_endpoint: str, tracked_addresses: List[str]):
        self.ws_endpoint = ws_endpoint
        self.tracked_addresses = set(addr.lower() for addr in tracked_addresses)
        self._callbacks: List[Callable] = []
        self._running = False
    
    def on_pending_tx(self, callback: Callable):
        """Register callback for pending transactions."""
        self._callbacks.append(callback)
    
    async def start(self):
        """Start mempool monitoring."""
        self._running = True
        
        while self._running:
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.ws_connect(self.ws_endpoint) as ws:
                        # Subscribe to pending transactions
                        await ws.send_json({
                            "jsonrpc": "2.0",
                            "id": 1,
                            "method": "eth_subscribe",
                            "params": ["newPendingTransactions"]
                        })
                        
                        logger.info("Connected to mempool")
                        
                        async for msg in ws:
                            if not self._running:
                                break
                            
                            if msg.type == aiohttp.WSMsgType.TEXT:
                                await self._process_message(msg.data, session)
            
            except Exception as e:
                logger.error(f"Mempool monitor error: {e}")
                if self._running:
                    await asyncio.sleep(5)
    
    async def _process_message(self, data: str, session: aiohttp.ClientSession):
        """Process incoming mempool message."""
        import json
        
        try:
            msg = json.loads(data)
            
            if "params" not in msg or "result" not in msg["params"]:
                return
            
            tx_hash = msg["params"]["result"]
            
            # Get transaction details
            async with session.post(
                self.ws_endpoint.replace("wss://", "https://").replace("ws://", "http://"),
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "eth_getTransactionByHash",
                    "params": [tx_hash]
                }
            ) as resp:
                result = await resp.json()
                tx = result.get("result")
                
                if not tx:
                    return
                
                from_addr = tx.get("from", "").lower()
                
                if from_addr in self.tracked_addresses:
                    logger.info(f"⚡ Pending TX from tracked wallet: {tx_hash}")
                    
                    for callback in self._callbacks:
                        try:
                            if asyncio.iscoroutinefunction(callback):
                                await callback(tx)
                            else:
                                callback(tx)
                        except Exception as e:
                            logger.error(f"Callback error: {e}")
        
        except Exception as e:
            logger.debug(f"Error processing mempool message: {e}")
    
    async def stop(self):
        """Stop mempool monitoring."""
        self._running = False
