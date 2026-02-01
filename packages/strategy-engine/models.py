"""
Strategy Engine Models - Dataclasses pour stratégies auto-trading
"""
from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from typing import Optional, Any
from datetime import datetime


class SignalType(Enum):
    """Type de signal de trading"""
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"
    CLOSE = "close"


class PositionStatus(Enum):
    """Statut d'une position"""
    OPEN = "open"
    CLOSED = "closed"
    PENDING = "pending"
    CANCELLED = "cancelled"


class StrategyStatus(Enum):
    """Statut d'une stratégie"""
    ACTIVE = "active"
    PAUSED = "paused"
    STOPPED = "stopped"
    ERROR = "error"


class TimeFrame(Enum):
    """Intervalles de temps pour l'analyse"""
    M1 = "1m"
    M5 = "5m"
    M15 = "15m"
    M30 = "30m"
    H1 = "1h"
    H4 = "4h"
    D1 = "1d"
    W1 = "1w"


@dataclass
class StrategyConfig:
    """
    Configuration pour une stratégie de trading
    """
    # Identifiants
    strategy_id: str
    strategy_type: str  # "dca", "grid", "momentum"
    name: str
    
    # Token cible
    token_address: str
    token_symbol: str
    chain_id: int = 1
    
    # Capital
    total_budget: Decimal = Decimal("1000")  # Budget total alloué
    max_position_size: Decimal = Decimal("100")  # Max par position
    min_trade_size: Decimal = Decimal("10")  # Min par trade
    
    # Risk management
    stop_loss_pct: Optional[Decimal] = None  # Stop loss en %
    take_profit_pct: Optional[Decimal] = None  # Take profit en %
    max_drawdown_pct: Decimal = Decimal("20")  # Drawdown max
    
    # Slippage & Gas
    max_slippage: Decimal = Decimal("2.0")
    max_gas_gwei: Decimal = Decimal("100")
    
    # Paramètres spécifiques à chaque stratégie
    params: dict[str, Any] = field(default_factory=dict)
    
    # Metadata
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None
    
    def __post_init__(self):
        if isinstance(self.total_budget, (int, float, str)):
            self.total_budget = Decimal(str(self.total_budget))
        if isinstance(self.max_position_size, (int, float, str)):
            self.max_position_size = Decimal(str(self.max_position_size))


@dataclass
class TradeSignal:
    """
    Signal de trading généré par une stratégie
    """
    # Identifiant
    signal_id: str
    strategy_id: str
    
    # Signal
    signal_type: SignalType
    token_address: str
    chain_id: int
    
    # Montant suggéré
    amount: Decimal  # En token de base (ETH, USDC, etc.)
    price_target: Optional[Decimal] = None  # Prix cible
    
    # Contexte
    confidence: Decimal = Decimal("0.5")  # 0-1, niveau de confiance
    reason: str = ""  # Explication du signal
    indicators: dict[str, Any] = field(default_factory=dict)  # RSI, MACD, etc.
    
    # Timestamps
    generated_at: datetime = field(default_factory=datetime.utcnow)
    valid_until: Optional[datetime] = None
    
    # Execution tracking
    executed: bool = False
    executed_at: Optional[datetime] = None
    tx_hash: Optional[str] = None
    
    @property
    def is_valid(self) -> bool:
        """Vérifie si le signal est encore valide"""
        if self.valid_until is None:
            return True
        return datetime.utcnow() < self.valid_until
    
    @property
    def is_actionable(self) -> bool:
        """Signal actionnable (pas HOLD et pas déjà exécuté)"""
        return (
            self.signal_type in (SignalType.BUY, SignalType.SELL, SignalType.CLOSE)
            and not self.executed
            and self.is_valid
        )


