"""
Tests for WalletManager.
"""
import os
import tempfile
import pytest
from eth_account import Account

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from manager import WalletManager, WalletNotFoundError, CryptoError
from database import init_db


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test_wallets.db")
        yield db_path


@pytest.fixture
def manager(temp_db):
    """Create a WalletManager with temporary database."""
    from database import Database
    db = Database(temp_db)
    db.init_db()
    return WalletManager(db=db)


@pytest.fixture
def sample_wallet():
    """Generate a sample wallet for testing."""
    account = Account.create()
    return {
        "name": "Test Wallet",
        "private_key": account.key.hex(),
        "address": account.address,
        "password": "super_secret_password_123!"
    }


class TestWalletEncryption:
    """Test encryption/decryption of private keys."""
    
    def test_encrypt_decrypt_roundtrip(self, manager, sample_wallet):
        """Test that encryption and decryption are reversible."""
        pk = sample_wallet["private_key"]
        password = sample_wallet["password"]
        
        encrypted, salt = manager._encrypt_private_key(pk, password)
        decrypted = manager._decrypt_private_key(encrypted, salt, password)
        
        assert decrypted == pk
    
    def test_wrong_password_fails(self, manager, sample_wallet):
        """Test that wrong password raises CryptoError."""
        pk = sample_wallet["private_key"]
        encrypted, salt = manager._encrypt_private_key(pk, "correct_password")
        
        with pytest.raises(CryptoError):
            manager._decrypt_private_key(encrypted, salt, "wrong_password")


class TestWalletManager:
    """Test WalletManager CRUD operations."""
    
    def test_add_wallet(self, manager, sample_wallet):
        """Test adding a new wallet."""
        result = manager.add_wallet(
            name=sample_wallet["name"],
            private_key=sample_wallet["private_key"],
            password=sample_wallet["password"]
        )
        
        assert result["name"] == sample_wallet["name"]
        assert result["address"] == sample_wallet["address"]
        assert "encrypted_private_key" not in result  # Should not expose
        assert result["is_active"] is True
    
    def test_add_duplicate_name_fails(self, manager, sample_wallet):
        """Test that duplicate wallet name raises ValueError."""
        manager.add_wallet(
            name=sample_wallet["name"],
            private_key=sample_wallet["private_key"],
            password=sample_wallet["password"]
        )
        
        # Try to add another wallet with same name
        new_account = Account.create()
        with pytest.raises(ValueError, match="already exists"):
            manager.add_wallet(
                name=sample_wallet["name"],
                private_key=new_account.key.hex(),
                password="another_password"
            )
    
    def test_list_wallets(self, manager, sample_wallet):
        """Test listing wallets."""
        # Add a wallet
        manager.add_wallet(
            name=sample_wallet["name"],
            private_key=sample_wallet["private_key"],
            password=sample_wallet["password"]
        )
        
        wallets = manager.list_wallets()
        
        assert len(wallets) == 1
        assert wallets[0]["name"] == sample_wallet["name"]
        assert "encrypted_private_key" not in wallets[0]
    
    def test_get_wallet(self, manager, sample_wallet):
        """Test getting a wallet by ID."""
        added = manager.add_wallet(
            name=sample_wallet["name"],
            private_key=sample_wallet["private_key"],
            password=sample_wallet["password"]
        )
        
        wallet = manager.get_wallet(added["id"])
        
        assert wallet["id"] == added["id"]
        assert wallet["name"] == sample_wallet["name"]
    
    def test_get_wallet_not_found(self, manager):
        """Test getting a non-existent wallet raises error."""
        with pytest.raises(WalletNotFoundError):
            manager.get_wallet(9999)
    
    def test_delete_wallet(self, manager, sample_wallet):
        """Test deleting a wallet."""
        added = manager.add_wallet(
            name=sample_wallet["name"],
            private_key=sample_wallet["private_key"],
            password=sample_wallet["password"]
        )
        
        result = manager.delete_wallet(added["id"])
        assert result is True
        
        # Verify it's gone
        with pytest.raises(WalletNotFoundError):
            manager.get_wallet(added["id"])
    
    def test_get_private_key(self, manager, sample_wallet):
        """Test retrieving decrypted private key."""
        added = manager.add_wallet(
            name=sample_wallet["name"],
            private_key=sample_wallet["private_key"],
            password=sample_wallet["password"]
        )
        
        pk = manager.get_private_key(added["id"], sample_wallet["password"])
        
        assert pk == sample_wallet["private_key"]
    
    def test_deactivate_wallet(self, manager, sample_wallet):
        """Test deactivating a wallet."""
        added = manager.add_wallet(
            name=sample_wallet["name"],
            private_key=sample_wallet["private_key"],
            password=sample_wallet["password"]
        )
        
        result = manager.deactivate_wallet(added["id"])
        
        assert result["is_active"] is False
        
        # Should still appear in list
        all_wallets = manager.list_wallets(active_only=False)
        assert len(all_wallets) == 1
        
        # But not in active-only list
        active_wallets = manager.list_wallets(active_only=True)
        assert len(active_wallets) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
