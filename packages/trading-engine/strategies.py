"""
Trading Strategies - DCA, Limit Orders, Stop Loss

Toutes les stratégies utilisent le mode DRY RUN par défaut.
Les vrais trades nécessitent une confirmation explicite.
"""

import asyncio
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from copy import deepcopy
from decimal import Decimal
from enum import Enum
from typing import Optional, Dict, Any, List, Callable
import json


class StrategyType(Enum):
    """Types de stratégies supportées"""
    DCA = "dca"
    LIMIT_ORDER = "limit"
    STOP_LOSS = "stop_loss"
    GRID = "grid"


class StrategyStatus(Enum):
    """État d'une stratégie"""
    ACTIVE = "active"
    PAUSED = "paused"
    STOPPED = "stopped"
    COMPLETED = "completed"
    ERROR = "error"


class OrderSide(Enum):
    """Direction de l'ordre"""
    BUY = "buy"
    SELL = "sell"


@dataclass
class ExecutionResult:
    """Résultat d'une exécution de stratégie"""
    success: bool
    strategy_id: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
    tx_hash: Optional[str] = None
    amount_in: Optional[Decimal] = None
    amount_out: Optional[Decimal] = None
    price: Optional[Decimal] = None
    gas_used: int = 0
    is_dry_run: bool = True
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "strategy_id": self.strategy_id,
            "timestamp": self.timestamp.isoformat(),
            "tx_hash": self.tx_hash,
            "amount_in": str(self.amount_in) if self.amount_in else None,
            "amount_out": str(self.amount_out) if self.amount_out else None,
            "price": str(self.price) if self.price else None,
            "gas_used": self.gas_used,
            "is_dry_run": self.is_dry_run,
            "error": self.error,
            "metadata": self.metadata,
        }


@dataclass(kw_only=True)
class StrategyConfig:
    """Configuration de base d'une stratégie"""
    id: str
    name: str
    strategy_type: StrategyType
    wallet_id: int
    network: str = "ethereum"
    is_active: bool = False
    dry_run: bool = True  # ALWAYS True by default
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_run: Optional[datetime] = None
    
    # Tokens
    token_in: str = "USDC"
    token_out: str = "ETH"
    
    # Slippage
    max_slippage: Decimal = Decimal("1.0")
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "strategy_type": self.strategy_type.value,
            "wallet_id": self.wallet_id,
            "network": self.network,
            "is_active": self.is_active,
            "dry_run": self.dry_run,
            "token_in": self.token_in,
            "token_out": self.token_out,
            "max_slippage": str(self.max_slippage),
        }


