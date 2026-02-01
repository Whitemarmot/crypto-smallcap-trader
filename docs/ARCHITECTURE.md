# Architecture - Crypto Smallcap Trader

## 🎯 Vue d'Ensemble

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           CRYPTO SMALLCAP TRADER                         │
│                    Agent AI de Trading pour Smallcaps                    │
└─────────────────────────────────────────────────────────────────────────┘

┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│   FRONTEND   │◄───│  AI-DECISION │◄───│   SOCIAL     │    │   WALLET     │
│   (React)    │    │   (Claude)   │    │  ANALYZER    │    │  (Solana)    │
└──────┬───────┘    └──────┬───────┘    └──────┬───────┘    └──────┬───────┘
       │                   │                   │                   │
       │                   ▼                   │                   │
       │           ┌──────────────┐            │                   │
       └──────────►│   TRADING    │◄───────────┴───────────────────┘
                   │   ENGINE     │
                   └──────┬───────┘
                          │
                          ▼
                   ┌──────────────┐
                   │   SOLANA     │
                   │  BLOCKCHAIN  │
                   └──────────────┘
```

## 📦 Packages

| Package | Responsabilité | Port |
|---------|---------------|------|
| `@cst/wallet` | Gestion wallet Solana, signatures, balances | - |
| `@cst/social-analyzer` | Scraping Twitter/Reddit/Telegram, scoring | 3001 |
| `@cst/ai-decision` | Analyse IA, décisions buy/sell via Claude | 3002 |
| `@cst/trading-engine` | Orchestration, exécution trades, DEX | 3003 |
| `@cst/frontend` | Dashboard React, monitoring temps réel | 5173 |

---

## 🛠️ Stack Technique

### Backend
| Composant | Technologie | Justification |
|-----------|-------------|---------------|
| Runtime | **Node.js 20 LTS** | Performance async, écosystème crypto |
| Langage | **TypeScript 5.3+** | Type safety, maintenabilité |
| Monorepo | **Turborepo** | Build cache, parallel execution |
| HTTP Server | **Fastify** | Performance 2x Express |
| Validation | **Zod** | Runtime validation + TypeScript |
| Queue | **BullMQ + Redis** | Jobs asynchrones, retry |
| DB | **PostgreSQL + Prisma** | Historique trades, analytics |

### Blockchain
| Composant | Technologie | Justification |
|-----------|-------------|---------------|
| Blockchain | **Solana** | ~400ms finality, $0.00025/tx |
| SDK | **@solana/web3.js** | SDK officiel |
| SPL Tokens | **@solana/spl-token** | Interaction tokens |
| DEX | **Jupiter Aggregator** | Best price routing |
| RPC | **Helius / QuickNode** | RPC fiable, websockets |

### Frontend
| Composant | Technologie | Justification |
|-----------|-------------|---------------|
| Framework | **React 18** | Écosystème, performance |
| Build | **Vite** | HMR rapide, ESM natif |
| State | **Zustand** | Simple, performant |
| Charts | **Lightweight Charts** | TradingView quality |
| Styling | **Tailwind CSS** | Utility-first, rapide |
| Wallet UI | **@solana/wallet-adapter** | Multi-wallet support |

### AI
| Composant | Technologie | Justification |
|-----------|-------------|---------------|
| LLM | **Claude API (Anthropic)** | Raisonnement supérieur |
| Model | **claude-sonnet-4-20250514** | Balance coût/performance |
| Embeddings | **OpenAI ada-002** | Semantic search tokens |

---

## 🔄 Flux de Données

### 1. Pipeline Social → Decision
```
Twitter API ─┐
Reddit API  ─┼──► Social Analyzer ──► Sentiment Score ──► AI Decision
Telegram    ─┘         │                    │                  │
                       ▼                    ▼                  ▼
                  Raw Posts          Aggregated Data      BUY/SELL/HOLD
                  Storage            per Token            Signal
