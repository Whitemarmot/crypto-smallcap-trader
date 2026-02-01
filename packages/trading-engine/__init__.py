"""
Crypto SmallCap Trader - Trading Engine
========================================

Multi-chain DEX trading with strategies (DCA, Limit, Stop Loss).

⚠️ IMPORTANT: All trades are in DRY RUN mode by default.
              Real execution requires explicit confirmation.

Quick Start:
------------

    from trading_engine import get_quote, execute_swap, Network
    
    # Get a quote
    quote = await get_quote("ETH", "USDC", Decimal("0.1"), "base")
    print(f"Price: {quote.price}")
    
    # Create a DCA strategy
    from trading_engine import DCAStrategy, DCAConfig
    
    config = DCAConfig(
        id="my-dca",
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

Supported Networks:
-------------------
- Ethereum (1)
- Base (8453)
- Arbitrum (42161)
- BSC (56)
- Polygon (137)
- Optimism (10)
"""

# Version
__version__ = "0.1.0"

# DEX Aggregator
from .dex_aggregator import (
    DexAggregator,
    Network,
    TokenInfo,
    Quote,
    SwapResult,
    COMMON_TOKENS,
    DEFAULT_RPC_URLS,
    get_quote,
    execute_swap,
)

# Strategies
from .strategies import (
    StrategyType,
    StrategyStatus,
    OrderSide,
    ExecutionResult,
    StrategyConfig,
    DCAConfig,
    LimitOrderConfig,
    StopLossConfig,
    BaseStrategy,
    DCAStrategy,
    LimitOrderStrategy,
    StopLossStrategy,
    StrategyRunner,
    create_strategy,
)

# Models (from existing)
from .models import (
    Token,
    SwapQuote,
    SwapTransaction,
    TradeOrder,
    TradeResult,
    TradeStatus,
    TradeDirection,
    TradingConfig,
    ChainId,
    GasSettings,
)

# Trader (from existing)
from .trader import Trader

__all__ = [
    # Version
    "__version__",
    
    # DEX Aggregator
    "DexAggregator",
    "Network",
    "TokenInfo",
    "Quote",
    "SwapResult",
    "COMMON_TOKENS",
    "DEFAULT_RPC_URLS",
    "get_quote",
    "execute_swap",
    
    # Strategies
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
    
    # Models
    "Token",
    "SwapQuote",
    "SwapTransaction",
    "TradeOrder",
    "TradeResult",
    "TradeStatus",
    "TradeDirection",
    "TradingConfig",
    "ChainId",
    "GasSettings",
    
    # Trader
    "Trader",
]
