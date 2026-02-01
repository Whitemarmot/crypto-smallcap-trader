# 🏗️ Architecture - Crypto Smallcap Trader

> Auto-trading multi-wallet pour EVM chains avec stratégies configurables

---

## 1. Vue d'Ensemble du Système

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           CRYPTO SMALLCAP TRADER                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐  │
│  │  Streamlit  │    │  Scheduler  │    │  Telegram   │    │   Alerts    │  │
│  │  Dashboard  │    │   (APSch)   │    │     Bot     │    │   System    │  │
│  └──────┬──────┘    └──────┬──────┘    └──────┬──────┘    └──────┬──────┘  │
│         │                  │                  │                  │         │
│  ───────┴──────────────────┴──────────────────┴──────────────────┴───────  │
│                              APPLICATION LAYER                              │
│  ────────────────────────────────────────────────────────────────────────  │
│                                                                             │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐  │
│  │   Wallet    │    │  Strategy   │    │  Risk       │    │  Data       │  │
│  │   Manager   │    │   Engine    │    │  Manager    │    │  Collector  │  │
│  └──────┬──────┘    └──────┬──────┘    └──────┬──────┘    └──────┬──────┘  │
│         │                  │                  │                  │         │
│  ───────┴──────────────────┴──────────────────┴──────────────────┴───────  │
│                               CORE SERVICES                                 │
│  ────────────────────────────────────────────────────────────────────────  │
│                                                                             │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐  │
│  │  Trading    │    │  Price      │    │  Sentiment  │    │  Social     │  │
│  │   Engine    │    │   Oracle    │    │   Analyzer  │    │   Scraper   │  │
│  └──────┬──────┘    └──────┬──────┘    └──────┬──────┘    └──────┬──────┘  │
│         │                  │                  │                  │         │
│  ───────┴──────────────────┴──────────────────┴──────────────────┴───────  │
│                               INFRASTRUCTURE                                │
│  ────────────────────────────────────────────────────────────────────────  │
│                                                                             │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐  │
│  │   SQLite    │    │   1inch     │    │ CoinGecko/  │    │  Twitter/   │  │
│  │     DB      │    │     API     │    │ DexScreener │    │   Reddit    │  │
│  └─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Principes Clés

| Principe | Description |
|----------|-------------|
| **Usage personnel** | Pas d'authentification, config locale |
| **Multi-wallet** | Gestion de N wallets avec clés chiffrées |
| **Multi-chain** | ETH, BSC, Base, Arbitrum, Polygon |
| **Modulaire** | Stratégies pluggables |
| **Event-driven** | Réactions en temps réel aux signaux |

---

## 2. Composants Principaux

### 2.1 Wallet Manager

```python
# packages/wallet-manager/manager.py

class WalletManager:
    """Gestion centralisée des wallets"""
    
    def __init__(self, db: Database, master_password: str):
        self.db = db
        self.cipher = derive_key(master_password)
        self._cache: Dict[str, LocalAccount] = {}
    
    def create_wallet(self, label: str, chain_ids: List[int]) -> Wallet
    def import_wallet(self, private_key: str, label: str) -> Wallet
    def list_wallets(self) -> List[Wallet]
    def get_account(self, wallet_id: str) -> LocalAccount
    def get_balances(self, wallet_id: str) -> Dict[int, Dict[str, Decimal]]
```

**Responsabilités:**
- Création/import de wallets EVM
- Chiffrement des clés privées (AES-256)
- Cache des comptes déchiffrés en mémoire
- Agrégation des balances multi-chain

### 2.2 Strategy Engine

```python
# packages/strategy-engine/engine.py

class StrategyEngine:
    """Orchestrateur des stratégies de trading"""
    
    def __init__(
        self,
        wallet_manager: WalletManager,
        trading_engine: Trader,
        risk_manager: RiskManager,
        db: Database
    ):
        self.strategies: Dict[str, BaseStrategy] = {}
        self.active_jobs: Dict[str, StrategyJob] = {}
    
    def register_strategy(self, strategy: BaseStrategy)
    def create_job(self, strategy_id: str, config: StrategyConfig) -> StrategyJob
    def start_job(self, job_id: str)
    def stop_job(self, job_id: str)
    def get_job_stats(self, job_id: str) -> JobStats

class BaseStrategy(ABC):
    """Interface pour toutes les stratégies"""
    
    @abstractmethod
    async def on_tick(self, context: TickContext) -> List[Signal]
    
    @abstractmethod
    async def on_signal(self, signal: Signal) -> Optional[TradeOrder]
    
    @property
    @abstractmethod
    def config_schema(self) -> Dict  # JSON Schema pour la config
```