@dataclass(kw_only=True)
class DCAConfig(StrategyConfig):
    """
    Dollar Cost Average Configuration
    
    Achète automatiquement un montant fixe à intervalles réguliers.
    """
    strategy_type: StrategyType = field(default=StrategyType.DCA)
    amount_per_buy: Decimal = Decimal("100")  # Montant en token_in (ex: 100 USDC)
    frequency_hours: int = 24  # Intervalle en heures
    total_budget: Optional[Decimal] = None  # Budget total (optionnel)
    max_executions: Optional[int] = None  # Nombre max d'achats
    
    # Tracking
    executions_count: int = 0
    total_spent: Decimal = Decimal("0")
    total_acquired: Decimal = Decimal("0")
    average_price: Decimal = Decimal("0")
    
    def to_dict(self) -> Dict[str, Any]:
        base = super().to_dict()
        base.update({
            "amount_per_buy": str(self.amount_per_buy),
            "frequency_hours": self.frequency_hours,
            "total_budget": str(self.total_budget) if self.total_budget else None,
            "max_executions": self.max_executions,
            "executions_count": self.executions_count,
            "total_spent": str(self.total_spent),
            "total_acquired": str(self.total_acquired),
            "average_price": str(self.average_price),
        })
        return base
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DCAConfig":
        return cls(
            id=data["id"],
            name=data["name"],
            strategy_type=StrategyType.DCA,
            wallet_id=data["wallet_id"],
            network=data.get("network", "ethereum"),
            is_active=data.get("is_active", False),
            dry_run=data.get("dry_run", True),
            token_in=data.get("token_in", "USDC"),
            token_out=data.get("token_out", "ETH"),
            max_slippage=Decimal(data.get("max_slippage", "1.0")),
            amount_per_buy=Decimal(data.get("amount_per_buy", "100")),
            frequency_hours=data.get("frequency_hours", 24),
            total_budget=Decimal(data["total_budget"]) if data.get("total_budget") else None,
            max_executions=data.get("max_executions"),
            executions_count=data.get("executions_count", 0),
            total_spent=Decimal(data.get("total_spent", "0")),
            total_acquired=Decimal(data.get("total_acquired", "0")),
            average_price=Decimal(data.get("average_price", "0")),
        )
    
    def should_execute(self) -> bool:
        """Vérifie si on doit exécuter le DCA"""
        if not self.is_active:
            return False
        
        # Check max executions
        if self.max_executions and self.executions_count >= self.max_executions:
            return False
        
        # Check budget
        if self.total_budget and self.total_spent >= self.total_budget:
            return False
        
        # Check timing
        if self.last_run:
            next_run = self.last_run + timedelta(hours=self.frequency_hours)
            if datetime.utcnow() < next_run:
                return False
        
        return True
    
    def next_execution_time(self) -> Optional[datetime]:
        """Retourne la prochaine exécution prévue"""
        if not self.is_active:
            return None
        if self.last_run:
            return self.last_run + timedelta(hours=self.frequency_hours)
        return datetime.utcnow()


@dataclass(kw_only=True)
class LimitOrderConfig(StrategyConfig):
    """
    Limit Order Configuration
    
    Achète/vend quand le prix atteint une cible.
    """
    strategy_type: StrategyType = field(default=StrategyType.LIMIT_ORDER)
    side: OrderSide = OrderSide.BUY
    target_price: Decimal = Decimal("0")  # Prix cible
    amount: Decimal = Decimal("100")  # Montant à trader
    is_filled: bool = False
    
    # Pour le tracking
    current_price: Optional[Decimal] = None
    distance_percent: Optional[Decimal] = None
    
    def to_dict(self) -> Dict[str, Any]:
        base = super().to_dict()
        base.update({
            "side": self.side.value,
            "target_price": str(self.target_price),
            "amount": str(self.amount),
            "is_filled": self.is_filled,
        })
        return base
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LimitOrderConfig":
        return cls(
            id=data["id"],
            name=data["name"],
            strategy_type=StrategyType.LIMIT_ORDER,
            wallet_id=data["wallet_id"],
            network=data.get("network", "ethereum"),
            is_active=data.get("is_active", False),
            dry_run=data.get("dry_run", True),
            token_in=data.get("token_in", "USDC"),
            token_out=data.get("token_out", "ETH"),
            max_slippage=Decimal(data.get("max_slippage", "1.0")),
            side=OrderSide(data.get("side", "buy")),
            target_price=Decimal(data.get("target_price", "0")),
            amount=Decimal(data.get("amount", "100")),
            is_filled=data.get("is_filled", False),
        )
    
    def should_execute(self, current_price: Decimal) -> bool:
        """Vérifie si le prix cible est atteint"""
        if not self.is_active or self.is_filled:
            return False
        
        if self.target_price <= 0:
            return False
        
        self.current_price = current_price
        
        if self.side == OrderSide.BUY:
            # Buy when price drops below target
            return current_price <= self.target_price
        else:
            # Sell when price rises above target
            return current_price >= self.target_price


