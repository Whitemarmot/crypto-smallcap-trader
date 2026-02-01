# Wallet Manager

Multi-wallet management system with AES-256-GCM encrypted private key storage.

## Features

- 🔐 **Secure Storage**: Private keys encrypted with AES-256-GCM
- 🔑 **PBKDF2 Key Derivation**: 100,000 iterations for password-based encryption
- 💼 **Multi-Wallet Support**: Manage multiple wallets with unique names
- ⛓️ **Multi-Network**: Support for Ethereum, Polygon, Arbitrum, Base, Optimism
- 📊 **Balance Tracking**: Fetch and cache live balances from blockchain

## Installation

```bash
pip install -e .
```

## Quick Start

```python
from wallet_manager import WalletManager, init_db

# Initialize database
init_db()

# Create manager
manager = WalletManager()

# Add a wallet (private key will be encrypted)
wallet = manager.add_wallet(
    name="Trading Wallet",
    private_key="0x...",  # Your private key
    password="your_secure_password"
)

# List wallets (no sensitive data exposed)
wallets = manager.list_wallets()

# Get live balances
balances = manager.get_balances(wallet["id"], network="ethereum")

# Retrieve private key when needed (requires password)
pk = manager.get_private_key(wallet["id"], "your_secure_password")
```

## Security Notes

- Private keys are **never stored in plaintext**
- Each wallet uses a unique salt for key derivation
- AES-256-GCM provides authenticated encryption
- Wrong password will fail decryption (no silent failures)

## API Reference

### WalletManager

| Method | Description |
|--------|-------------|
| `add_wallet(name, private_key, password)` | Add wallet with encrypted key |
| `list_wallets(active_only=False)` | List all wallets (no keys) |
| `get_wallet(id)` | Get wallet details |
| `get_wallet_by_name(name)` | Get wallet by name |
| `delete_wallet(id)` | Permanently delete wallet |
| `deactivate_wallet(id)` | Soft delete (set inactive) |
| `get_private_key(id, password)` | Decrypt and return private key |
| `get_balances(id, network)` | Fetch live blockchain balances |
| `get_cached_balances(id, network)` | Get stored balances |

## Supported Networks

- Ethereum
- Polygon
- Arbitrum
- Base
- Optimism

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `WALLET_DB_PATH` | SQLite database path | `data/wallets.db` |
| `ETH_RPC_URL` | Ethereum RPC endpoint | Public RPC |
| `POLYGON_RPC_URL` | Polygon RPC endpoint | Public RPC |
| `ARBITRUM_RPC_URL` | Arbitrum RPC endpoint | Public RPC |
| `BASE_RPC_URL` | Base RPC endpoint | Public RPC |
| `OPTIMISM_RPC_URL` | Optimism RPC endpoint | Public RPC |

## Testing

```bash
pip install -e ".[dev]"
pytest -v
```