### 2.3 Risk Manager

```python
# packages/risk-manager/risk.py

@dataclass
class RiskLimits:
    max_position_size_pct: Decimal = Decimal("10")  # % du portfolio
    max_daily_loss_pct: Decimal = Decimal("5")      # Stop trading si atteint
    max_single_trade_pct: Decimal = Decimal("2")    # Par trade
    max_gas_gwei: int = 100                          # Gas cap
    min_liquidity_usd: Decimal = Decimal("50000")   # Liquidité minimum
    max_slippage_pct: Decimal = Decimal("3")
    cooldown_after_loss_min: int = 30               # Pause après perte

class RiskManager:
    """Contrôle et limite les risques"""
    
    def __init__(self, limits: RiskLimits, db: Database):
        self.limits = limits
        self.db = db
    
    async def check_trade(self, order: TradeOrder) -> RiskCheckResult
    async def record_trade(self, result: TradeResult)
    async def get_daily_pnl(self, wallet_id: str) -> Decimal
    async def is_trading_allowed(self, wallet_id: str) -> bool
    async def check_token_safety(self, token: str, chain_id: int) -> TokenSafetyScore
```

### 2.4 Data Collector

```python
# packages/data-collector/collector.py

class DataCollector:
    """Agrège les données de marché et sociales"""
    
    def __init__(self, db: Database):
        self.price_sources = [DexScreener(), CoinGecko(), OneInchPrices()]
        self.social_sources = [TwitterScraper(), RedditScraper(), TelegramMonitor()]
    
    async def get_token_data(self, token: str, chain_id: int) -> TokenData
    async def get_price_history(self, token: str, timeframe: str) -> List[OHLCV]
    async def get_social_mentions(self, token: str, hours: int = 24) -> SocialData
    async def subscribe_price(self, token: str, callback: Callable)
```

### 2.5 Trading Engine (existant)

Le `Trader` dans `packages/trading-engine/trader.py` gère déjà:
- Swaps via 1inch Aggregator
- Multi-chain support
- Gas estimation EIP-1559
- Approvals automatiques

---

## 3. Flux de Données

### 3.1 Flux Principal de Trading

```
┌──────────────┐
│   Trigger    │ (Scheduler / Manual / Signal)
└──────┬───────┘
       │
       ▼
┌──────────────┐     ┌──────────────┐
│   Strategy   │────▶│ Data Collect │ (Prix, Sentiment, etc.)
│    on_tick   │◀────│              │
└──────┬───────┘     └──────────────┘
       │
       │ Signal(BUY/SELL)
       ▼
┌──────────────┐
│   Strategy   │
│  on_signal   │
└──────┬───────┘
       │
       │ TradeOrder
       ▼
┌──────────────┐     ┌──────────────┐
│     Risk     │────▶│   REJECT     │ (Limite atteinte)
│   Manager    │     └──────────────┘
└──────┬───────┘
       │ APPROVED
       ▼
┌──────────────┐
│   Trading    │
│    Engine    │
└──────┬───────┘
       │
       │ TradeResult
       ▼
┌──────────────┐     ┌──────────────┐
│   Database   │     │    Alerts    │ (Telegram, etc.)
│    Record    │     │   Dispatch   │
└──────────────┘     └──────────────┘
```

### 3.2 Flux de Données Temps Réel