@dataclass(kw_only=True)
class StopLossConfig(StrategyConfig):
    """
    Stop Loss Configuration
    
    Vend automatiquement quand le prix baisse d'un certain pourcentage.
    """
    strategy_type: StrategyType = field(default=StrategyType.STOP_LOSS)
    trigger_percent: Decimal = Decimal("10")  # Baisse de 10%
    reference_price: Optional[Decimal] = None  # Prix de référence
    trailing: bool = False  # Si True, ajuste le stop loss à la hausse
    amount: Decimal = Decimal("100")  # Montant à vendre
    is_triggered: bool = False
    
    # Tracking
    highest_price: Optional[Decimal] = None  # Pour trailing stop
    current_stop_price: Optional[Decimal] = None
    
    def to_dict(self) -> Dict[str, Any]:
        base = super().to_dict()
        base.update({
            "trigger_percent": str(self.trigger_percent),
            "reference_price": str(self.reference_price) if self.reference_price else None,
            "trailing": self.trailing,
            "amount": str(self.amount),
            "is_triggered": self.is_triggered,
            "highest_price": str(self.highest_price) if self.highest_price else None,
        })
        return base
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StopLossConfig":
        return cls(
            id=data["id"],
            name=data["name"],
            strategy_type=StrategyType.STOP_LOSS,
            wallet_id=data["wallet_id"],
            network=data.get("network", "ethereum"),
            is_active=data.get("is_active", False),
            dry_run=data.get("dry_run", True),
            token_in=data.get("token_in", "ETH"),  # On vend de l'ETH
            token_out=data.get("token_out", "USDC"),  # Pour du USDC
            max_slippage=Decimal(data.get("max_slippage", "1.0")),
            trigger_percent=Decimal(data.get("trigger_percent", "10")),
            reference_price=Decimal(data["reference_price"]) if data.get("reference_price") else None,
            trailing=data.get("trailing", False),
            amount=Decimal(data.get("amount", "100")),
            is_triggered=data.get("is_triggered", False),
            highest_price=Decimal(data["highest_price"]) if data.get("highest_price") else None,
        )
    
    def should_execute(self, current_price: Decimal) -> bool:
        """Vérifie si le stop loss est déclenché"""
        if not self.is_active or self.is_triggered:
            return False
        
        if not self.reference_price:
            return False
        
        # Update trailing stop
        if self.trailing:
            if self.highest_price is None or current_price > self.highest_price:
                self.highest_price = current_price
            ref = self.highest_price
        else:
            ref = self.reference_price
        
        # Calculate stop price
        drop = ref * (self.trigger_percent / 100)
        stop_price = ref - drop
        self.current_stop_price = stop_price
        
        return current_price <= stop_price


class BaseStrategy(ABC):
    """Classe de base pour les stratégies de trading"""
    
    def __init__(self, config: StrategyConfig, db_callback: Optional[Callable] = None):
        """
        Initialize strategy
        
        Args:
            config: Strategy configuration
            db_callback: Optional callback to save execution results to DB
        """
        self.config = config
        self.db_callback = db_callback
        self._running = False
    
    @abstractmethod
    async def check_and_execute(self) -> Optional[ExecutionResult]:
        """Check conditions and execute if met"""
        pass
    
    def start(self):
        """Start the strategy"""
        self.config.is_active = True
        self._running = True
    
    def stop(self):
        """Stop the strategy"""
        self.config.is_active = False
        self._running = False
    
    def pause(self):
        """Pause the strategy"""
        self.config.is_active = False
    
    def resume(self):
        """Resume the strategy"""
        self.config.is_active = True
    
    async def _log_execution(self, result: ExecutionResult):
        """Log execution to DB via callback"""
        if self.db_callback:
            try:
                await self.db_callback(result)
            except Exception as e:
                print(f"Failed to log execution: {e}")


