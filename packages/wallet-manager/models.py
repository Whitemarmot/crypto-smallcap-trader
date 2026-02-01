"""
SQLAlchemy models for wallet management.
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship, declarative_base

Base = declarative_base()


class Wallet(Base):
    """Wallet model storing encrypted private keys."""
    
    __tablename__ = "wallets"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False, unique=True)
    address = Column(String(255), nullable=False, unique=True)
    encrypted_private_key = Column(Text, nullable=False)
    salt = Column(String(64), nullable=False)  # Salt for key derivation
    created_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)
    
    # Relationship to balances
    balances = relationship("Balance", back_populates="wallet", cascade="all, delete-orphan")
    
    def to_dict(self, include_sensitive: bool = False) -> dict:
        """Convert wallet to dictionary, optionally excluding sensitive data."""
        data = {
            "id": self.id,
            "name": self.name,
            "address": self.address,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "is_active": self.is_active,
        }
        if include_sensitive:
            data["encrypted_private_key"] = self.encrypted_private_key
            data["salt"] = self.salt
        return data
    
    def __repr__(self) -> str:
        return f"<Wallet(id={self.id}, name='{self.name}', address='{self.address[:8]}...')>"


class Balance(Base):
    """Balance model tracking token holdings per wallet."""
    
    __tablename__ = "balances"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    wallet_id = Column(Integer, ForeignKey("wallets.id", ondelete="CASCADE"), nullable=False)
    token = Column(String(50), nullable=False)  # Token symbol (e.g., ETH, USDC)
    token_address = Column(String(255), nullable=True)  # Contract address (null for native tokens)
    amount = Column(Float, default=0.0)
    usd_value = Column(Float, default=0.0)
    network = Column(String(50), nullable=False)  # e.g., ethereum, polygon, solana
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationship to wallet
    wallet = relationship("Wallet", back_populates="balances")
    
    def to_dict(self) -> dict:
        """Convert balance to dictionary."""
        return {
            "id": self.id,
            "wallet_id": self.wallet_id,
            "token": self.token,
            "token_address": self.token_address,
            "amount": self.amount,
            "usd_value": self.usd_value,
            "network": self.network,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
    
    def __repr__(self) -> str:
        return f"<Balance(wallet_id={self.wallet_id}, token='{self.token}', amount={self.amount})>"