```
External Sources                    Internal Processing
─────────────────                   ────────────────────

┌─────────────┐
│ DexScreener │──┐
│   WebSocket │  │     ┌────────────────┐     ┌─────────────┐
└─────────────┘  │     │                │     │             │
                 ├────▶│  Price Oracle  │────▶│  Strategy   │
┌─────────────┐  │     │                │     │   Engine    │
│  1inch API  │──┘     └────────────────┘     └─────────────┘
│   Quotes    │
└─────────────┘

┌─────────────┐
│   Twitter   │──┐
│     API     │  │     ┌────────────────┐     ┌─────────────┐
└─────────────┘  │     │                │     │             │
                 ├────▶│   Sentiment    │────▶│  Strategy   │
┌─────────────┐  │     │    Analyzer    │     │   Engine    │
│   Reddit    │──┘     └────────────────┘     └─────────────┘
│     API     │
└─────────────┘
```

---

## 4. Stratégies de Trading

### 4.1 DCA (Dollar Cost Averaging)

```python
class DCAStrategy(BaseStrategy):
    """Achats réguliers à intervalles fixes"""
    
    @dataclass
    class Config:
        token_address: str
        chain_id: int
        amount_per_buy: Decimal      # Montant en stablecoin
        interval_hours: int          # Fréquence
        total_budget: Optional[Decimal]  # Budget total (optionnel)
        price_deviation_skip: Decimal = Decimal("5")  # Skip si prix +X%
    
    async def on_tick(self, ctx: TickContext) -> List[Signal]:
        if self._should_buy_now(ctx):
            current_price = await self.get_price(ctx)
            avg_price = await self.get_avg_buy_price()
            
            # Skip si prix trop élevé vs moyenne
            if avg_price and current_price > avg_price * (1 + self.config.price_deviation_skip/100):
                return []
            
            return [Signal(action=Action.BUY, amount=self.config.amount_per_buy)]
        return []
```

**Use case:** Accumulation long-terme d'un token avec lissage du prix d'entrée.

---

### 4.2 Grid Trading

```python
class GridStrategy(BaseStrategy):
    """Grille d'ordres buy/sell à niveaux fixes"""
    
    @dataclass
    class Config:
        token_address: str
        chain_id: int
        lower_price: Decimal         # Limite basse
        upper_price: Decimal         # Limite haute
        grid_levels: int             # Nombre de niveaux (ex: 10)
        amount_per_grid: Decimal     # Montant par niveau
        rebalance_on_breakout: bool  # Re-centrer si prix sort
    
    def __init__(self, config: Config):
        self.grids = self._calculate_grid_levels()
        self.active_orders: Dict[int, GridOrder] = {}
    
    async def on_tick(self, ctx: TickContext) -> List[Signal]:
        price = await self.get_price(ctx)
        signals = []
        
        for level, grid in self.grids.items():
            if price <= grid.buy_price and not grid.is_filled:
                signals.append(Signal(
                    action=Action.BUY,
                    price=grid.buy_price,
                    grid_level=level
                ))
            elif price >= grid.sell_price and grid.is_filled:
                signals.append(Signal(
                    action=Action.SELL,
                    price=grid.sell_price,
                    grid_level=level
                ))
        
        return signals
```

**Use case:** Range trading sur des tokens avec volatilité prévisible.

---

### 4.3 Sniper

```python
class SniperStrategy(BaseStrategy):
    """Achat rapide au listing/launch"""
    
    @dataclass
    class Config:
        # Cibles
        target_tokens: List[str]      # Adresses à surveiller
        monitor_factories: List[str]  # Factory contracts (Uniswap, etc.)
        
        # Conditions d'entrée
        min_liquidity: Decimal        # Liquidité minimale
        max_buy_tax: Decimal          # Tax max acceptable
        max_sell_tax: Decimal
        honeypot_check: bool = True
        
        # Exécution
        buy_amount: Decimal
        gas_multiplier: Decimal = Decimal("1.5")  # Priority gas
        max_slippage: Decimal = Decimal("10")
        
        # Sortie
        take_profit_pct: Decimal = Decimal("100")  # +100% = 2x
        stop_loss_pct: Decimal = Decimal("50")     # -50%
        trailing_stop_pct: Optional[Decimal] = None
    
    async def on_new_pair(self, pair: PairCreatedEvent) -> Optional[Signal]:
        # Vérifications de sécurité
        safety = await self.check_token_safety(pair.token)
        if not safety.is_safe:
            return None
        
        # Vérifier liquidité
        if pair.initial_liquidity < self.config.min_liquidity:
            return None
        
        return Signal(
            action=Action.BUY,
            amount=self.config.buy_amount,
            priority=Priority.HIGH,
            gas_multiplier=self.config.gas_multiplier
        )
```

