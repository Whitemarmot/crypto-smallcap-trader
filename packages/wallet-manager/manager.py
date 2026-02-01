"""
Wallet Manager - Core business logic for multi-wallet management.
"""
import os
import base64
import hashlib
import secrets
from datetime import datetime
from typing import Optional

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from eth_account import Account
from web3 import Web3

try:
    from .database import Database, init_db
    from .models import Wallet, Balance
except ImportError:
    from database import Database, init_db
    from models import Wallet, Balance


class CryptoError(Exception):
    """Exception raised for cryptographic errors."""
    pass


class WalletNotFoundError(Exception):
    """Exception raised when wallet is not found."""
    pass


class WalletManager:
    """
    Multi-wallet manager with encrypted private key storage.
    
    Supports:
    - Adding wallets with AES-256-GCM encrypted private keys
    - Listing wallets (without sensitive data)
    - Getting wallet details
    - Deleting wallets
    - Fetching live balances from blockchain
    """
    
    # RPC endpoints for different networks
    NETWORK_RPCS = {
        "ethereum": os.environ.get("ETH_RPC_URL", "https://eth.llamarpc.com"),
        "polygon": os.environ.get("POLYGON_RPC_URL", "https://polygon.llamarpc.com"),
        "arbitrum": os.environ.get("ARBITRUM_RPC_URL", "https://arbitrum.llamarpc.com"),
        "base": os.environ.get("BASE_RPC_URL", "https://base.llamarpc.com"),
        "optimism": os.environ.get("OPTIMISM_RPC_URL", "https://optimism.llamarpc.com"),
    }
    
    # Native token symbols per network
    NATIVE_TOKENS = {
        "ethereum": "ETH",
        "polygon": "MATIC",
        "arbitrum": "ETH",
        "base": "ETH",
        "optimism": "ETH",
    }
    
    def __init__(self, db: Database = None, db_path: str = None):
        """
        Initialize wallet manager.
        
        Args:
            db: Existing Database instance
            db_path: Path to database file (creates new Database if db not provided)
        """
        if db:
            self.db = db
        else:
            self.db = init_db(db_path)
    
    def _derive_key(self, password: str, salt: bytes) -> bytes:
        """
        Derive a 256-bit key from password using PBKDF2.
        
        Args:
            password: User password
            salt: Random salt for key derivation
            
        Returns:
            32-byte derived key
        """
        return hashlib.pbkdf2_hmac(
            'sha256',
            password.encode('utf-8'),
            salt,
            iterations=100000,
            dklen=32
        )
    
    def _encrypt_private_key(self, private_key: str, password: str) -> tuple[str, str]:
        """
        Encrypt a private key using AES-256-GCM.
        
        Args:
            private_key: The private key to encrypt
            password: Password for encryption
            
        Returns:
            Tuple of (encrypted_data_base64, salt_hex)
        """
        # Generate random salt and nonce
        salt = secrets.token_bytes(16)
        nonce = secrets.token_bytes(12)
        
        # Derive key from password
        key = self._derive_key(password, salt)
        
        # Encrypt using AES-GCM
        aesgcm = AESGCM(key)
        ciphertext = aesgcm.encrypt(nonce, private_key.encode('utf-8'), None)
        
        # Combine nonce + ciphertext and encode
        encrypted_data = base64.b64encode(nonce + ciphertext).decode('utf-8')
        
        return encrypted_data, salt.hex()
    
    def _decrypt_private_key(self, encrypted_data: str, salt_hex: str, password: str) -> str:
        """
        Decrypt a private key using AES-256-GCM.
        
        Args:
            encrypted_data: Base64-encoded nonce + ciphertext
            salt_hex: Hex-encoded salt
            password: Password for decryption
            
        Returns:
            Decrypted private key
            
        Raises:
            CryptoError: If decryption fails
        """
        try:
            salt = bytes.fromhex(salt_hex)
            data = base64.b64decode(encrypted_data)
            
            # Extract nonce and ciphertext
            nonce = data[:12]
            ciphertext = data[12:]
            
            # Derive key and decrypt
            key = self._derive_key(password, salt)
            aesgcm = AESGCM(key)
            
            plaintext = aesgcm.decrypt(nonce, ciphertext, None)
            return plaintext.decode('utf-8')
        except Exception as e:
            raise CryptoError(f"Failed to decrypt private key: {e}")
    
    def _get_address_from_private_key(self, private_key: str) -> str:
        """
        Derive Ethereum address from private key.
        
        Args:
            private_key: Hex-encoded private key (with or without 0x prefix)
            
        Returns:
            Checksummed Ethereum address
        """
        if not private_key.startswith('0x'):
            private_key = '0x' + private_key
        account = Account.from_key(private_key)
        return account.address
    
    def add_wallet(self, name: str, private_key: str, password: str) -> dict:
        """
        Add a new wallet with encrypted private key.
        
        Args:
            name: Friendly name for the wallet
            private_key: Hex-encoded private key
            password: Password to encrypt the private key
            
        Returns:
            Dictionary with wallet info (without sensitive data)
            
        Raises:
            ValueError: If wallet with same name or address already exists
        """
        # Derive address from private key
        address = self._get_address_from_private_key(private_key)
        
        # Encrypt the private key
        encrypted_pk, salt = self._encrypt_private_key(private_key, password)
        
        with self.db.get_session() as session:
            # Check for existing wallet with same name or address
            existing = session.query(Wallet).filter(
                (Wallet.name == name) | (Wallet.address == address)
            ).first()
            
            if existing:
                if existing.name == name:
                    raise ValueError(f"Wallet with name '{name}' already exists")
                else:
                    raise ValueError(f"Wallet with address '{address}' already exists")
            
            # Create new wallet
            wallet = Wallet(
                name=name,
                address=address,
                encrypted_private_key=encrypted_pk,
                salt=salt,
                is_active=True
            )
            
            session.add(wallet)
            session.flush()  # Get the ID
            
            return wallet.to_dict(include_sensitive=False)
    
    def list_wallets(self, active_only: bool = False) -> list[dict]:
        """
        List all wallets without sensitive data.
        
        Args:
            active_only: If True, only return active wallets
            
        Returns:
            List of wallet dictionaries (without private keys)
        """
        with self.db.get_session() as session:
            query = session.query(Wallet)
            if active_only:
                query = query.filter(Wallet.is_active == True)
            
            wallets = query.order_by(Wallet.created_at.desc()).all()
            return [w.to_dict(include_sensitive=False) for w in wallets]
    
    def get_wallet(self, wallet_id: int) -> dict:
        """
        Get wallet details by ID.
        
        Args:
            wallet_id: Wallet ID
            
        Returns:
            Wallet dictionary (without sensitive data)
            
        Raises:
            WalletNotFoundError: If wallet not found
        """
        with self.db.get_session() as session:
            wallet = session.query(Wallet).filter(Wallet.id == wallet_id).first()
            
            if not wallet:
                raise WalletNotFoundError(f"Wallet with ID {wallet_id} not found")
            
            return wallet.to_dict(include_sensitive=False)
    
    def get_wallet_by_name(self, name: str) -> dict:
        """
        Get wallet details by name.
        
        Args:
            name: Wallet name
            
        Returns:
            Wallet dictionary (without sensitive data)
            
        Raises:
            WalletNotFoundError: If wallet not found
        """
        with self.db.get_session() as session:
            wallet = session.query(Wallet).filter(Wallet.name == name).first()
            
            if not wallet:
                raise WalletNotFoundError(f"Wallet with name '{name}' not found")
            
            return wallet.to_dict(include_sensitive=False)
    
    def delete_wallet(self, wallet_id: int) -> bool:
        """
        Delete a wallet by ID.
        
        Args:
            wallet_id: Wallet ID
            
        Returns:
            True if deleted successfully
            
        Raises:
            WalletNotFoundError: If wallet not found
        """
        with self.db.get_session() as session:
            wallet = session.query(Wallet).filter(Wallet.id == wallet_id).first()
            
            if not wallet:
                raise WalletNotFoundError(f"Wallet with ID {wallet_id} not found")
            
            session.delete(wallet)
            return True
    
    def deactivate_wallet(self, wallet_id: int) -> dict:
        """
        Deactivate a wallet (soft delete).
        
        Args:
            wallet_id: Wallet ID
            
        Returns:
            Updated wallet dictionary
        """
        with self.db.get_session() as session:
            wallet = session.query(Wallet).filter(Wallet.id == wallet_id).first()
            
            if not wallet:
                raise WalletNotFoundError(f"Wallet with ID {wallet_id} not found")
            
            wallet.is_active = False
            return wallet.to_dict(include_sensitive=False)
    
    def get_private_key(self, wallet_id: int, password: str) -> str:
        """
        Decrypt and return the private key for a wallet.
        
        Args:
            wallet_id: Wallet ID
            password: Password to decrypt the key
            
        Returns:
            Decrypted private key
            
        Raises:
            WalletNotFoundError: If wallet not found
            CryptoError: If decryption fails
        """
        with self.db.get_session() as session:
            wallet = session.query(Wallet).filter(Wallet.id == wallet_id).first()
            
            if not wallet:
                raise WalletNotFoundError(f"Wallet with ID {wallet_id} not found")
            
            return self._decrypt_private_key(
                wallet.encrypted_private_key,
                wallet.salt,
                password
            )
    
    def get_balances(self, wallet_id: int, network: str = "ethereum") -> list[dict]:
        """
        Fetch live balances for a wallet from the blockchain.
        
        Args:
            wallet_id: Wallet ID
            network: Blockchain network (ethereum, polygon, etc.)
            
        Returns:
            List of balance dictionaries
            
        Raises:
            WalletNotFoundError: If wallet not found
            ValueError: If network not supported
        """
        if network not in self.NETWORK_RPCS:
            raise ValueError(f"Unsupported network: {network}. Supported: {list(self.NETWORK_RPCS.keys())}")
        
        with self.db.get_session() as session:
            wallet = session.query(Wallet).filter(Wallet.id == wallet_id).first()
            
            if not wallet:
                raise WalletNotFoundError(f"Wallet with ID {wallet_id} not found")
            
            address = wallet.address
            
            # Connect to network
            w3 = Web3(Web3.HTTPProvider(self.NETWORK_RPCS[network]))
            
            balances = []
            
            # Get native token balance
            try:
                native_balance_wei = w3.eth.get_balance(address)
                native_balance = float(w3.from_wei(native_balance_wei, 'ether'))
                
                native_token = self.NATIVE_TOKENS[network]
                
                # Update or create balance record
                balance_record = session.query(Balance).filter(
                    Balance.wallet_id == wallet_id,
                    Balance.token == native_token,
                    Balance.network == network
                ).first()
                
                if balance_record:
                    balance_record.amount = native_balance
                    balance_record.updated_at = datetime.utcnow()
                else:
                    balance_record = Balance(
                        wallet_id=wallet_id,
                        token=native_token,
                        token_address=None,
                        amount=native_balance,
                        usd_value=0.0,  # TODO: Fetch price
                        network=network
                    )
                    session.add(balance_record)
                
                session.flush()
                balances.append(balance_record.to_dict())
                
            except Exception as e:
                # Log error but continue
                print(f"Error fetching native balance: {e}")
            
            return balances
    
    def get_cached_balances(self, wallet_id: int, network: str = None) -> list[dict]:
        """
        Get cached balances from database (no blockchain call).
        
        Args:
            wallet_id: Wallet ID
            network: Optional network filter
            
        Returns:
            List of cached balance dictionaries
        """
        with self.db.get_session() as session:
            query = session.query(Balance).filter(Balance.wallet_id == wallet_id)
            
            if network:
                query = query.filter(Balance.network == network)
            
            balances = query.all()
            return [b.to_dict() for b in balances]
