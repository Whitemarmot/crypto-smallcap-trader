"""
Copy-Trading System for Following Whales and Influencers.

This package provides tools for:
- Tracking whale wallets on-chain
- Monitoring known influencer wallets
- Detecting trades in real-time
- Copy-trading with configurable filters and delays
"""

from .models import (
    TrackedWallet,
    DetectedTrade,
    CopyConfig,
    CopyResult,
    TradeType,
    WalletType
)

from .whale_tracker import (
    WhaleTracker,
    EtherscanClient,
    DexScreenerClient,
    KNOWN_WHALES
)

from .whale_api import (
    # Main API functions
    get_whale_transactions,
    analyze_whale_portfolio,
    get_known_whales,
    check_for_alerts,
    # Sync wrappers for Streamlit
    get_whale_transactions_sync,
    analyze_whale_portfolio_sync,
    check_for_alerts_sync,
    # Data classes
    WhaleTransaction,
    WhalePortfolio,
    WhaleAlert,
    TokenHolding,
    # Whale databases
    KNOWN_WHALES_ETHEREUM,
    KNOWN_WHALES_BASE,
)

from .influencer_monitor import (
    InfluencerMonitor,
    KNOWN_INFLUENCERS,
    SMART_MONEY_WALLETS
)

from .trade_detector import (
    TradeDetector,
    MemPoolMonitor
)

from .filters import (
    TradeFilter,
    FilterResult,
    AdvancedFilters
)

from .copy_engine import (
    CopyTrader,
    CopyDecision,
    PendingCopy,
    create_copy_trader
)

__version__ = "0.1.0"

__all__ = [
    # Models
    "TrackedWallet",
    "DetectedTrade",
    "CopyConfig",
    "CopyResult",
    "TradeType",
    "WalletType",
    
    # Whale Tracking (legacy)
    "WhaleTracker",
    "EtherscanClient",
    "DexScreenerClient",
    "KNOWN_WHALES",
    
    # Whale API (new, recommended)
    "get_whale_transactions",
    "analyze_whale_portfolio",
    "get_known_whales",
    "check_for_alerts",
    "get_whale_transactions_sync",
    "analyze_whale_portfolio_sync",
    "check_for_alerts_sync",
    "WhaleTransaction",
    "WhalePortfolio",
    "WhaleAlert",
    "TokenHolding",
    "KNOWN_WHALES_ETHEREUM",
    "KNOWN_WHALES_BASE",
    
    # Influencer Monitoring
    "InfluencerMonitor",
    "KNOWN_INFLUENCERS",
    "SMART_MONEY_WALLETS",
    
    # Trade Detection
    "TradeDetector",
    "MemPoolMonitor",
    
    # Filters
    "TradeFilter",
    "FilterResult",
    "AdvancedFilters",
    
    # Copy Engine
    "CopyTrader",
    "CopyDecision",
    "PendingCopy",
    "create_copy_trader",
]