**Use case:** Snipe les nouveaux listings avec protection anti-rug.

---

### 4.4 Copy Trading

```python
class CopyTradingStrategy(BaseStrategy):
    """Réplique les trades de wallets performants"""
    
    @dataclass
    class Config:
        watch_wallets: List[str]      # Wallets à copier
        chains: List[int]
        
        # Filtres
        min_trade_size_usd: Decimal   # Ignorer les petits trades
        copy_delay_seconds: int = 5   # Délai avant copie
        token_whitelist: Optional[List[str]]
        token_blacklist: List[str] = field(default_factory=list)
        
        # Sizing
        copy_mode: Literal["fixed", "proportional"]
        fixed_amount: Optional[Decimal]
        portfolio_pct: Optional[Decimal]  # % de notre portfolio
    
    async def on_wallet_tx(self, tx: WalletTransaction) -> Optional[Signal]:
        if not self._is_relevant_trade(tx):
            return None
        
        # Attendre avant de copier (éviter front-run detection)
        await asyncio.sleep(self.config.copy_delay_seconds)
        
        # Calculer le montant
        if self.config.copy_mode == "fixed":
            amount = self.config.fixed_amount
        else:
            their_pct = tx.amount_usd / await self.get_wallet_value(tx.wallet)
            amount = their_pct * await self.get_our_portfolio_value()
        
        return Signal(
            action=tx.action,  # BUY or SELL
            token=tx.token,
            amount=amount,
            reason=f"Copy {tx.wallet[:8]}..."
        )
```

**Use case:** Suivre des smart money wallets identifiés.

---

### 4.5 Sentiment-Based Trading

```python
class SentimentStrategy(BaseStrategy):
    """Trading basé sur l'analyse de sentiment social"""
    
    @dataclass
    class Config:
        tokens_watchlist: List[str]
        
        # Sources
        twitter_enabled: bool = True
        reddit_enabled: bool = True
        telegram_enabled: bool = True
        
        # Seuils
        sentiment_buy_threshold: float = 0.7   # Score > 0.7 = BUY
        sentiment_sell_threshold: float = 0.3  # Score < 0.3 = SELL
        min_mentions: int = 50                 # Mentions min pour signal
        momentum_window_hours: int = 4         # Fenêtre d'analyse
        
        # AI
        use_llm_analysis: bool = True
        llm_model: str = "claude-3-haiku"
    
    async def on_tick(self, ctx: TickContext) -> List[Signal]:
        signals = []
        
        for token in self.config.tokens_watchlist:
            # Collecter les mentions
            mentions = await self.collect_mentions(token)
            
            if len(mentions) < self.config.min_mentions:
                continue
            
            # Analyser le sentiment
            if self.config.use_llm_analysis:
                sentiment = await self.llm_sentiment_analysis(mentions)
            else:
                sentiment = self.basic_sentiment_analysis(mentions)
            
            # Calculer le momentum
            momentum = await self.calculate_sentiment_momentum(token)
            
            # Générer signal
            if sentiment.score > self.config.sentiment_buy_threshold and momentum > 0:
                signals.append(Signal(
                    action=Action.BUY,
                    token=token,
                    confidence=sentiment.score,
                    reason=f"Sentiment: {sentiment.score:.2f}, Momentum: +{momentum:.1f}%"
                ))
        
        return signals
```

**Use case:** Capter les pumps liés au buzz social avant le mouvement de prix.

---

## 5. Gestion des Risques

### 5.1 Niveaux de Protection

