"""
Data models for the copy-trading system.
"""
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from enum import Enum
from datetime import datetime


class TradeType(Enum):
    BUY = "buy"
    SELL = "sell"
    SWAP = "swap"


class WalletType(Enum):
    WHALE = "whale"
    INFLUENCER = "influencer"
    SMART_MONEY = "smart_money"
    CUSTOM = "custom"


@dataclass
class TrackedWallet:
    """A wallet being tracked for copy-trading."""
    address: str
    name: str
    wallet_type: WalletType = WalletType.CUSTOM
    weight: float = 1.0  # Influence on copy decisions (0.0 - 1.0)
    enabled: bool = True
    notes: str = ""
    tags: List[str] = field(default_factory=list)
    added_at: datetime = field(default_factory=datetime.utcnow)
    
    # Stats
    total_trades_detected: int = 0
    profitable_trades: int = 0
    win_rate: float = 0.0
    
    def __post_init__(self):
        self.address = self.address.lower()
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "address": self.address,
            "name": self.name,
            "wallet_type": self.wallet_type.value,
            "weight": self.weight,
            "enabled": self.enabled,
            "notes": self.notes,
            "tags": self.tags,
            "added_at": self.added_at.isoformat(),
            "total_trades_detected": self.total_trades_detected,
            "profitable_trades": self.profitable_trades,
            "win_rate": self.win_rate
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TrackedWallet":
        data["wallet_type"] = WalletType(data.get("wallet_type", "custom"))
        if isinstance(data.get("added_at"), str):
            data["added_at"] = datetime.fromisoformat(data["added_at"])
        return cls(**data)


@dataclass
class DetectedTrade:
    """A trade detected from a tracked wallet."""
    tx_hash: str
    wallet_address: str
    wallet_name: str
    trade_type: TradeType
    token_in: str
    token_out: str
    token_in_symbol: str
    token_out_symbol: str
    amount_in: float
    amount_out: float
    amount_usd: float
    price_impact: float
    dex: str  # uniswap, sushiswap, etc.
    chain: str  # ethereum, bsc, arbitrum, etc.
    block_number: int
    timestamp: datetime
    gas_price_gwei: float
    
    # Metadata
    wallet_weight: float = 1.0
    confidence_score: float = 1.0
    
    def __post_init__(self):
        self.wallet_address = self.wallet_address.lower()
        self.token_in = self.token_in.lower()
        self.token_out = self.token_out.lower()
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "tx_hash": self.tx_hash,
            "wallet_address": self.wallet_address,
            "wallet_name": self.wallet_name,
            "trade_type": self.trade_type.value,
            "token_in": self.token_in,
            "token_out": self.token_out,
            "token_in_symbol": self.token_in_symbol,
            "token_out_symbol": self.token_out_symbol,
            "amount_in": self.amount_in,
            "amount_out": self.amount_out,
            "amount_usd": self.amount_usd,
            "price_impact": self.price_impact,
            "dex": self.dex,
            "chain": self.chain,
            "block_number": self.block_number,
            "timestamp": self.timestamp.isoformat(),
            "gas_price_gwei": self.gas_price_gwei,
            "wallet_weight": self.wallet_weight,
            "confidence_score": self.confidence_score
        }


@dataclass
class CopyConfig:
    """Configuration for copy-trading behavior."""
    # Global settings
    enabled: bool = True
    dry_run: bool = True  # Simulate trades without executing
    max_concurrent_copies: int = 3
    
    # Size settings
    default_size_multiplier: float = 0.1  # Copy 10% of whale's trade size
    max_trade_size_usd: float = 1000.0
    min_trade_size_usd: float = 10.0
    max_portfolio_allocation: float = 0.25  # Max 25% of portfolio per trade
    
    # Timing settings
    min_delay_seconds: float = 5.0  # Random delay range to avoid front-running
    max_delay_seconds: float = 30.0
    max_copy_age_seconds: float = 300.0  # Don't copy trades older than 5 min
    
    # Filter settings
    min_wallet_weight: float = 0.5
    min_confidence_score: float = 0.7
    min_amount_usd: float = 1000.0  # Only copy trades > $1000
    max_price_impact: float = 5.0  # Max 5% price impact
    
    # Token filters
    token_whitelist: List[str] = field(default_factory=list)
    token_blacklist: List[str] = field(default_factory=list)
    
    # Chain settings
    allowed_chains: List[str] = field(default_factory=lambda: ["ethereum", "arbitrum", "base"])
    allowed_dexes: List[str] = field(default_factory=lambda: ["uniswap", "sushiswap", "1inch"])
    
    # Risk settings
    stop_loss_percent: float = 10.0
    take_profit_percent: float = 50.0
    max_slippage: float = 3.0
    
    # Gas settings
    max_gas_price_gwei: float = 100.0
    gas_priority_fee_gwei: float = 2.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "enabled": self.enabled,
            "dry_run": self.dry_run,
            "max_concurrent_copies": self.max_concurrent_copies,
            "default_size_multiplier": self.default_size_multiplier,
            "max_trade_size_usd": self.max_trade_size_usd,
            "min_trade_size_usd": self.min_trade_size_usd,
            "max_portfolio_allocation": self.max_portfolio_allocation,
            "min_delay_seconds": self.min_delay_seconds,
            "max_delay_seconds": self.max_delay_seconds,
            "max_copy_age_seconds": self.max_copy_age_seconds,
            "min_wallet_weight": self.min_wallet_weight,
            "min_confidence_score": self.min_confidence_score,
            "min_amount_usd": self.min_amount_usd,
            "max_price_impact": self.max_price_impact,
            "token_whitelist": self.token_whitelist,
            "token_blacklist": self.token_blacklist,
            "allowed_chains": self.allowed_chains,
            "allowed_dexes": self.allowed_dexes,
            "stop_loss_percent": self.stop_loss_percent,
            "take_profit_percent": self.take_profit_percent,
            "max_slippage": self.max_slippage,
            "max_gas_price_gwei": self.max_gas_price_gwei,
            "gas_priority_fee_gwei": self.gas_priority_fee_gwei
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CopyConfig":
        return cls(**data)


@dataclass
class CopyResult:
    """Result of a copy trade execution."""
    success: bool
    original_trade: DetectedTrade
    tx_hash: Optional[str] = None
    amount_spent: float = 0.0
    amount_received: float = 0.0
    gas_used: float = 0.0
    error_message: Optional[str] = None
    executed_at: datetime = field(default_factory=datetime.utcnow)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "original_trade": self.original_trade.to_dict(),
            "tx_hash": self.tx_hash,
            "amount_spent": self.amount_spent,
            "amount_received": self.amount_received,
            "gas_used": self.gas_used,
            "error_message": self.error_message,
            "executed_at": self.executed_at.isoformat()
        }