```

### 2. Pipeline Trading
```
┌─────────────────────────────────────────────────────────────────┐
│                      TRADING ENGINE LOOP                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  1. COLLECT      2. ANALYZE       3. DECIDE       4. EXECUTE    │
│  ───────────     ─────────────    ──────────      ───────────   │
│  │ Social   │    │ Sentiment  │   │ Claude   │   │ Jupiter  │   │
│  │ Analyzer │───►│ + Volume   │──►│ Analysis │──►│ Swap     │   │
│  │          │    │ + Price    │   │          │   │          │   │
│  └──────────┘    └────────────┘   └──────────┘   └──────────┘   │
│                                         │                        │
│                                         ▼                        │
│                                   ┌──────────┐                   │
│                                   │ Risk     │                   │
│                                   │ Manager  │                   │
│                                   └──────────┘                   │
└─────────────────────────────────────────────────────────────────┘
```

### 3. Data Flow Détaillé
```
[External Sources]           [Internal Services]           [Storage]
       │                            │                          │
Twitter ──────┐                     │                          │
       │      │   ┌─────────────────┼──────────────────┐       │
Reddit ───────┼──►│ Social Analyzer │                  │       │
       │      │   │  - Fetch posts  │                  │       │
Telegram ─────┘   │  - NLP scoring  │──────────────────┼──────►│ PostgreSQL
                  │  - Token detect │                  │       │ (posts, scores)
                  └────────┬────────┘                  │       │
                           │                           │       │
                           ▼                           │       │
                  ┌─────────────────┐                  │       │
Jupiter API ─────►│ Trading Engine  │                  │       │
                  │  - Price feeds  │──────────────────┼──────►│ PostgreSQL
Helius RPC ──────►│  - Order exec   │                  │       │ (trades, P&L)
                  │  - Portfolio    │                  │       │
                  └────────┬────────┘                  │       │
                           │                           │       │
                           ▼                           │       │
                  ┌─────────────────┐                  │       │
Claude API ──────►│  AI Decision    │                  │       │
                  │  - Sentiment    │──────────────────┼──────►│ PostgreSQL
                  │  - Risk eval    │                  │       │ (decisions)
                  │  - Trade signal │                  │       │
                  └─────────────────┘                  │       │
                                                       │       │
                  ┌─────────────────┐                  │       │
                  │    Frontend     │◄─────────────────┘       │
                  │  - Dashboard    │                          │
                  │  - Realtime     │◄─────────────────────────┘
                  └─────────────────┘      (WebSocket)
```

---

## 🔌 APIs Internes

### Social Analyzer API (port 3001)
```typescript
// GET /api/v1/sentiment/:token
// Retourne le score de sentiment pour un token
{
  token: "BONK",
  score: 0.73,           // -1 to 1
  volume: 1523,          // mentions 24h
  trending: true,
  sources: {
    twitter: { score: 0.8, count: 890 },
    reddit: { score: 0.6, count: 433 },
    telegram: { score: 0.7, count: 200 }
  },
  updatedAt: "2024-01-15T12:00:00Z"
}

// GET /api/v1/trending
// Liste des tokens trending
{
  tokens: [
    { symbol: "BONK", score: 0.73, change24h: "+45%" },
    { symbol: "WIF", score: 0.65, change24h: "+23%" }
  ]
}

// POST /api/v1/track
// Ajouter un token à tracker
{ token: "MYTOKEN", contract: "abc123..." }
```

### AI Decision API (port 3002)
```typescript
// POST /api/v1/analyze
// Analyse complète et décision
Request:
{
  token: "BONK",
  sentiment: { ... },      // from social-analyzer
  marketData: {
    price: 0.00001234,
    volume24h: 5000000,
    priceChange24h: 0.15,
    marketCap: 500000000
  },
  portfolio: {
    balance: 100,          // SOL
    positions: [...]
  }
}

Response:
{
  decision: "BUY",         // BUY | SELL | HOLD
  confidence: 0.82,        // 0 to 1
  reasoning: "Strong social momentum...",
  suggestedAction: {
    type: "BUY",
    amount: 5,             // SOL
    slippage: 0.5,         // %
    stopLoss: 0.00001000,
    takeProfit: 0.00001800
  }
}

// GET /api/v1/history
// Historique des décisions
{ decisions: [...], stats: { winRate: 0.67, ... } }
```

### Trading Engine API (port 3003)
```typescript
// POST /api/v1/trade/execute
// Exécuter un trade
Request:
{
  action: "BUY",
  tokenMint: "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263",
  amountIn: 5,             // SOL
  slippageBps: 50,         // 0.5%
  priorityFee: 0.0001      // SOL
}