class DCAStrategy(BaseStrategy):
    """
    Dollar Cost Average Strategy
    
    Achète automatiquement un montant fixe à intervalles réguliers.
    
    Example:
        config = DCAConfig(
            id="dca-eth-1",
            name="DCA ETH Daily",
            wallet_id=1,
            network="base",
            token_in="USDC",
            token_out="ETH",
            amount_per_buy=Decimal("50"),
            frequency_hours=24,
        )
        strategy = DCAStrategy(config)
        strategy.start()
        result = await strategy.check_and_execute()
    """
    
    def __init__(self, config: DCAConfig, dex=None, db_callback=None):
        super().__init__(config, db_callback)
        self.config: DCAConfig = config
        self.dex = dex
    
    async def check_and_execute(self) -> Optional[ExecutionResult]:
        """Check if DCA should execute and do it"""
        if not self.config.should_execute():
            return None
        
        from .dex_aggregator import DexAggregator, Network
        
        try:
            # Get or create DEX client
            if self.dex:
                dex = self.dex
                close_after = False
            else:
                dex = DexAggregator(dry_run=self.config.dry_run)
                await dex._init_client()
                close_after = True
            
            try:
                network = Network.from_name(self.config.network)
                
                # Get quote
                quote = await dex.get_quote(
                    self.config.token_in,
                    self.config.token_out,
                    self.config.amount_per_buy,
                    network,
                )
                
                # Execute swap
                result = await dex.execute_swap(
                    wallet_address="",  # Will be filled by wallet manager
                    private_key="",
                    token_in=self.config.token_in,
                    token_out=self.config.token_out,
                    amount=self.config.amount_per_buy,
                    slippage=self.config.max_slippage,
                    network=network,
                )
                
                # Update config stats
                if result.success:
                    self.config.executions_count += 1
                    self.config.total_spent += self.config.amount_per_buy
                    acquired = quote.dst_amount_human
                    self.config.total_acquired += acquired
                    if self.config.total_acquired > 0:
                        self.config.average_price = self.config.total_spent / self.config.total_acquired
                
                self.config.last_run = datetime.utcnow()
                
                exec_result = ExecutionResult(
                    success=result.success,
                    strategy_id=self.config.id,
                    tx_hash=result.tx_hash,
                    amount_in=self.config.amount_per_buy,
                    amount_out=quote.dst_amount_human,
                    price=quote.price,
                    is_dry_run=result.is_dry_run,
                    error=result.error,
                    metadata={
                        "type": "dca",
                        "execution_count": self.config.executions_count,
                        "total_spent": str(self.config.total_spent),
                        "total_acquired": str(self.config.total_acquired),
                        "average_price": str(self.config.average_price),
                    }
                )
                
                await self._log_execution(exec_result)
                return exec_result
                
            finally:
                if close_after:
                    await dex.close()
                    
        except Exception as e:
            error_result = ExecutionResult(
                success=False,
                strategy_id=self.config.id,
                is_dry_run=self.config.dry_run,
                error=str(e),
            )
            await self._log_execution(error_result)
            return error_result


class LimitOrderStrategy(BaseStrategy):
    """
    Limit Order Strategy
    
    Execute when price reaches target.
    
    Example:
        config = LimitOrderConfig(
            id="limit-1",
            name="Buy ETH at $3000",
            wallet_id=1,
            network="ethereum",
            side=OrderSide.BUY,
            token_in="USDC",
            token_out="ETH",
            target_price=Decimal("3000"),
            amount=Decimal("500"),
        )
        strategy = LimitOrderStrategy(config)
    """
    
    def __init__(self, config: LimitOrderConfig, dex=None, db_callback=None):
        super().__init__(config, db_callback)
        self.config: LimitOrderConfig = config
        self.dex = dex
    
    async def get_current_price(self) -> Decimal:
        """Get current price for the pair"""
        from .dex_aggregator import DexAggregator, Network
        
        async with DexAggregator() as dex:
            network = Network.from_name(self.config.network)
            quote = await dex.get_quote(
                self.config.token_in,
                self.config.token_out,
                Decimal("1"),  # 1 unit for price
                network,
            )
            return quote.price
    
    async def check_and_execute(self) -> Optional[ExecutionResult]:
        """Check price and execute if target reached"""
        try:
            current_price = await self.get_current_price()
            
            if not self.config.should_execute(current_price):
                # Update distance for UI
                if self.config.target_price > 0:
                    diff = abs(current_price - self.config.target_price)
                    self.config.distance_percent = (diff / self.config.target_price) * 100
                return None
            
            from .dex_aggregator import DexAggregator, Network
            
            async with DexAggregator(dry_run=self.config.dry_run) as dex:
                network = Network.from_name(self.config.network)
                
                # Execute the order
                result = await dex.execute_swap(
                    wallet_address="",
                    private_key="",
                    token_in=self.config.token_in,
                    token_out=self.config.token_out,
                    amount=self.config.amount,
                    slippage=self.config.max_slippage,
                    network=network,
                )
                
                if result.success:
                    self.config.is_filled = True
                    self.config.is_active = False
                
                self.config.last_run = datetime.utcnow()
                
                exec_result = ExecutionResult(
                    success=result.success,
                    strategy_id=self.config.id,
                    tx_hash=result.tx_hash,
                    amount_in=self.config.amount,
                    amount_out=result.dst_amount / (10 ** 18) if result.dst_amount else None,
                    price=current_price,
                    is_dry_run=result.is_dry_run,
                    error=result.error,
                    metadata={
                        "type": "limit_order",
                        "side": self.config.side.value,
                        "target_price": str(self.config.target_price),
                        "trigger_price": str(current_price),
                    }
                )
                
                await self._log_execution(exec_result)
                return exec_result
                
        except Exception as e:
            return ExecutionResult(
                success=False,
                strategy_id=self.config.id,
                is_dry_run=self.config.dry_run,
                error=str(e),
            )


