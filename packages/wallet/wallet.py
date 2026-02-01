"""
EVM Wallet generation and management.
Supports secure private key encryption.
"""

import os
import json
import secrets
from dataclasses import dataclass
from typing import Optional, Tuple

from eth_account import Account
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64


@dataclass
class WalletInfo:
    """Wallet information container."""
    address: str
    private_key_encrypted: Optional[bytes] = None
    private_key_plain: Optional[str] = None  # Only populated if not encrypted


class WalletEncryption:
    """Handle private key encryption/decryption using Fernet (AES-128-CBC)."""
    
    SALT_SIZE = 16
    ITERATIONS = 480000  # OWASP recommendation for PBKDF2-SHA256
    
    @classmethod
    def _derive_key(cls, password: str, salt: bytes) -> bytes:
        """Derive encryption key from password using PBKDF2."""
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=cls.ITERATIONS,
        )
        return base64.urlsafe_b64encode(kdf.derive(password.encode()))
    
    @classmethod
    def encrypt(cls, private_key: str, password: str) -> bytes:
        """
        Encrypt a private key with a password.
        
        Args:
            private_key: Hex string of private key (with or without 0x prefix)
            password: Password for encryption
            
        Returns:
            Encrypted data as bytes (salt + encrypted_key)
        """
        salt = secrets.token_bytes(cls.SALT_SIZE)
        key = cls._derive_key(password, salt)
        fernet = Fernet(key)
        
        # Normalize private key (remove 0x prefix if present)
        pk_clean = private_key.lower().removeprefix("0x")
        encrypted = fernet.encrypt(pk_clean.encode())
        
        # Prepend salt to encrypted data
        return salt + encrypted
    
    @classmethod
    def decrypt(cls, encrypted_data: bytes, password: str) -> str:
        """
        Decrypt an encrypted private key.
        
        Args:
            encrypted_data: Encrypted data (salt + encrypted_key)
            password: Password used for encryption
            
        Returns:
            Private key as hex string (without 0x prefix)
            
        Raises:
            ValueError: If decryption fails (wrong password)
        """
        salt = encrypted_data[:cls.SALT_SIZE]
        encrypted_key = encrypted_data[cls.SALT_SIZE:]
        
        key = cls._derive_key(password, salt)
        fernet = Fernet(key)
        
        try:
            decrypted = fernet.decrypt(encrypted_key)
            return decrypted.decode()
        except Exception as e:
            raise ValueError("Decryption failed. Wrong password?") from e


class EVMWallet:
    """EVM Wallet manager for generating and managing wallets."""
    
    def __init__(self):
        # Enable unaudited HD wallet features
        Account.enable_unaudited_hdwallet_features()
    
    def generate(self, password: Optional[str] = None) -> WalletInfo:
        """
        Generate a new EVM wallet.
        
        Args:
            password: Optional password to encrypt the private key.
                     If None, private key is returned in plain text.
                     
        Returns:
            WalletInfo with address and private key (encrypted or plain)
        """
        # Generate random private key
        account = Account.create()
        
        if password:
            encrypted = WalletEncryption.encrypt(account.key.hex(), password)
            return WalletInfo(
                address=account.address,
                private_key_encrypted=encrypted,
            )
        else:
            return WalletInfo(
                address=account.address,
                private_key_plain=account.key.hex(),
            )
    
    def generate_from_mnemonic(
        self,
        mnemonic: Optional[str] = None,
        password: Optional[str] = None,
        account_index: int = 0,
    ) -> Tuple[WalletInfo, str]:
        """
        Generate wallet from mnemonic (BIP-39).
        
        Args:
            mnemonic: Optional existing mnemonic. If None, generates new one.
            password: Optional password to encrypt the private key.
            account_index: Account index for derivation path (default 0)
            
        Returns:
            Tuple of (WalletInfo, mnemonic)
        """
        if mnemonic is None:
            mnemonic = Account.create_with_mnemonic()[1]
        
        # Standard Ethereum derivation path
        derivation_path = f"m/44'/60'/0'/0/{account_index}"
        account = Account.from_mnemonic(mnemonic, account_path=derivation_path)
        
        if password:
            encrypted = WalletEncryption.encrypt(account.key.hex(), password)
            wallet = WalletInfo(
                address=account.address,
                private_key_encrypted=encrypted,
            )
        else:
            wallet = WalletInfo(
                address=account.address,
                private_key_plain=account.key.hex(),
            )
        
        return wallet, mnemonic
    
    def from_private_key(
        self,
        private_key: str,
        password: Optional[str] = None,
    ) -> WalletInfo:
        """
        Import wallet from existing private key.
        
        Args:
            private_key: Hex string of private key (with or without 0x prefix)
            password: Optional password to encrypt the private key.
            
        Returns:
            WalletInfo with address and private key
        """
        # Normalize and validate private key
        pk_clean = private_key.lower().removeprefix("0x")
        if len(pk_clean) != 64:
            raise ValueError("Invalid private key length")
        
        account = Account.from_key(private_key)
        
        if password:
            encrypted = WalletEncryption.encrypt(private_key, password)
            return WalletInfo(
                address=account.address,
                private_key_encrypted=encrypted,
            )
        else:
            return WalletInfo(
                address=account.address,
                private_key_plain=pk_clean,
            )
    
    def decrypt_private_key(
        self,
        wallet: WalletInfo,
        password: str,
    ) -> str:
        """
        Decrypt the private key from an encrypted wallet.
        
        Args:
            wallet: WalletInfo with encrypted private key
            password: Password used for encryption
            
        Returns:
            Decrypted private key as hex string
        """
        if wallet.private_key_encrypted is None:
            raise ValueError("Wallet has no encrypted private key")
        
        return WalletEncryption.decrypt(wallet.private_key_encrypted, password)
    
    def save_wallet(
        self,
        wallet: WalletInfo,
        filepath: str,
    ) -> None:
        """
        Save wallet to a JSON file.
        
        Args:
            wallet: WalletInfo to save
            filepath: Path to save the wallet
        """
        data = {
            "address": wallet.address,
        }
        
        if wallet.private_key_encrypted:
            # Store encrypted key as base64 for JSON compatibility
            data["private_key_encrypted"] = base64.b64encode(
                wallet.private_key_encrypted
            ).decode()
        
        # Never save plain text private keys to file
        if wallet.private_key_plain:
            raise ValueError(
                "Cannot save unencrypted wallet. Provide a password to encrypt first."
            )
        
        with open(filepath, "w") as f:
            json.dump(data, f, indent=2)
    
    def load_wallet(self, filepath: str) -> WalletInfo:
        """
        Load wallet from a JSON file.
        
        Args:
            filepath: Path to the wallet file
            
        Returns:
            WalletInfo loaded from file
        """
        with open(filepath) as f:
            data = json.load(f)
        
        encrypted = None
        if "private_key_encrypted" in data:
            encrypted = base64.b64decode(data["private_key_encrypted"])
        
        return WalletInfo(
            address=data["address"],
            private_key_encrypted=encrypted,
        )


# Convenience functions
def create_wallet(password: Optional[str] = None) -> WalletInfo:
    """Create a new EVM wallet."""
    return EVMWallet().generate(password)


def create_wallet_with_mnemonic(
    password: Optional[str] = None,
) -> Tuple[WalletInfo, str]:
    """Create a new EVM wallet with mnemonic backup."""
    return EVMWallet().generate_from_mnemonic(password=password)


def import_wallet(private_key: str, password: Optional[str] = None) -> WalletInfo:
    """Import wallet from private key."""
    return EVMWallet().from_private_key(private_key, password)