Response:
{
  success: true,
  txSignature: "5xyz...",
  executed: {
    amountIn: 5,
    amountOut: 50000000,   // tokens received
    pricePerToken: 0.0000001,
    fee: 0.000025
  }
}

// GET /api/v1/portfolio
// État du portfolio
{
  totalValueSOL: 150.5,
  positions: [
    {
      token: "BONK",
      amount: 50000000,
      valueSOL: 25.5,
      pnl: "+15%",
      entryPrice: 0.00000008
    }
  ],
  history: [...]
}

// POST /api/v1/trade/simulate
// Dry-run sans exécution
{ ... }

// WebSocket /ws/portfolio
// Updates temps réel
```

### Wallet API (interne, pas de port HTTP)
```typescript
// Interface TypeScript uniquement (pas d'API REST pour sécurité)

interface WalletService {
  // Lecture
  getPublicKey(): PublicKey;
  getBalance(): Promise<number>;
  getTokenBalances(): Promise<TokenBalance[]>;
  
  // Transactions
  signTransaction(tx: Transaction): Promise<Transaction>;
  signAndSend(tx: Transaction): Promise<string>;
  
  // Sécurité
  isLocked(): boolean;
  unlock(password: string): Promise<void>;
  lock(): void;
}
```

---

## 🔐 Sécurité - Gestion des Clés Privées

### Architecture de Sécurité
```
┌─────────────────────────────────────────────────────────────────┐
│                    SECURITY ARCHITECTURE                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                    APPLICATION LAYER                      │   │
│  │  Trading Engine │ AI Decision │ Social Analyzer          │   │
│  └──────────────────────────┬───────────────────────────────┘   │
│                             │                                    │
│                             │ Request signature                  │
│                             ▼                                    │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                    WALLET SERVICE                         │   │
│  │  - In-memory key (decrypted only when needed)            │   │
│  │  - Auto-lock after timeout                                │   │
│  │  - Transaction signing only                               │   │
│  └──────────────────────────┬───────────────────────────────┘   │
│                             │                                    │
│                             │ Encrypted at rest                  │
│                             ▼                                    │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                    ENCRYPTED STORAGE                      │   │
│  │  - AES-256-GCM encryption                                │   │
│  │  - Key derived from password (Argon2id)                  │   │
│  │  - Stored in: ~/.cst/wallet.enc                          │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Règles de Sécurité

#### 1. Stockage des Clés
```typescript
// ❌ JAMAIS
const privateKey = process.env.PRIVATE_KEY;  // Jamais en env var
const key = fs.readFileSync('key.json');     // Jamais en clair

// ✅ TOUJOURS
// Clé chiffrée avec AES-256-GCM
// Dérivation du mot de passe avec Argon2id
// Fichier avec permissions 600 (owner read/write only)
```

#### 2. Encryption Flow
```
Password ──► Argon2id ──► Derived Key ──► AES-256-GCM ──► Encrypted Keypair
                │               │
                │               └──► IV (random 12 bytes)
                │               └──► Auth Tag (16 bytes)
                │
                └──► Salt (32 bytes, stored with encrypted data)
```

#### 3. Runtime Security
```typescript
// Wallet auto-lock
const LOCK_TIMEOUT_MS = 5 * 60 * 1000; // 5 minutes

// Memory clearing
function clearSensitive(buffer: Buffer) {
  buffer.fill(0);  // Zero-fill before GC
}

// Transaction limits
const MAX_TRADE_SOL = 10;           // Max par trade
const MAX_DAILY_SOL = 50;           // Max par jour
const REQUIRE_CONFIRMATION = 5;     // SOL > 5 = confirmation requise
```

#### 4. Environment Variables
```bash
# .env (jamais commité!)

# ✅ OK - Clés API (peuvent être révoquées)
CLAUDE_API_KEY=sk-ant-...
HELIUS_API_KEY=...
TWITTER_BEARER_TOKEN=...

# ✅ OK - Config
DATABASE_URL=postgresql://...
REDIS_URL=redis://...
SOLANA_RPC_URL=https://...

# ❌ INTERDIT - Jamais de clés privées!
# WALLET_PRIVATE_KEY=...  # NEVER!
```

