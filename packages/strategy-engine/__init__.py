"""
Strategy Engine - Auto-trading strategies for crypto
"""
from .models import (
    Strategy, StrategyConfig, StrategyStatus,
    TradeSignal, SignalType,
    Position, PositionStatus,
    MarketData, ExecutionResult,
    TimeFrame,
)
from .base import BaseStrategy
from .executor import StrategyExecutor, ExecutorConfig
from .strategies import (
    DCAStrategy,
    GridStrategy,
    MomentumStrategy,
    STRATEGY_REGISTRY,
    get_strategy_class,
    create_strategy,
)

__version__ = "0.1.0"

__all__ = [
    # Models
    "Strategy",
    "StrategyConfig",
    "StrategyStatus",
    "TradeSignal",
    "SignalType",
    "Position",
    "PositionStatus",
    "MarketData",
    "ExecutionResult",
    "TimeFrame",
    # Base
    "BaseStrategy",
    # Executor
    "StrategyExecutor",
    "ExecutorConfig",
    # Strategies
    "DCAStrategy",
    "GridStrategy",
    "MomentumStrategy",
    "STRATEGY_REGISTRY",
    "get_strategy_class",
    "create_strategy",
]
