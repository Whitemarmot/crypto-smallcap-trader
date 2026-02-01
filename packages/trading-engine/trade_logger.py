"""
Trade Logger - Log all trades to database

Provides callbacks for strategies to log their executions.
"""

import sqlite3
import json
import os
from datetime import datetime
from typing import Optional, Dict, Any
from contextlib import contextmanager


class TradeLogger:
    """
    Log trades to SQLite database
    
    Compatible with the frontend database schema.
    
    Example:
        logger = TradeLogger()
        
        # Log a trade
        trade_id = logger.log_trade(
            wallet_id=1,
            strategy_id=5,
            trade_type="buy",
            token_in="USDC",
            token_out="ETH",
            amount_in="100",
            amount_out="0.032",
            price_usd=3125.0,
            tx_hash="0x123...",
            status="success",
            is_dry_run=True,
        )
    """
    
    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize trade logger
        
        Args:
            db_path: Path to SQLite database. Defaults to frontend DB.
        """
        if db_path is None:
            # Default to frontend database
            self.db_path = os.path.join(
                os.path.dirname(__file__), 
                '..', 'frontend-streamlit', 'data', 'trader.db'
            )
        else:
            self.db_path = db_path
        
        # Ensure directory exists
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        
        # Initialize tables
        self._init_db()
    
    @contextmanager
    def _get_connection(self):
        """Context manager for database connections"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
    
    def _init_db(self):
        """Initialize database tables if they don't exist"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Create trades table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS trades (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    wallet_id INTEGER,
                    strategy_id INTEGER,
                    tx_hash TEXT,
                    trade_type TEXT NOT NULL,
                    token_in TEXT NOT NULL,
                    token_out TEXT NOT NULL,
                    amount_in TEXT NOT NULL,
                    amount_out TEXT,
                    price_usd REAL,
                    gas_used INTEGER,
                    gas_price INTEGER,
                    network TEXT,
                    status TEXT DEFAULT 'pending',
                    is_dry_run INTEGER DEFAULT 1,
                    error TEXT,
                    metadata TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    executed_at TIMESTAMP
                )
            ''')
            
            # Create index for faster queries
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_trades_wallet 
                ON trades(wallet_id)
            ''')
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_trades_strategy 
                ON trades(strategy_id)
            ''')
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_trades_status 
                ON trades(status)
            ''')
    
    def log_trade(
        self,
        wallet_id: int,
        trade_type: str,
        token_in: str,
        token_out: str,
        amount_in: str,
        amount_out: Optional[str] = None,
        price_usd: Optional[float] = None,
        strategy_id: Optional[int] = None,
        tx_hash: Optional[str] = None,
        gas_used: int = 0,
        gas_price: int = 0,
        network: str = "ethereum",
        status: str = "pending",
        is_dry_run: bool = True,
        error: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> int:
        """
        Log a trade to the database
        
        Args:
            wallet_id: ID of the wallet
            trade_type: Type of trade (buy, sell, swap)
            token_in: Input token symbol
            token_out: Output token symbol
            amount_in: Input amount
            amount_out: Output amount (if known)
            price_usd: Price in USD
            strategy_id: Optional strategy ID
            tx_hash: Transaction hash (if executed)
            gas_used: Gas used
            gas_price: Gas price in wei
            network: Network name
            status: Trade status (pending, success, failed)
            is_dry_run: Whether this was a simulation
            error: Error message if failed
            metadata: Additional metadata
        
        Returns:
            Trade ID
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO trades (
                    wallet_id, strategy_id, tx_hash, trade_type,
                    token_in, token_out, amount_in, amount_out,
                    price_usd, gas_used, gas_price, network,
                    status, is_dry_run, error, metadata, executed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                wallet_id, strategy_id, tx_hash, trade_type,
                token_in, token_out, amount_in, amount_out,
                price_usd, gas_used, gas_price, network,
                status, int(is_dry_run), error,
                json.dumps(metadata) if metadata else None,
                datetime.utcnow().isoformat() if status != 'pending' else None
            ))
            return cursor.lastrowid
    
    def update_trade_status(
        self,
        trade_id: int,
        status: str,
        tx_hash: Optional[str] = None,
        amount_out: Optional[str] = None,
        gas_used: int = 0,
        error: Optional[str] = None,
    ):
        """Update trade status after execution"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            updates = ["status = ?", "executed_at = ?"]
            values = [status, datetime.utcnow().isoformat()]
            
            if tx_hash:
                updates.append("tx_hash = ?")
                values.append(tx_hash)
            
            if amount_out:
                updates.append("amount_out = ?")
                values.append(amount_out)
            
            if gas_used:
                updates.append("gas_used = ?")
                values.append(gas_used)
            
            if error:
                updates.append("error = ?")
                values.append(error)
            
            values.append(trade_id)
            
            cursor.execute(f'''
                UPDATE trades SET {", ".join(updates)}
                WHERE id = ?
            ''', values)
    
    def get_trades(
        self,
        wallet_id: Optional[int] = None,
        strategy_id: Optional[int] = None,
        status: Optional[str] = None,
        limit: int = 50,
    ) -> list:
        """Get trades from database"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            query = "SELECT * FROM trades WHERE 1=1"
            params = []
            
            if wallet_id:
                query += " AND wallet_id = ?"
                params.append(wallet_id)
            
            if strategy_id:
                query += " AND strategy_id = ?"
                params.append(strategy_id)
            
            if status:
                query += " AND status = ?"
                params.append(status)
            
            query += " ORDER BY created_at DESC LIMIT ?"
            params.append(limit)
            
            cursor.execute(query, params)
            
            return [dict(row) for row in cursor.fetchall()]
    
    def get_trade_stats(
        self,
        wallet_id: Optional[int] = None,
        strategy_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Get aggregate trade statistics"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            where = "1=1"
            params = []
            
            if wallet_id:
                where += " AND wallet_id = ?"
                params.append(wallet_id)
            
            if strategy_id:
                where += " AND strategy_id = ?"
                params.append(strategy_id)
            
            # Total trades
            cursor.execute(f"SELECT COUNT(*) FROM trades WHERE {where}", params)
            total = cursor.fetchone()[0]
            
            # Successful trades
            cursor.execute(
                f"SELECT COUNT(*) FROM trades WHERE {where} AND status = 'success'",
                params
            )
            successful = cursor.fetchone()[0]
            
            # Dry run vs live
            cursor.execute(
                f"SELECT COUNT(*) FROM trades WHERE {where} AND is_dry_run = 1",
                params
            )
            dry_runs = cursor.fetchone()[0]
            
            # Volume (sum of amount_in for successful trades)
            cursor.execute(
                f"SELECT SUM(CAST(amount_in AS REAL)) FROM trades WHERE {where} AND status = 'success'",
                params
            )
            volume = cursor.fetchone()[0] or 0
            
            return {
                "total_trades": total,
                "successful_trades": successful,
                "failed_trades": total - successful,
                "dry_run_trades": dry_runs,
                "live_trades": total - dry_runs,
                "success_rate": (successful / total * 100) if total > 0 else 0,
                "total_volume": volume,
            }


# Strategy callback for logging
def create_db_callback(logger: TradeLogger, wallet_id: int, strategy_id: int):
    """
    Create a callback function for strategies to log executions
    
    Args:
        logger: TradeLogger instance
        wallet_id: Wallet ID
        strategy_id: Strategy ID
    
    Returns:
        Async callback function
    
    Example:
        logger = TradeLogger()
        callback = create_db_callback(logger, wallet_id=1, strategy_id=5)
        strategy = DCAStrategy(config, db_callback=callback)
    """
    async def callback(result):
        """Log execution result to database"""
        try:
            logger.log_trade(
                wallet_id=wallet_id,
                strategy_id=strategy_id,
                trade_type="buy" if result.metadata.get('type') == 'dca' else "swap",
                token_in=result.metadata.get('token_in', 'USDC'),
                token_out=result.metadata.get('token_out', 'ETH'),
                amount_in=str(result.amount_in) if result.amount_in else "0",
                amount_out=str(result.amount_out) if result.amount_out else None,
                price_usd=float(result.price) if result.price else None,
                tx_hash=result.tx_hash,
                gas_used=result.gas_used if hasattr(result, 'gas_used') else 0,
                network=result.metadata.get('network', 'ethereum'),
                status="success" if result.success else "failed",
                is_dry_run=result.is_dry_run,
                error=result.error,
                metadata=result.metadata,
            )
        except Exception as e:
            print(f"Failed to log trade: {e}")
    
    return callback


# Singleton instance
_logger_instance: Optional[TradeLogger] = None


def get_trade_logger(db_path: Optional[str] = None) -> TradeLogger:
    """Get the trade logger singleton instance"""
    global _logger_instance
    if _logger_instance is None:
        _logger_instance = TradeLogger(db_path)
    return _logger_instance


# Exports
__all__ = [
    "TradeLogger",
    "create_db_callback",
    "get_trade_logger",
]