#### 5. Secrets Management (Production)
```yaml
# Options recommandées:
# 1. HashiCorp Vault
# 2. AWS Secrets Manager
# 3. Doppler
# 4. 1Password Connect

# Le wallet password est fourni au démarrage:
# - Interactivement (stdin)
# - Via secret manager
# - JAMAIS en variable d'environnement
```

### Checklist Sécurité

- [ ] Clé privée chiffrée au repos (AES-256-GCM)
- [ ] Dérivation de clé avec Argon2id (memory-hard)
- [ ] Auto-lock du wallet après inactivité
- [ ] Limites de transaction configurables
- [ ] Logs sans données sensibles
- [ ] Permissions fichiers restrictives (600)
- [ ] Pas de clé privée dans env vars
- [ ] Pas de clé privée dans logs/console
- [ ] Rate limiting sur les APIs
- [ ] HTTPS obligatoire (même en dev)

---

## 📁 Structure des Fichiers

```
crypto-smallcap-trader/
├── package.json              # Workspace root
├── turbo.json               # Turborepo config
├── .env.example             # Template variables
├── docker-compose.yml       # Dev stack (postgres, redis)
│
├── docs/
│   ├── ARCHITECTURE.md      # Ce fichier
│   └── API.md              # OpenAPI specs
│
├── packages/
│   ├── wallet/             # @cst/wallet
│   │   ├── src/
│   │   │   ├── index.ts
│   │   │   ├── encryption.ts
│   │   │   ├── keystore.ts
│   │   │   └── signer.ts
│   │   ├── package.json
│   │   └── tsconfig.json
│   │
│   ├── social-analyzer/    # @cst/social-analyzer
│   │   ├── src/
│   │   │   ├── index.ts
│   │   │   ├── server.ts
│   │   │   ├── scrapers/
│   │   │   │   ├── twitter.ts
│   │   │   │   ├── reddit.ts
│   │   │   │   └── telegram.ts
│   │   │   └── scoring.ts
│   │   ├── package.json
│   │   └── tsconfig.json
│   │
│   ├── ai-decision/        # @cst/ai-decision
│   │   ├── src/
│   │   │   ├── index.ts
│   │   │   ├── server.ts
│   │   │   ├── claude.ts
│   │   │   ├── prompts/
│   │   │   └── risk.ts
│   │   ├── package.json
│   │   └── tsconfig.json
│   │
│   ├── trading-engine/     # @cst/trading-engine
│   │   ├── src/
│   │   │   ├── index.ts
│   │   │   ├── server.ts
│   │   │   ├── jupiter.ts
│   │   │   ├── portfolio.ts
│   │   │   └── executor.ts
│   │   ├── package.json
│   │   └── tsconfig.json
│   │
│   └── frontend/           # @cst/frontend
│       ├── src/
│       │   ├── App.tsx
│       │   ├── main.tsx
│       │   ├── components/
│       │   ├── hooks/
│       │   └── stores/
│       ├── index.html
│       ├── package.json
│       ├── vite.config.ts
│       └── tailwind.config.js
│
└── scripts/
    ├── setup.sh            # Initial setup
    └── deploy.sh           # Deployment
```

---

## 🚀 Déploiement

### Développement
```bash
# Prérequis
docker-compose up -d  # PostgreSQL + Redis

# Installation
npm install

# Démarrage (tous les services)
npm run dev
```

### Production
```
┌─────────────────────────────────────────────────────────────────┐
│                    PRODUCTION DEPLOYMENT                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐           │
│  │   Frontend   │  │   Backend    │  │   Workers    │           │
│  │   (Vercel)   │  │   (Railway)  │  │  (Railway)   │           │
│  └──────────────┘  └──────────────┘  └──────────────┘           │
│         │                 │                 │                    │
│         └────────────────┼─────────────────┘                    │
│                          │                                       │
│                          ▼                                       │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │            Managed Services                               │   │
│  │  PostgreSQL (Supabase) │ Redis (Upstash) │ Helius RPC    │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 📊 Monitoring

| Métrique | Outil | Alerte |
|----------|-------|--------|
| Uptime services | UptimeRobot | < 99.9% |
| Latence trades | Prometheus | > 2s |
| Erreurs | Sentry | Any error |
| Wallet balance | Custom | < 1 SOL |
| Win rate | Grafana | < 50% (7d) |

---

*Document généré le 2026-02-01 - Version 1.0*