class StopLossStrategy(BaseStrategy):
    """
    Stop Loss Strategy
    
    Automatically sell when price drops by X%.
    
    Example:
        config = StopLossConfig(
            id="sl-1",
            name="Stop Loss ETH 10%",
            wallet_id=1,
            network="ethereum",
            token_in="ETH",  # Token to sell
            token_out="USDC",  # Token to receive
            reference_price=Decimal("3500"),
            trigger_percent=Decimal("10"),  # Sell if drops 10%
            amount=Decimal("0.5"),  # Amount of ETH to sell
            trailing=True,  # Optional: trailing stop
        )
    """
    
    def __init__(self, config: StopLossConfig, dex=None, db_callback=None):
        super().__init__(config, db_callback)
        self.config: StopLossConfig = config
        self.dex = dex
    
    async def get_current_price(self) -> Decimal:
        """Get current price for the pair"""
        from .dex_aggregator import DexAggregator, Network
        
        async with DexAggregator() as dex:
            network = Network.from_name(self.config.network)
            # Get price of token_in in terms of token_out
            quote = await dex.get_quote(
                self.config.token_in,
                self.config.token_out,
                Decimal("1"),
                network,
            )
            return quote.price
    
    async def check_and_execute(self) -> Optional[ExecutionResult]:
        """Check price and execute stop loss if triggered"""
        try:
            current_price = await self.get_current_price()
            
            if not self.config.should_execute(current_price):
                return None
            
            from .dex_aggregator import DexAggregator, Network
            
            async with DexAggregator(dry_run=self.config.dry_run) as dex:
                network = Network.from_name(self.config.network)
                
                # Execute the sell
                result = await dex.execute_swap(
                    wallet_address="",
                    private_key="",
                    token_in=self.config.token_in,
                    token_out=self.config.token_out,
                    amount=self.config.amount,
                    slippage=self.config.max_slippage,
                    network=network,
                )
                
                if result.success:
                    self.config.is_triggered = True
                    self.config.is_active = False
                
                self.config.last_run = datetime.utcnow()
                
                exec_result = ExecutionResult(
                    success=result.success,
                    strategy_id=self.config.id,
                    tx_hash=result.tx_hash,
                    amount_in=self.config.amount,
                    price=current_price,
                    is_dry_run=result.is_dry_run,
                    error=result.error,
                    metadata={
                        "type": "stop_loss",
                        "trigger_percent": str(self.config.trigger_percent),
                        "reference_price": str(self.config.reference_price),
                        "stop_price": str(self.config.current_stop_price),
                        "trigger_price": str(current_price),
                        "trailing": self.config.trailing,
                    }
                )
                
                await self._log_execution(exec_result)
                return exec_result
                
        except Exception as e:
            return ExecutionResult(
                success=False,
                strategy_id=self.config.id,
                is_dry_run=self.config.dry_run,
                error=str(e),
            )