```
┌─────────────────────────────────────────────────────────────────┐
│                     RISK MANAGEMENT LAYERS                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Level 1: PRE-TRADE CHECKS                                       │
│  ├── Token safety (honeypot, taxes, liquidity)                  │
│  ├── Position sizing limits                                      │
│  ├── Daily loss limit check                                      │
│  └── Gas price check                                             │
│                                                                  │
│  Level 2: TRADE EXECUTION                                        │
│  ├── Slippage protection                                         │
│  ├── MEV protection (private mempool optional)                   │
│  ├── Transaction deadline                                        │
│  └── Gas limit cap                                               │
│                                                                  │
│  Level 3: POST-TRADE MONITORING                                  │
│  ├── Stop-loss automation                                        │
│  ├── Take-profit triggers                                        │
│  ├── Trailing stops                                              │
│  └── Time-based exits                                            │
│                                                                  │
│  Level 4: PORTFOLIO LEVEL                                        │
│  ├── Max exposure per token                                      │
│  ├── Max exposure per chain                                      │
│  ├── Correlation limits                                          │
│  └── Emergency kill switch                                       │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 5.2 Token Safety Check

```python
@dataclass
class TokenSafetyScore:
    is_safe: bool
    score: int  # 0-100
    
    # Détails
    honeypot_risk: bool
    buy_tax: Decimal
    sell_tax: Decimal
    liquidity_usd: Decimal
    liquidity_locked: bool
    holder_concentration: Decimal  # % held by top 10
    contract_verified: bool
    has_mint_function: bool
    has_blacklist: bool
    
    warnings: List[str]
    
    @property
    def summary(self) -> str:
        if self.score >= 80:
            return "✅ Safe"
        elif self.score >= 50:
            return "⚠️ Caution"
        else:
            return "🚫 High Risk"

async def check_token_safety(token: str, chain_id: int) -> TokenSafetyScore:
    """Analyse complète de la sécurité d'un token"""
    
    # 1. Honeypot detection (simulation de buy/sell)
    honeypot = await simulate_trade(token, chain_id)
    
    # 2. Contract analysis
    contract = await get_contract_info(token, chain_id)
    
    # 3. Liquidity check
    liquidity = await get_liquidity_info(token, chain_id)
    
    # 4. Holder distribution
    holders = await get_holder_stats(token, chain_id)
    
    # Calculate score
    score = 100
    warnings = []
    
    if honeypot.is_honeypot:
        score = 0
        warnings.append("🚨 HONEYPOT DETECTED")
    
    if contract.buy_tax > 10:
        score -= 30
        warnings.append(f"High buy tax: {contract.buy_tax}%")
    
    if not liquidity.is_locked:
        score -= 20
        warnings.append("Liquidity not locked")
    
    if holders.top10_pct > 80:
        score -= 25
        warnings.append(f"High concentration: top 10 hold {holders.top10_pct}%")
    
    return TokenSafetyScore(
        is_safe=score >= 50 and not honeypot.is_honeypot,
        score=score,
        warnings=warnings,
        # ... autres champs
    )
```

### 5.3 Position Management

```python
class PositionManager:
    """Gestion des positions ouvertes avec stop-loss/take-profit"""
    
    async def create_position(
        self,
        trade_result: TradeResult,
        stop_loss_pct: Optional[Decimal] = None,
        take_profit_pct: Optional[Decimal] = None,
        trailing_stop_pct: Optional[Decimal] = None,
    ) -> Position:
        position = Position(
            id=str(uuid.uuid4()),
            wallet_id=trade_result.order.wallet_id,
            token=trade_result.order.dst_token,
            entry_price=trade_result.execution_price,
            quantity=trade_result.dst_amount_received,
            entry_time=datetime.utcnow(),
            stop_loss=self._calculate_stop_loss(trade_result, stop_loss_pct),
            take_profit=self._calculate_take_profit(trade_result, take_profit_pct),
            trailing_stop_pct=trailing_stop_pct,
        )
        
        await self.db.save_position(position)
        return position
    
    async def check_exits(self) -> List[Signal]:
        """Vérifie toutes les positions pour exits"""
        signals = []
        
        for position in await self.db.get_open_positions():
            current_price = await self.get_price(position.token)
            
            # Update trailing stop
            if position.trailing_stop_pct:
                position.update_trailing_stop(current_price)
            
            # Check stop-loss
            if position.stop_loss and current_price <= position.stop_loss:
                signals.append(Signal(
                    action=Action.SELL,
                    position_id=position.id,
                    reason="Stop-loss triggered"
                ))
            
            # Check take-profit
            elif position.take_profit and current_price >= position.take_profit:
                signals.append(Signal(
                    action=Action.SELL,
                    position_id=position.id,
                    reason="Take-profit triggered"
                ))
        
        return signals
