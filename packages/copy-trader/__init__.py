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
    
    # Whale Tracking
    "WhaleTracker",
    "EtherscanClient",
    "DexScreenerClient",
    "KNOWN_WHALES",
    
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
