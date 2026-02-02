"""
🔐 Wallet Keys - Encrypted private key storage
Uses AES encryption (Fernet) with password-derived key
"""

import os
import json
import base64
import hashlib
from typing import Optional
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

DATA_DIR = os.path.join(os.path.dirname(__file__), '..', 'data')
KEYS_FILE = os.path.join(DATA_DIR, 'wallet_keys.enc')
SALT_FILE = os.path.join(DATA_DIR, '.salt')

# Master password from environment
MASTER_PASSWORD = os.environ.get('WALLET_MASTER_PASSWORD', '')


def _get_salt() -> bytes:
    """Get or create salt for key derivation"""
    if os.path.exists(SALT_FILE):
        with open(SALT_FILE, 'rb') as f:
            return f.read()
    else:
        salt = os.urandom(16)
        os.makedirs(os.path.dirname(SALT_FILE), exist_ok=True)
        with open(SALT_FILE, 'wb') as f:
            f.write(salt)
        return salt


def _derive_key(password: str) -> bytes:
    """Derive encryption key from password using PBKDF2"""
    salt = _get_salt()
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=480000,
    )
    key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
    return key


def _get_fernet() -> Optional[Fernet]:
    """Get Fernet instance with derived key"""
    if not MASTER_PASSWORD:
        print("⚠️ WALLET_MASTER_PASSWORD not set")
        return None
    
    key = _derive_key(MASTER_PASSWORD)
    return Fernet(key)


def _load_keys() -> dict:
    """Load encrypted keys file"""
    if not os.path.exists(KEYS_FILE):
        return {}
    
    fernet = _get_fernet()
    if not fernet:
        return {}
    
    try:
        with open(KEYS_FILE, 'rb') as f:
            encrypted = f.read()
        decrypted = fernet.decrypt(encrypted)
        return json.loads(decrypted.decode())
    except Exception as e:
        print(f"❌ Failed to decrypt keys: {e}")
        return {}


def _save_keys(keys: dict):
    """Save encrypted keys file"""
    fernet = _get_fernet()
    if not fernet:
        raise ValueError("WALLET_MASTER_PASSWORD not set")
    
    os.makedirs(os.path.dirname(KEYS_FILE), exist_ok=True)
    
    data = json.dumps(keys).encode()
    encrypted = fernet.encrypt(data)
    
    with open(KEYS_FILE, 'wb') as f:
        f.write(encrypted)


def store_private_key(wallet_address: str, private_key: str) -> bool:
    """
    Store a private key for a wallet address (encrypted)
    
    Args:
        wallet_address: Ethereum address (0x...)
        private_key: Private key (with or without 0x prefix)
    
    Returns:
        True if stored successfully
    """
    if not MASTER_PASSWORD:
        print("❌ Set WALLET_MASTER_PASSWORD environment variable first")
        return False
    
    # Normalize
    wallet_address = wallet_address.lower()
    if private_key.startswith('0x'):
        private_key = private_key[2:]
    
    # Validate
    if len(private_key) != 64:
        print("❌ Invalid private key length")
        return False
    
    keys = _load_keys()
    keys[wallet_address] = private_key
    _save_keys(keys)
    
    print(f"✅ Private key stored for {wallet_address[:10]}...")
    return True


def get_private_key(wallet_address: str) -> Optional[str]:
    """
    Get private key for a wallet address
    
    Args:
        wallet_address: Ethereum address
    
    Returns:
        Private key (without 0x prefix) or None
    """
    wallet_address = wallet_address.lower()
    keys = _load_keys()
    return keys.get(wallet_address)


def has_private_key(wallet_address: str) -> bool:
    """Check if we have the private key for a wallet"""
    wallet_address = wallet_address.lower()
    keys = _load_keys()
    return wallet_address in keys


def delete_private_key(wallet_address: str) -> bool:
    """Delete a stored private key"""
    wallet_address = wallet_address.lower()
    keys = _load_keys()
    
    if wallet_address in keys:
        del keys[wallet_address]
        _save_keys(keys)
        print(f"✅ Private key deleted for {wallet_address[:10]}...")
        return True
    
    return False


def list_stored_wallets() -> list:
    """List wallet addresses with stored keys"""
    keys = _load_keys()
    return list(keys.keys())


if __name__ == '__main__':
    # Test
    print("🔐 Wallet Keys Test")
    
    if not MASTER_PASSWORD:
        print("Set WALLET_MASTER_PASSWORD to test")
    else:
        # Test store/retrieve
        test_addr = "0x1234567890abcdef1234567890abcdef12345678"
        test_key = "abcd" * 16  # 64 hex chars
        
        store_private_key(test_addr, test_key)
        retrieved = get_private_key(test_addr)
        
        assert retrieved == test_key, "Key mismatch!"
        print("✅ Store/retrieve test passed")
        
        delete_private_key(test_addr)
        print("✅ Cleanup done")