class StrategyRunner:
    """
    Gestionnaire de stratégies
    
    Exécute les stratégies actives à intervalles réguliers.
    
    Example:
        runner = StrategyRunner()
        runner.add_strategy(dca_strategy)
        runner.add_strategy(stop_loss_strategy)
        await runner.run_once()  # Single check
        # or
        await runner.run_loop(interval_seconds=60)  # Continuous loop
    """
    
    def __init__(self, db=None):
        self.strategies: Dict[str, BaseStrategy] = {}
        self.db = db
        self._running = False
    
    def add_strategy(self, strategy: BaseStrategy):
        """Add a strategy to the runner"""
        self.strategies[strategy.config.id] = strategy
    
    def remove_strategy(self, strategy_id: str):
        """Remove a strategy"""
        if strategy_id in self.strategies:
            self.strategies[strategy_id].stop()
            del self.strategies[strategy_id]
    
    def get_strategy(self, strategy_id: str) -> Optional[BaseStrategy]:
        """Get a strategy by ID"""
        return self.strategies.get(strategy_id)
    
    async def run_once(self) -> List[ExecutionResult]:
        """Run all strategies once and return results"""
        results = []
        
        for strategy in self.strategies.values():
            if strategy.config.is_active:
                try:
                    result = await strategy.check_and_execute()
                    if result:
                        results.append(result)
                except Exception as e:
                    results.append(ExecutionResult(
                        success=False,
                        strategy_id=strategy.config.id,
                        error=str(e),
                    ))
        
        return results
    
    async def run_loop(self, interval_seconds: int = 60):
        """Run strategies in a continuous loop"""
        self._running = True
        
        while self._running:
            try:
                results = await self.run_once()
                for result in results:
                    print(f"[{result.timestamp}] Strategy {result.strategy_id}: "
                          f"{'✅' if result.success else '❌'} "
                          f"{'(dry run)' if result.is_dry_run else ''}")
            except Exception as e:
                print(f"Error in strategy loop: {e}")
            
            await asyncio.sleep(interval_seconds)
    
    def stop(self):
        """Stop the runner loop"""
        self._running = False
        for strategy in self.strategies.values():
            strategy.stop()


# Factory function
def create_strategy(
    strategy_type: str,
    config_dict: Dict[str, Any],
    dex=None,
    db_callback=None,
) -> BaseStrategy:
    """
    Create a strategy from config dict
    
    Args:
        strategy_type: Type of strategy (dca, limit, stop_loss)
        config_dict: Configuration dictionary
        dex: Optional DEX client
        db_callback: Optional callback for logging
    
    Returns:
        Strategy instance
    """
    if strategy_type.lower() == "dca":
        config = DCAConfig.from_dict(config_dict)
        return DCAStrategy(config, dex, db_callback)
    elif strategy_type.lower() in ("limit", "limit_order"):
        config = LimitOrderConfig.from_dict(config_dict)
        return LimitOrderStrategy(config, dex, db_callback)
    elif strategy_type.lower() in ("stop_loss", "stoploss", "sl"):
        config = StopLossConfig.from_dict(config_dict)
        return StopLossStrategy(config, dex, db_callback)
    else:
        raise ValueError(f"Unknown strategy type: {strategy_type}")


# Convenience exports
__all__ = [
    "StrategyType",
    "StrategyStatus",
    "OrderSide",
    "ExecutionResult",
    "StrategyConfig",
    "DCAConfig",
    "LimitOrderConfig",
    "StopLossConfig",
    "BaseStrategy",
    "DCAStrategy",
    "LimitOrderStrategy",
    "StopLossStrategy",
    "StrategyRunner",
    "create_strategy",
]
