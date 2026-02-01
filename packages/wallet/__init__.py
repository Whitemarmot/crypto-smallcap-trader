"""
EVM Wallet Package for crypto-smallcap-trader.
Supports Ethereum, BSC, Base, and Arbitrum.
"""

from .wallet import (
    EVMWallet,
    WalletInfo,
    WalletEncryption,
    create_wallet,
    create_wallet_with_mnemonic,
    import_wallet,
)

from .balance import (
    BalanceChecker,
    NativeBalance,
    TokenBalance,
    get_balance,
    get_token_balance,
    get_all_balances,
    POPULAR_TOKENS,
)

from .networks import (
    NetworkConfig,
    NETWORKS,
    TESTNETS,
    ALL_NETWORKS,
    get_network,
    get_chain_id,
    get_rpc_url,
    list_networks,
)

__all__ = [
    # Wallet
    "EVMWallet",
    "WalletInfo",
    "WalletEncryption",
    "create_wallet",
    "create_wallet_with_mnemonic",
    "import_wallet",
    # Balance
    "BalanceChecker",
    "NativeBalance",
    "TokenBalance",
    "get_balance",
    "get_token_balance",
    "get_all_balances",
    "POPULAR_TOKENS",
    # Networks
    "NetworkConfig",
    "NETWORKS",
    "TESTNETS",
    "ALL_NETWORKS",
    "get_network",
    "get_chain_id",
    "get_rpc_url",
    "list_networks",
]

__version__ = "0.1.0"