```

---

## 6. Base de Données (SQLite)

### 6.1 Schéma

```sql
-- Wallets
CREATE TABLE wallets (
    id TEXT PRIMARY KEY,
    label TEXT NOT NULL,
    address TEXT NOT NULL UNIQUE,
    private_key_encrypted BLOB NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT 1
);

CREATE TABLE wallet_chains (
    wallet_id TEXT REFERENCES wallets(id),
    chain_id INTEGER NOT NULL,
    PRIMARY KEY (wallet_id, chain_id)
);

-- Strategies
CREATE TABLE strategy_jobs (
    id TEXT PRIMARY KEY,
    strategy_type TEXT NOT NULL,  -- 'dca', 'grid', 'sniper', etc.
    config JSON NOT NULL,
    wallet_id TEXT REFERENCES wallets(id),
    status TEXT DEFAULT 'stopped',  -- 'running', 'stopped', 'paused'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP,
    stopped_at TIMESTAMP
);

-- Trades
CREATE TABLE trades (
    id TEXT PRIMARY KEY,
    wallet_id TEXT REFERENCES wallets(id),
    strategy_job_id TEXT REFERENCES strategy_jobs(id),
    chain_id INTEGER NOT NULL,
    
    -- Trade details
    direction TEXT NOT NULL,  -- 'buy' or 'sell'
    src_token TEXT NOT NULL,
    dst_token TEXT NOT NULL,
    src_amount TEXT NOT NULL,  -- Decimal as string
    dst_amount TEXT,
    price TEXT,
    slippage TEXT,
    
    -- Execution
    tx_hash TEXT,
    status TEXT NOT NULL,  -- 'pending', 'submitted', 'confirmed', 'failed'
    gas_used INTEGER,
    gas_price TEXT,
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    submitted_at TIMESTAMP,
    confirmed_at TIMESTAMP,
    
    -- Error handling
    error_message TEXT,
    retry_count INTEGER DEFAULT 0
);

CREATE INDEX idx_trades_wallet ON trades(wallet_id);
CREATE INDEX idx_trades_status ON trades(status);
CREATE INDEX idx_trades_created ON trades(created_at);

-- Positions
CREATE TABLE positions (
    id TEXT PRIMARY KEY,
    wallet_id TEXT REFERENCES wallets(id),
    chain_id INTEGER NOT NULL,
    token TEXT NOT NULL,
    
    -- Entry
    entry_trade_id TEXT REFERENCES trades(id),
    entry_price TEXT NOT NULL,
    quantity TEXT NOT NULL,
    entry_time TIMESTAMP NOT NULL,
    
    -- Exit conditions
    stop_loss TEXT,
    take_profit TEXT,
    trailing_stop_pct TEXT,
    trailing_stop_price TEXT,
    
    -- Status
    status TEXT DEFAULT 'open',  -- 'open', 'closed'
    exit_trade_id TEXT REFERENCES trades(id),
    exit_price TEXT,
    exit_time TIMESTAMP,
    pnl TEXT,
    pnl_pct TEXT
);

-- Price history (cache)
CREATE TABLE price_cache (
    token TEXT NOT NULL,
    chain_id INTEGER NOT NULL,
    price TEXT NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    source TEXT,
    PRIMARY KEY (token, chain_id, timestamp)
);

-- Social mentions
CREATE TABLE social_mentions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    token TEXT NOT NULL,
    source TEXT NOT NULL,  -- 'twitter', 'reddit', 'telegram'
    content TEXT,
    author TEXT,
    sentiment_score REAL,
    timestamp TIMESTAMP NOT NULL,
    raw_data JSON
);

CREATE INDEX idx_mentions_token ON social_mentions(token, timestamp);