@dataclass
class Position:
    """
    Position ouverte ou fermée
    """
    # Identifiants
    position_id: str
    strategy_id: str
    
    # Token
    token_address: str
    token_symbol: str
    chain_id: int
    
    # Montants
    entry_amount: Decimal  # Montant investi (en quote token)
    token_amount: Decimal  # Quantité de tokens achetés
    entry_price: Decimal  # Prix d'entrée moyen
    
    # Status
    status: PositionStatus = PositionStatus.OPEN
    
    # Exit info (si fermée)
    exit_price: Optional[Decimal] = None
    exit_amount: Optional[Decimal] = None
    realized_pnl: Optional[Decimal] = None
    realized_pnl_pct: Optional[Decimal] = None
    
    # Risk levels
    stop_loss_price: Optional[Decimal] = None
    take_profit_price: Optional[Decimal] = None
    
    # Timestamps
    opened_at: datetime = field(default_factory=datetime.utcnow)
    closed_at: Optional[datetime] = None
    last_updated: datetime = field(default_factory=datetime.utcnow)
    
    # Transactions
    entry_tx_hash: Optional[str] = None
    exit_tx_hash: Optional[str] = None
    
    # DCA tracking
    cost_basis: Decimal = Decimal("0")  # Coût total investi
    num_entries: int = 1  # Nombre d'entrées (DCA)
    
    def update_with_dca(self, additional_amount: Decimal, additional_tokens: Decimal):
        """Met à jour la position avec un nouvel achat DCA"""
        new_cost = self.cost_basis + additional_amount
        new_tokens = self.token_amount + additional_tokens
        
        self.cost_basis = new_cost
        self.token_amount = new_tokens
        self.entry_amount = new_cost
        self.entry_price = new_cost / new_tokens if new_tokens > 0 else Decimal("0")
        self.num_entries += 1
        self.last_updated = datetime.utcnow()
    
    def calculate_pnl(self, current_price: Decimal) -> tuple[Decimal, Decimal]:
        """
        Calcule le PnL actuel
        
        Returns:
            (pnl_value, pnl_percentage)
        """
        current_value = self.token_amount * current_price
        pnl = current_value - self.cost_basis
        pnl_pct = (pnl / self.cost_basis * 100) if self.cost_basis > 0 else Decimal("0")
        return pnl, pnl_pct
    
    def close(self, exit_price: Decimal, exit_amount: Decimal, tx_hash: Optional[str] = None):
        """Ferme la position"""
        self.status = PositionStatus.CLOSED
        self.exit_price = exit_price
        self.exit_amount = exit_amount
        self.realized_pnl = exit_amount - self.cost_basis
        self.realized_pnl_pct = (
            (self.realized_pnl / self.cost_basis * 100) 
            if self.cost_basis > 0 else Decimal("0")
        )
        self.closed_at = datetime.utcnow()
        self.exit_tx_hash = tx_hash


@dataclass
class Strategy:
    """
    Représentation complète d'une stratégie de trading
    """
    # Configuration
    config: StrategyConfig
    
    # État
    status: StrategyStatus = StrategyStatus.PAUSED
    
    # Positions
    positions: list[Position] = field(default_factory=list)
    
    # Signaux générés
    signals: list[TradeSignal] = field(default_factory=list)
    
    # Métriques
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    total_pnl: Decimal = Decimal("0")
    max_drawdown: Decimal = Decimal("0")
    
    # Capital tracking
    allocated_capital: Decimal = Decimal("0")  # Capital actuellement utilisé
    available_capital: Decimal = Decimal("0")  # Capital disponible
    
    # Timestamps
    started_at: Optional[datetime] = None
    last_trade_at: Optional[datetime] = None
    last_analysis_at: Optional[datetime] = None
    
    # Error tracking
    last_error: Optional[str] = None
    error_count: int = 0
    
    def __post_init__(self):
        self.available_capital = self.config.total_budget - self.allocated_capital
    
    @property
    def open_positions(self) -> list[Position]:
        """Retourne les positions ouvertes"""
        return [p for p in self.positions if p.status == PositionStatus.OPEN]
    
    @property
    def win_rate(self) -> Decimal:
        """Calcule le win rate"""
        if self.total_trades == 0:
            return Decimal("0")
        return Decimal(self.winning_trades) / Decimal(self.total_trades) * 100
    
    def add_signal(self, signal: TradeSignal):
        """Ajoute un signal"""
        self.signals.append(signal)
        # Garde les 100 derniers signaux
        if len(self.signals) > 100:
            self.signals = self.signals[-100:]
    
    def record_trade(self, pnl: Decimal):
        """Enregistre un trade terminé"""
        self.total_trades += 1
        self.total_pnl += pnl
        self.last_trade_at = datetime.utcnow()
        
        if pnl > 0:
            self.winning_trades += 1
        elif pnl < 0:
            self.losing_trades += 1


@dataclass
class MarketData:
    """
    Données de marché pour l'analyse
    """
    token_address: str
    chain_id: int
    
    # Prix
    current_price: Decimal
    price_24h_ago: Optional[Decimal] = None
    price_change_24h: Optional[Decimal] = None
    
    # Volume
    volume_24h: Optional[Decimal] = None
    
    # OHLCV récent
    ohlcv: list[dict] = field(default_factory=list)  # [{open, high, low, close, volume, timestamp}]
    
    # Indicateurs calculés
    rsi_14: Optional[Decimal] = None
    macd_line: Optional[Decimal] = None
    macd_signal: Optional[Decimal] = None
    macd_histogram: Optional[Decimal] = None
    sma_20: Optional[Decimal] = None
    sma_50: Optional[Decimal] = None
    ema_12: Optional[Decimal] = None
    ema_26: Optional[Decimal] = None
    bollinger_upper: Optional[Decimal] = None
    bollinger_lower: Optional[Decimal] = None
    
    # Timestamp
    fetched_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class ExecutionResult:
    """
    Résultat de l'exécution d'un signal
    """
    signal: TradeSignal
    success: bool
    
    # Trade details
    tx_hash: Optional[str] = None
    executed_amount: Decimal = Decimal("0")
    executed_price: Decimal = Decimal("0")
    
    # Costs
    gas_used: int = 0
    gas_cost: Decimal = Decimal("0")
    slippage_actual: Decimal = Decimal("0")
    
    # Timing
    execution_time_ms: int = 0
    executed_at: datetime = field(default_factory=datetime.utcnow)
    
    # Error
    error: Optional[str] = None
    error_code: Optional[str] = None
