"""
Database setup and session management for wallet manager.
"""
import os
from contextlib import contextmanager
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

try:
    from .models import Base
except ImportError:
    from models import Base

# Default database path
DEFAULT_DB_PATH = os.path.join(os.path.dirname(__file__), "data", "wallets.db")


class Database:
    """Database manager for wallet storage."""
    
    def __init__(self, db_path: str = None):
        """
        Initialize database connection.
        
        Args:
            db_path: Path to SQLite database file. Defaults to data/wallets.db
        """
        self.db_path = db_path or os.environ.get("WALLET_DB_PATH", DEFAULT_DB_PATH)
        
        # Ensure data directory exists
        db_dir = os.path.dirname(self.db_path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)
        
        # Create engine with SQLite
        self.engine = create_engine(
            f"sqlite:///{self.db_path}",
            echo=False,
            connect_args={"check_same_thread": False}  # Allow multi-threaded access
        )
        
        # Session factory
        self.SessionLocal = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=self.engine
        )
    
    def init_db(self) -> None:
        """Create all tables in the database."""
        Base.metadata.create_all(bind=self.engine)
    
    def drop_db(self) -> None:
        """Drop all tables (use with caution!)."""
        Base.metadata.drop_all(bind=self.engine)
    
    @contextmanager
    def get_session(self) -> Session:
        """
        Context manager for database sessions.
        
        Usage:
            with db.get_session() as session:
                session.query(Wallet).all()
        """
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
    
    def get_session_instance(self) -> Session:
        """Get a session instance (caller must handle commit/close)."""
        return self.SessionLocal()


# Global database instance (lazy initialization)
_db_instance: Database = None


def get_database(db_path: str = None) -> Database:
    """
    Get the global database instance.
    
    Args:
        db_path: Optional path to database file
        
    Returns:
        Database instance
    """
    global _db_instance
    if _db_instance is None:
        _db_instance = Database(db_path)
    return _db_instance


def init_db(db_path: str = None) -> Database:
    """
    Initialize the database and create all tables.
    
    Args:
        db_path: Optional path to database file
        
    Returns:
        Initialized Database instance
    """
    db = get_database(db_path)
    db.init_db()
    return db