-- Daily stats
CREATE TABLE daily_stats (
    date DATE NOT NULL,
    wallet_id TEXT REFERENCES wallets(id),
    
    -- P&L
    starting_value_usd TEXT,
    ending_value_usd TEXT,
    pnl_usd TEXT,
    pnl_pct TEXT,
    
    -- Activity
    trades_count INTEGER DEFAULT 0,
    wins INTEGER DEFAULT 0,
    losses INTEGER DEFAULT 0,
    gas_spent_usd TEXT,
    
    PRIMARY KEY (date, wallet_id)
);

-- Alerts log
CREATE TABLE alerts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    type TEXT NOT NULL,  -- 'trade', 'risk', 'system', 'price'
    severity TEXT NOT NULL,  -- 'info', 'warning', 'critical'
    message TEXT NOT NULL,
    data JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    sent BOOLEAN DEFAULT 0
);

-- Token safety cache
CREATE TABLE token_safety (
    token TEXT NOT NULL,
    chain_id INTEGER NOT NULL,
    safety_score INTEGER,
    is_honeypot BOOLEAN,
    buy_tax TEXT,
    sell_tax TEXT,
    liquidity_usd TEXT,
    holder_data JSON,
    checked_at TIMESTAMP,
    PRIMARY KEY (token, chain_id)
);
```

### 6.2 Database Manager

```python
# packages/database/db.py

class Database:
    def __init__(self, path: str = "data/trader.db"):
        self.path = path
        self.connection = None
    
    async def connect(self):
        self.connection = await aiosqlite.connect(self.path)
        await self._run_migrations()
    
    # Wallets
    async def save_wallet(self, wallet: Wallet) -> None
    async def get_wallet(self, wallet_id: str) -> Optional[Wallet]
    async def list_wallets(self) -> List[Wallet]
    
    # Trades
    async def save_trade(self, trade: Trade) -> None
    async def get_trade(self, trade_id: str) -> Optional[Trade]
    async def get_trades(
        self,
        wallet_id: Optional[str] = None,
        status: Optional[str] = None,
        since: Optional[datetime] = None,
        limit: int = 100
    ) -> List[Trade]
    
    # Positions
    async def save_position(self, position: Position) -> None
    async def get_open_positions(self, wallet_id: Optional[str] = None) -> List[Position]
    async def close_position(self, position_id: str, exit_trade: Trade) -> None
    
    # Stats
    async def get_daily_stats(self, wallet_id: str, days: int = 30) -> List[DailyStats]
    async def update_daily_stats(self, wallet_id: str) -> None
    
    # Cache
    async def cache_price(self, token: str, chain_id: int, price: Decimal) -> None
    async def get_cached_price(self, token: str, chain_id: int, max_age_sec: int = 60) -> Optional[Decimal]
```

---

## 7. Interface Utilisateur (Streamlit)

### 7.1 Structure des Pages

```
pages/
├── 1_🏠_Dashboard.py       # Vue d'ensemble
├── 2_💰_Wallets.py         # Gestion wallets
├── 3_🤖_Strategies.py      # Config stratégies
├── 4_📊_Positions.py       # Positions ouvertes
├── 5_📈_Analytics.py       # Stats & performance
├── 6_⚙️_Settings.py        # Configuration
└── 7_🔔_Alerts.py          # Historique alertes
```

### 7.2 Dashboard Principal

```python
# pages/1_🏠_Dashboard.py

import streamlit as st

st.set_page_config(page_title="Crypto Trader", layout="wide")

# Header avec stats globales
col1, col2, col3, col4 = st.columns(4)
col1.metric("Portfolio Total", "$12,450", "+$320 (2.6%)")
col2.metric("P&L Today", "+$180", "+1.5%")
col3.metric("Active Strategies", "3", "2 running")
col4.metric("Open Positions", "5", "2 in profit")

# Wallets overview
st.subheader("💰 Wallets")
for wallet in get_wallets():
    with st.expander(f"{wallet.label} - {wallet.address[:8]}..."):
        display_wallet_balances(wallet)

# Active strategies
st.subheader("🤖 Stratégies Actives")
for job in get_active_jobs():
    col1, col2, col3 = st.columns([3, 1, 1])
    col1.write(f"**{job.strategy_type}** - {job.config.token}")
    col2.write(f"P&L: {job.pnl}")
    if col3.button("Stop", key=job.id):
        stop_job(job.id)

