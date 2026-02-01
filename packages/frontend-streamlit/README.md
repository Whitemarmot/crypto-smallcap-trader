# 🚀 SmallCap Trader - Frontend Streamlit

Dashboard interactif pour le monitoring et contrôle du bot de trading crypto.

## 📁 Structure

```
frontend-streamlit/
├── app.py                    # Dashboard principal
├── pages/
│   ├── 1_wallet.py          # Vue wallet & portfolio
│   ├── 2_trades.py          # Historique des trades
│   └── 3_signals.py         # Signaux sociaux
├── requirements.txt          # Dépendances Python
└── README.md
```

## 🛠️ Installation

```bash
cd packages/frontend-streamlit
pip install -r requirements.txt
```

## 🚀 Lancement

```bash
streamlit run app.py
```

Le dashboard sera accessible sur `http://localhost:8501`

## 📊 Pages

### 🏠 Dashboard Principal (`app.py`)
- Vue d'ensemble du portfolio
- Métriques clés (valeur, P&L, win rate)
- Graphique de performance
- Positions actives
- Signaux récents

### 💼 Wallet (`pages/1_wallet.py`)
- Balance et holdings
- Allocation du portfolio
- Actions (dépôt, retrait, swap)
- Historique des transactions

### 📈 Trades (`pages/2_trades.py`)
- Historique complet des trades
- Performance cumulative
- Stats par token
- Filtres avancés
- Export CSV/PDF

### 📡 Signaux (`pages/3_signals.py`)
- Feed de signaux en temps réel
- Sources: Twitter, Telegram, Discord
- Analyse de sentiment
- Top KOLs performance
- Configuration des alertes

## ⚙️ Configuration

Variables d'environnement (optionnel):
- `API_URL`: URL de l'API backend
- `REFRESH_INTERVAL`: Intervalle de rafraîchissement (secondes)

## 🎨 Personnalisation

Le thème Streamlit peut être configuré dans `.streamlit/config.toml`:

```toml
[theme]
primaryColor = "#667eea"
backgroundColor = "#0e1117"
secondaryBackgroundColor = "#1e1e2e"
textColor = "#fafafa"
```
