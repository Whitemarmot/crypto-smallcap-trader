"""
Crypto SmallCap Trader - SQLite Database for Wallets & Strategies
Multi-wallet management with encrypted private keys
"""

import sqlite3
import json
import os
from datetime import datetime
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from contextlib import contextmanager


DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'trader.db')


@dataclass
class WalletRecord:
    """Wallet record from database"""
    id: int
    name: str
    address: str
    network: str
    is_active: bool
    created_at: datetime
    encrypted_key: Optional[bytes] = None


@dataclass  
class StrategyRecord:
    """Strategy record from database"""
    id: int
    name: str
    strategy_type: str
    wallet_id: int
    config: Dict[str, Any]
    is_active: bool
    created_at: datetime
    last_run: Optional[datetime] = None


@dataclass
class StrategyExecution:
    """Strategy execution history record"""
    id: int
    strategy_id: int
    executed_at: datetime
    status: str
    result: Dict[str, Any]
    tx_hash: Optional[str] = None
    error: Optional[str] = None


class Database:
    """SQLite database manager for trader app"""
    
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self._init_db()
    
    @contextmanager
    def get_connection(self):
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
        """Initialize database tables"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Wallets table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS wallets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    address TEXT UNIQUE NOT NULL,
                    network TEXT DEFAULT 'ethereum',
                    encrypted_key BLOB,
                    is_active INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Strategies table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS strategies (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    strategy_type TEXT NOT NULL,
                    wallet_id INTEGER,
                    config TEXT DEFAULT '{}',
                    is_active INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_run TIMESTAMP,
                    FOREIGN KEY (wallet_id) REFERENCES wallets(id)
                )
            ''')
            
            # Strategy executions table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS strategy_executions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    strategy_id INTEGER NOT NULL,
                    executed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    status TEXT NOT NULL,
                    result TEXT DEFAULT '{}',
                    tx_hash TEXT,
                    error TEXT,
                    FOREIGN KEY (strategy_id) REFERENCES strategies(id)
                )
            ''')
            
            # Trades table
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
                    status TEXT DEFAULT 'pending',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    executed_at TIMESTAMP,
                    FOREIGN KEY (wallet_id) REFERENCES wallets(id),
                    FOREIGN KEY (strategy_id) REFERENCES strategies(id)
                )
            ''')
            
            # Settings table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Social signals table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS signals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    token TEXT NOT NULL,
                    signal_type TEXT NOT NULL,
                    source TEXT NOT NULL,
                    message TEXT,
                    sentiment_score REAL DEFAULT 0,
                    hype_score REAL DEFAULT 0,
                    mentions INTEGER DEFAULT 1,
                    metadata TEXT DEFAULT '{}',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Token trending stats (aggregated)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS token_trends (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    token TEXT NOT NULL,
                    mentions_1h INTEGER DEFAULT 0,
                    mentions_24h INTEGER DEFAULT 0,
                    avg_sentiment REAL DEFAULT 0,
                    hype_score REAL DEFAULT 0,
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(token)
                )
            ''')
    
    # ========== WALLET METHODS ==========
    
    def add_wallet(self, name: str, address: str, network: str = 'ethereum', 
                   encrypted_key: Optional[bytes] = None) -> int:
        """Add a new wallet"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO wallets (name, address, network, encrypted_key)
                VALUES (?, ?, ?, ?)
            ''', (name, address.lower(), network, encrypted_key))
            return cursor.lastrowid
    
    def get_wallets(self) -> List[WalletRecord]:
        """Get all wallets"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM wallets ORDER BY created_at DESC')
            rows = cursor.fetchall()
            return [WalletRecord(
                id=row['id'],
                name=row['name'],
                address=row['address'],
                network=row['network'],
                is_active=bool(row['is_active']),
                created_at=datetime.fromisoformat(row['created_at']) if row['created_at'] else datetime.now(),
                encrypted_key=row['encrypted_key']
            ) for row in rows]
    
    def get_active_wallet(self) -> Optional[WalletRecord]:
        """Get the currently active wallet"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM wallets WHERE is_active = 1 LIMIT 1')
            row = cursor.fetchone()
            if row:
                return WalletRecord(
                    id=row['id'],
                    name=row['name'],
                    address=row['address'],
                    network=row['network'],
                    is_active=True,
                    created_at=datetime.fromisoformat(row['created_at']) if row['created_at'] else datetime.now(),
                    encrypted_key=row['encrypted_key']
                )
            return None
    
    def set_active_wallet(self, wallet_id: int):
        """Set a wallet as active (deactivates others)"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('UPDATE wallets SET is_active = 0')
            cursor.execute('UPDATE wallets SET is_active = 1 WHERE id = ?', (wallet_id,))
    
    def delete_wallet(self, wallet_id: int):
        """Delete a wallet"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM wallets WHERE id = ?', (wallet_id,))
    
    def update_wallet_name(self, wallet_id: int, name: str):
        """Update wallet name"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('UPDATE wallets SET name = ? WHERE id = ?', (name, wallet_id))
    
    # ========== STRATEGY METHODS ==========
    
    def add_strategy(self, name: str, strategy_type: str, wallet_id: int, 
                     config: Dict[str, Any]) -> int:
        """Add a new strategy"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO strategies (name, strategy_type, wallet_id, config)
                VALUES (?, ?, ?, ?)
            ''', (name, strategy_type, wallet_id, json.dumps(config)))
            return cursor.lastrowid
    
    def get_strategies(self, wallet_id: Optional[int] = None) -> List[StrategyRecord]:
        """Get all strategies, optionally filtered by wallet"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if wallet_id:
                cursor.execute('SELECT * FROM strategies WHERE wallet_id = ? ORDER BY created_at DESC', (wallet_id,))
            else:
                cursor.execute('SELECT * FROM strategies ORDER BY created_at DESC')
            rows = cursor.fetchall()
            return [StrategyRecord(
                id=row['id'],
                name=row['name'],
                strategy_type=row['strategy_type'],
                wallet_id=row['wallet_id'],
                config=json.loads(row['config']) if row['config'] else {},
                is_active=bool(row['is_active']),
                created_at=datetime.fromisoformat(row['created_at']) if row['created_at'] else datetime.now(),
                last_run=datetime.fromisoformat(row['last_run']) if row['last_run'] else None
            ) for row in rows]
    
    def get_active_strategies(self) -> List[StrategyRecord]:
        """Get only active strategies"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM strategies WHERE is_active = 1')
            rows = cursor.fetchall()
            return [StrategyRecord(
                id=row['id'],
                name=row['name'],
                strategy_type=row['strategy_type'],
                wallet_id=row['wallet_id'],
                config=json.loads(row['config']) if row['config'] else {},
                is_active=True,
                created_at=datetime.fromisoformat(row['created_at']) if row['created_at'] else datetime.now(),
                last_run=datetime.fromisoformat(row['last_run']) if row['last_run'] else None
            ) for row in rows]
    
    def toggle_strategy(self, strategy_id: int, active: bool):
        """Enable/disable a strategy"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('UPDATE strategies SET is_active = ? WHERE id = ?', (int(active), strategy_id))
    
    def update_strategy_config(self, strategy_id: int, config: Dict[str, Any]):
        """Update strategy configuration"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('UPDATE strategies SET config = ? WHERE id = ?', (json.dumps(config), strategy_id))
    
    def delete_strategy(self, strategy_id: int):
        """Delete a strategy"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM strategies WHERE id = ?', (strategy_id,))
    
    def update_strategy_last_run(self, strategy_id: int):
        """Update last run timestamp"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('UPDATE strategies SET last_run = CURRENT_TIMESTAMP WHERE id = ?', (strategy_id,))
    
    # ========== EXECUTION HISTORY ==========
    
    def add_execution(self, strategy_id: int, status: str, result: Dict[str, Any],
                      tx_hash: Optional[str] = None, error: Optional[str] = None) -> int:
        """Record a strategy execution"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO strategy_executions (strategy_id, status, result, tx_hash, error)
                VALUES (?, ?, ?, ?, ?)
            ''', (strategy_id, status, json.dumps(result), tx_hash, error))
            return cursor.lastrowid
    
    def get_executions(self, strategy_id: Optional[int] = None, limit: int = 50) -> List[StrategyExecution]:
        """Get execution history"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if strategy_id:
                cursor.execute('''
                    SELECT * FROM strategy_executions 
                    WHERE strategy_id = ? 
                    ORDER BY executed_at DESC LIMIT ?
                ''', (strategy_id, limit))
            else:
                cursor.execute('''
                    SELECT * FROM strategy_executions 
                    ORDER BY executed_at DESC LIMIT ?
                ''', (limit,))
            rows = cursor.fetchall()
            return [StrategyExecution(
                id=row['id'],
                strategy_id=row['strategy_id'],
                executed_at=datetime.fromisoformat(row['executed_at']) if row['executed_at'] else datetime.now(),
                status=row['status'],
                result=json.loads(row['result']) if row['result'] else {},
                tx_hash=row['tx_hash'],
                error=row['error']
            ) for row in rows]
    
    # ========== TRADES ==========
    
    def add_trade(self, wallet_id: int, trade_type: str, token_in: str, token_out: str,
                  amount_in: str, amount_out: Optional[str] = None, price_usd: Optional[float] = None,
                  strategy_id: Optional[int] = None, tx_hash: Optional[str] = None) -> int:
        """Record a trade"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO trades (wallet_id, strategy_id, tx_hash, trade_type, token_in, token_out, amount_in, amount_out, price_usd)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (wallet_id, strategy_id, tx_hash, trade_type, token_in, token_out, amount_in, amount_out, price_usd))
            return cursor.lastrowid
    
    def get_trades(self, wallet_id: Optional[int] = None, limit: int = 50) -> List[Dict[str, Any]]:
        """Get trade history"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if wallet_id:
                cursor.execute('SELECT * FROM trades WHERE wallet_id = ? ORDER BY created_at DESC LIMIT ?', (wallet_id, limit))
            else:
                cursor.execute('SELECT * FROM trades ORDER BY created_at DESC LIMIT ?', (limit,))
            return [dict(row) for row in cursor.fetchall()]
    
    # ========== SETTINGS ==========
    
    def get_setting(self, key: str, default: Any = None) -> Any:
        """Get a setting value"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT value FROM settings WHERE key = ?', (key,))
            row = cursor.fetchone()
            if row:
                try:
                    return json.loads(row['value'])
                except json.JSONDecodeError:
                    return row['value']
            return default
    
    def set_setting(self, key: str, value: Any):
        """Set a setting value"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            value_str = json.dumps(value) if not isinstance(value, str) else value
            cursor.execute('''
                INSERT OR REPLACE INTO settings (key, value, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
            ''', (key, value_str))
    
    def get_all_settings(self) -> Dict[str, Any]:
        """Get all settings"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT key, value FROM settings')
            result = {}
            for row in cursor.fetchall():
                try:
                    result[row['key']] = json.loads(row['value'])
                except json.JSONDecodeError:
                    result[row['key']] = row['value']
            return result
    
    # ========== SIGNALS ==========
    
    def add_signal(self, token: str, signal_type: str, source: str, 
                   message: Optional[str] = None, sentiment_score: float = 0,
                   hype_score: float = 0, metadata: Optional[Dict] = None) -> int:
        """Add a new social signal"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO signals (token, signal_type, source, message, sentiment_score, hype_score, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (token.upper(), signal_type, source, message, sentiment_score, hype_score, 
                  json.dumps(metadata or {})))
            return cursor.lastrowid
    
    def get_signals(self, limit: int = 50, token: Optional[str] = None, 
                    source: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get recent signals"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            query = 'SELECT * FROM signals WHERE 1=1'
            params = []
            
            if token:
                query += ' AND token = ?'
                params.append(token.upper())
            if source:
                query += ' AND source = ?'
                params.append(source)
            
            query += ' ORDER BY created_at DESC LIMIT ?'
            params.append(limit)
            
            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]
    
    def update_token_trend(self, token: str, mentions_1h: int, mentions_24h: int,
                           avg_sentiment: float, hype_score: float):
        """Update or insert token trending stats"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO token_trends (token, mentions_1h, mentions_24h, avg_sentiment, hype_score, last_updated)
                VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ''', (token.upper(), mentions_1h, mentions_24h, avg_sentiment, hype_score))
    
    def get_trending_tokens(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get top trending tokens by hype score"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM token_trends 
                ORDER BY hype_score DESC, mentions_24h DESC 
                LIMIT ?
            ''', (limit,))
            return [dict(row) for row in cursor.fetchall()]
    
    def get_token_sentiment(self, token: str) -> Optional[Dict[str, Any]]:
        """Get sentiment data for a specific token"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM token_trends WHERE token = ?', (token.upper(),))
            row = cursor.fetchone()
            return dict(row) if row else None
    
    def cleanup_old_signals(self, days: int = 7):
        """Remove signals older than X days"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                DELETE FROM signals 
                WHERE created_at < datetime('now', ?)
            ''', (f'-{days} days',))
    
    # ========== STATS ==========
    
    def get_portfolio_stats(self) -> Dict[str, Any]:
        """Get aggregate portfolio statistics"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Total wallets
            cursor.execute('SELECT COUNT(*) as count FROM wallets')
            total_wallets = cursor.fetchone()['count']
            
            # Active strategies
            cursor.execute('SELECT COUNT(*) as count FROM strategies WHERE is_active = 1')
            active_strategies = cursor.fetchone()['count']
            
            # Total trades
            cursor.execute('SELECT COUNT(*) as count FROM trades')
            total_trades = cursor.fetchone()['count']
            
            # Recent trades (24h)
            cursor.execute('''
                SELECT COUNT(*) as count FROM trades 
                WHERE created_at > datetime('now', '-1 day')
            ''')
            recent_trades = cursor.fetchone()['count']
            
            return {
                'total_wallets': total_wallets,
                'active_strategies': active_strategies,
                'total_trades': total_trades,
                'recent_trades_24h': recent_trades
            }


# Singleton instance
_db_instance: Optional[Database] = None


def get_db() -> Database:
    """Get the database singleton instance"""
    global _db_instance
    if _db_instance is None:
        _db_instance = Database()
    return _db_instance
