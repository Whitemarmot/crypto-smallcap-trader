"""
Trading Engine Models - Dataclasses pour trades EVM
"""
from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from typing import Optional
from datetime import datetime


class TradeStatus(Enum):
    """Statut d'un trade"""
    PENDING = "pending"
    QUOTED = "quoted"
    SUBMITTED = "submitted"
    CONFIRMED = "confirmed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TradeDirection(Enum):
    """Direction du trade"""
    BUY = "buy"
    SELL = "sell"


class ChainId(Enum):
    """Chains EVM supportées"""
    ETHEREUM = 1
    BSC = 56
    POLYGON = 137
    ARBITRUM = 42161
    OPTIMISM = 10
    BASE = 8453
    AVALANCHE = 43114


@dataclass
class Token:
    """Représentation d'un token ERC20"""
    address: str
    symbol: str
    decimals: int
    chain_id: int
    name: Optional[str] = None
    logo_uri: Optional[str] = None
    
    @property
    def is_native(self) -> bool:
        """True si token natif (ETH, MATIC, etc.)"""
        return self.address.lower() == "0xeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee"
    
    def to_wei(self, amount: Decimal) -> int:
        """Convertit un montant human-readable en wei"""
        return int(amount * Decimal(10 ** self.decimals))
    
    def from_wei(self, wei_amount: int) -> Decimal:
        """Convertit des wei en montant human-readable"""
        return Decimal(wei_amount) / Decimal(10 ** self.decimals)


@dataclass
class SwapQuote:
    """Quote retournée par 1inch API"""
    src_token: Token
    dst_token: Token
    src_amount: int  # en wei
    dst_amount: int  # en wei estimé
    
    # Routing info
    protocols: list[dict] = field(default_factory=list)
    gas_estimate: int = 0
    
    # Prix
    price: Decimal = Decimal("0")  # dst/src ratio
    price_impact: Decimal = Decimal("0")  # en pourcentage
    
    # Timestamps
    quoted_at: datetime = field(default_factory=datetime.utcnow)
    valid_until: Optional[datetime] = None
    
    @property
    def src_amount_human(self) -> Decimal:
        return self.src_token.from_wei(self.src_amount)
    
    @property
    def dst_amount_human(self) -> Decimal:
        return self.dst_token.from_wei(self.dst_amount)


@dataclass
class SwapTransaction:
    """Transaction de swap prête à être signée"""
    to: str
    data: str
    value: int  # ETH à envoyer (0 si token ERC20)
    gas: int
    gas_price: Optional[int] = None
    max_fee_per_gas: Optional[int] = None
    max_priority_fee_per_gas: Optional[int] = None
    
    # Metadata
    quote: Optional[SwapQuote] = None
    chain_id: int = 1


@dataclass
class TradeOrder:
    """Ordre de trade complet"""
    id: str
    wallet_address: str
    chain_id: int
    
    # Tokens
    src_token: Token
    dst_token: Token
    
    # Montants
    src_amount: int  # en wei
    min_dst_amount: Optional[int] = None  # slippage protection
    
    # Config
    slippage: Decimal = Decimal("1.0")  # en pourcentage
    direction: TradeDirection = TradeDirection.BUY
    
    # Status tracking
    status: TradeStatus = TradeStatus.PENDING
    tx_hash: Optional[str] = None
    
    # Timestamps
    created_at: datetime = field(default_factory=datetime.utcnow)
    executed_at: Optional[datetime] = None
    
    # Results
    actual_dst_amount: Optional[int] = None
    gas_used: Optional[int] = None
    error_message: Optional[str] = None


@dataclass
class TradeResult:
    """Résultat d'un trade exécuté"""
    order: TradeOrder
    success: bool
    tx_hash: Optional[str] = None
    
    # Montants réels
    src_amount_spent: int = 0
    dst_amount_received: int = 0
    
    # Coûts
    gas_used: int = 0
    gas_price: int = 0
    total_gas_cost: int = 0  # en wei
    
    # Timing
    execution_time_ms: int = 0
    confirmed_at: Optional[datetime] = None
    
    # Error handling
    error: Optional[str] = None
    error_code: Optional[str] = None
    
    @property
    def effective_price(self) -> Decimal:
        """Prix effectif obtenu"""
        if self.src_amount_spent == 0:
            return Decimal("0")
        src_dec = self.order.src_token.from_wei(self.src_amount_spent)
        dst_dec = self.order.dst_token.from_wei(self.dst_amount_received)
        return dst_dec / src_dec if src_dec > 0 else Decimal("0")


@dataclass
class GasSettings:
    """Configuration gas pour transactions"""
    max_gas_price_gwei: Decimal = Decimal("100")
    max_priority_fee_gwei: Decimal = Decimal("2")
    gas_limit_multiplier: Decimal = Decimal("1.2")  # 20% buffer
    use_eip1559: bool = True


@dataclass
class TradingConfig:
    """Configuration globale du trader"""
    # API
    oneinch_api_key: Optional[str] = None
    oneinch_base_url: str = "https://api.1inch.dev"
    
    # RPC endpoints par chain
    rpc_urls: dict[int, str] = field(default_factory=dict)
    
    # Limites
    max_slippage: Decimal = Decimal("5.0")
    min_trade_usd: Decimal = Decimal("10")
    max_trade_usd: Decimal = Decimal("10000")
    
    # Gas
    gas_settings: GasSettings = field(default_factory=GasSettings)
    
    # Timeouts (en secondes)
    quote_timeout: int = 10
    tx_timeout: int = 120
    confirmation_blocks: int = 2