# Recent trades
st.subheader("📜 Recent Trades")
trades_df = get_recent_trades(limit=20)
st.dataframe(trades_df)

# Alerts
st.subheader("🔔 Alertes Récentes")
for alert in get_recent_alerts(limit=5):
    st.warning(f"[{alert.type}] {alert.message}")
```

---

## 8. Configuration

### 8.1 Structure de Config

```yaml
# config/config.yaml

# General
environment: production
data_dir: ./data

# Master password (pour chiffrement wallets)
# Set via MASTER_PASSWORD env var

# Chains
chains:
  - chain_id: 1
    name: Ethereum
    rpc_url: ${ETH_RPC_URL}
    explorer: https://etherscan.io
  - chain_id: 56
    name: BSC
    rpc_url: ${BSC_RPC_URL}
    explorer: https://bscscan.com
  - chain_id: 8453
    name: Base
    rpc_url: ${BASE_RPC_URL}
    explorer: https://basescan.org

# APIs
apis:
  oneinch:
    api_key: ${ONEINCH_API_KEY}
    base_url: https://api.1inch.dev
  coingecko:
    api_key: ${COINGECKO_API_KEY}  # Optional
  dexscreener:
    base_url: https://api.dexscreener.com

# Trading defaults
trading:
  max_slippage: 3.0
  gas_limit_multiplier: 1.2
  tx_timeout: 120
  quote_timeout: 10

# Risk defaults
risk:
  max_position_pct: 10
  max_daily_loss_pct: 5
  max_single_trade_pct: 2
  min_liquidity_usd: 50000
  cooldown_after_loss_min: 30

# Alerts
alerts:
  telegram:
    enabled: true
    bot_token: ${TELEGRAM_BOT_TOKEN}
    chat_id: ${TELEGRAM_CHAT_ID}

# Scheduler
scheduler:
  timezone: UTC
  price_check_interval: 60  # seconds
  position_check_interval: 30
```

---

## 9. Déploiement

### 9.1 Structure des Fichiers

```
crypto-smallcap-trader/
├── packages/
│   ├── wallet-manager/
│   ├── strategy-engine/
│   ├── risk-manager/
│   ├── data-collector/
│   ├── trading-engine/      # Existant
│   ├── wallet/              # Existant
│   └── frontend-streamlit/  # Existant
├── config/
│   ├── config.yaml
│   └── strategies/          # Configs de stratégies
├── data/
│   ├── trader.db            # SQLite
│   └── logs/
├── scripts/
│   ├── start.sh
│   └── backup.sh
├── tests/
├── docs/
│   └── ARCHITECTURE.md
├── requirements.txt
├── docker-compose.yml
└── README.md
```

### 9.2 Docker Compose

```yaml
version: '3.8'

services:
  trader:
    build: .
    volumes:
      - ./data:/app/data
      - ./config:/app/config
    environment:
      - MASTER_PASSWORD=${MASTER_PASSWORD}
      - ONEINCH_API_KEY=${ONEINCH_API_KEY}
      - ETH_RPC_URL=${ETH_RPC_URL}
    ports:
      - "8501:8501"  # Streamlit
    restart: unless-stopped

  # Optional: Telegram bot for alerts
  telegram-bot:
    build:
      context: .
      dockerfile: Dockerfile.telegram
    environment:
      - TELEGRAM_BOT_TOKEN=${TELEGRAM_BOT_TOKEN}
    depends_on:
      - trader
    restart: unless-stopped
```

---

## 10. Roadmap

### Phase 1: Foundation ✅
- [x] Wallet management
- [x] Trading engine (1inch)
- [ ] SQLite database
- [ ] Basic Streamlit UI

### Phase 2: Strategies
- [ ] DCA strategy
- [ ] Grid trading
- [ ] Position management (SL/TP)

### Phase 3: Intelligence
- [ ] Sniper strategy
- [ ] Copy trading
- [ ] Sentiment analysis
- [ ] Token safety checks

### Phase 4: Polish
- [ ] Telegram alerts
- [ ] Advanced analytics
- [ ] Backtesting framework
- [ ] Multi-user (optional)

---

*Document généré le 2026-02-01*
