# Crypto Smallcap Trader 🚀

AI-powered trading agent for smallcap cryptocurrencies on EVM chains.

## Features
- 💰 Auto-managed EVM wallet (ETH, BSC, Base, Arbitrum)
- 📊 Social media sentiment analysis (Twitter, Reddit, Telegram)
- 🧠 AI-driven buy/sell decisions
- 🎨 Dashboard UI for monitoring

## Stack
- **Backend**: Python 3.11+ / FastAPI
- **Blockchain**: EVM (web3.py, eth-account)
- **DEX**: Uniswap V3, PancakeSwap, 1inch API
- **Frontend**: Streamlit (MVP)
- **AI**: Claude API pour sentiment & decisions
- **Database**: SQLite

## Supported Chains
- Ethereum Mainnet
- BSC (Binance Smart Chain)
- Base
- Arbitrum
- Polygon

## Structure
```
packages/
├── wallet/          # Gestion wallet EVM
├── trading-engine/  # Exécution trades sur DEX
├── social-analyzer/ # Scraping & sentiment analysis
├── ai-decision/     # Moteur de décision IA
└── frontend/        # Dashboard web
```

## Status
🚧 Under development
