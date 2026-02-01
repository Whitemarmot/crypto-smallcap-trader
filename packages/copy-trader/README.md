# 🐋 Copy Trading Module

Copy-trading system for following whales and influencers on Ethereum and Base networks.

## Features

- **Whale Tracking**: Monitor known whale wallets on-chain
- **Transaction Detection**: Detect swaps, transfers, and trades via Etherscan/Basescan APIs
- **Portfolio Analysis**: Analyze whale holdings and activity
- **Alert System**: Get notified when whales make significant moves
- **Copy Trading**: Simulate or execute trades following whale activity

## Installation

```bash
pip install -r requirements.txt
```

## Quick Start

### Get Known Whales

```python
from copy_trader import get_known_whales, KNOWN_WHALES_ETHEREUM, KNOWN_WHALES_BASE

# Get all known whales for a network
whales = get_known_whales("ethereum")
for address, info in whales.items():
    print(f"{info['name']}: {address}")
```

### Fetch Whale Transactions

```python
from copy_trader import get_whale_transactions_sync

# Get recent transactions (sync version for Streamlit)
transactions = get_whale_transactions_sync(
    wallet_address="0xd8da6bf26964af9d7eed9e03e53415d37aa96045",  # vitalik.eth
    network="ethereum",
    limit=50,
    api_key="YOUR_ETHERSCAN_API_KEY"  # Optional but recommended
)

for tx in transactions:
    print(f"{tx['token_symbol']}: {tx['value']} - {'SWAP' if tx['is_swap'] else 'TRANSFER'}")
```

### Analyze Whale Portfolio

```python
from copy_trader import analyze_whale_portfolio_sync

portfolio = analyze_whale_portfolio_sync(
    wallet_address="0xd8da6bf26964af9d7eed9e03e53415d37aa96045",
    network="ethereum",
    api_key="YOUR_ETHERSCAN_API_KEY"
)

print(f"Native balance: {portfolio['native_balance']} ETH")
print(f"Tokens held: {len(portfolio['holdings'])}")
for holding in portfolio['holdings']:
    print(f"  {holding['symbol']}: {holding['balance']}")
```

### Check for Alerts

```python
from copy_trader import check_for_alerts_sync

alerts = check_for_alerts_sync(
    wallet_address="0x28c6c06298d514db089934071355e5743bf21d60",  # Binance
    network="ethereum",
    min_amount_usd=10000,
    lookback_minutes=60,
    api_key="YOUR_ETHERSCAN_API_KEY"
)

for alert in alerts:
    print(alert['message'])
```

## Async Usage

For better performance, use the async versions:

```python
import asyncio
from copy_trader import get_whale_transactions, analyze_whale_portfolio

async def main():
    txs = await get_whale_transactions(
        "0xd8da6bf26964af9d7eed9e03e53415d37aa96045",
        "ethereum",
        limit=50
    )
    print(f"Found {len(txs)} transactions")

asyncio.run(main())
```

## Known Whales

### Ethereum (13 addresses)
- **Exchanges**: Binance, Coinbase hot/cold wallets
- **Market Makers**: Jump Trading, Wintermute, GSR Markets
- **Smart Money**: vitalik.eth
- **DeFi Whales**: Major Aave/Compound depositors

### Base (7 addresses)
- **Foundation**: Base Foundation treasury
- **Infrastructure**: Base Bridge, WETH contract
- **DeFi**: Aerodrome Finance
- **Whales**: Active traders identified from on-chain analysis

## API Rate Limits

- Etherscan free tier: 5 calls/second
- The module includes built-in rate limiting (4.5 req/sec)
- Results are cached for 5 minutes to minimize API calls

## Configuration

Set your API key via environment variable:
```bash
export ETHERSCAN_API_KEY=your_key_here
```

Or pass it directly to functions:
```python
get_whale_transactions_sync(address, network, api_key="your_key")
```

## Streamlit Integration

The module integrates with the Streamlit frontend via `pages/7_whales.py`:

1. **Known Whales Tab**: Browse and track known whale addresses
2. **Tracking Tab**: Manage your watchlist
3. **Transactions Tab**: View recent activity from tracked whales
4. **Alerts Tab**: Check for significant moves

## Data Classes

- `WhaleTransaction`: Single transaction from a whale
- `WhalePortfolio`: Portfolio snapshot with holdings
- `WhaleAlert`: Alert for significant activity
- `TokenHolding`: Token balance in a portfolio

## Cache

Results are cached in `.cache/` directory for 5 minutes.
Clear cache programmatically:

```python
from copy_trader.whale_api import _cache
_cache.clear()
```

## License

MIT
