"""
Wallet Manager - Multi-wallet management with encrypted key storage.
"""
try:
    from .database import Database, init_db, get_database
    from .manager import WalletManager, CryptoError, WalletNotFoundError
    from .models import Wallet, Balance, Base
except ImportError:
    from database import Database, init_db, get_database
    from manager import WalletManager, CryptoError, WalletNotFoundError
    from models import Wallet, Balance, Base

__all__ = [
    "WalletManager",
    "Database",
    "init_db",
    "get_database",
    "Wallet",
    "Balance",
    "Base",
    "CryptoError",
    "WalletNotFoundError",
]

__version__ = "0.1.0"
