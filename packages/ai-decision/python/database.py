"""
Database integration for AI Decision logging
Logs all predictions for tracking and analysis
"""

import sqlite3
import json
import os
from datetime import datetime
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from contextlib import contextmanager


@dataclass
class AIDecisionRecord:
    """Record of an AI decision"""
    id: int
    symbol: str
    network: str
    action: str
    confidence: float
    total_score: float
    sentiment_score: float
    volume_score: float
    price_score: float
    reason: str
    input_data: Dict[str, Any]
    created_at: datetime
    
    # Optional outcome tracking
    outcome: Optional[str] = None  # 'profit', 'loss', 'pending'
    outcome_pct: Optional[float] = None
    outcome_at: Optional[datetime] = None


class AIDecisionDB:
    """
    Database handler for AI decisions
    Integrates with the main trader.db
    """
    
    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            # Default: use the main trader.db from frontend-streamlit
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
            db_path = os.path.join(base_dir, 'frontend-streamlit', 'data', 'trader.db')
        
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self._init_tables()
    
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
    
    def _init_tables(self):
        """Initialize AI decision tables"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # AI Decisions table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS ai_decisions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    network TEXT NOT NULL,
                    action TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    total_score REAL NOT NULL,
                    sentiment_score REAL,
                    volume_score REAL,
                    price_score REAL,
                    reason TEXT,
                    input_data TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    outcome TEXT,
                    outcome_pct REAL,
                    outcome_at TIMESTAMP
                )
            ''')
            
            # Create index for quick lookups
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_ai_decisions_symbol 
                ON ai_decisions(symbol, network)
            ''')
            
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_ai_decisions_created 
                ON ai_decisions(created_at DESC)
            ''')
            
            # AI Config history table (track config changes)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS ai_config_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    config_type TEXT NOT NULL,
                    config_data TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
    
    def log_decision(
        self,
        symbol: str,
        network: str,
        action: str,
        confidence: float,
        total_score: float,
        sentiment_score: Optional[float] = None,
        volume_score: Optional[float] = None,
        price_score: Optional[float] = None,
        reason: str = "",
        input_data: Optional[Dict[str, Any]] = None
    ) -> int:
        """
        Log an AI decision to the database
        
        Returns: inserted record ID
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO ai_decisions 
                (symbol, network, action, confidence, total_score, 
                 sentiment_score, volume_score, price_score, reason, input_data)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                symbol, network, action, confidence, total_score,
                sentiment_score, volume_score, price_score, reason,
                json.dumps(input_data) if input_data else None
            ))
            return cursor.lastrowid
    
    def log_analysis_result(self, result) -> int:
        """Log an AnalysisResult object"""
        # Accept duck-typed AnalysisResult to avoid circular import
        
        input_data = {
            'sentiment': result.prediction.input_sentiment,
            'volume_change': result.prediction.input_volume_change,
            'price_change': result.prediction.input_price_change
        }
        
        return self.log_decision(
            symbol=result.symbol,
            network=result.network,
            action=result.action.value,
            confidence=result.confidence,
            total_score=result.score.total_score,
            sentiment_score=result.score.sentiment_score,
            volume_score=result.score.volume_score,
            price_score=result.score.price_score,
            reason=result.prediction.reason,
            input_data=input_data
        )
    
    def get_decisions(
        self,
        symbol: Optional[str] = None,
        network: Optional[str] = None,
        action: Optional[str] = None,
        limit: int = 50
    ) -> List[AIDecisionRecord]:
        """Get decision history with optional filters"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            query = 'SELECT * FROM ai_decisions WHERE 1=1'
            params = []
            
            if symbol:
                query += ' AND symbol = ?'
                params.append(symbol)
            if network:
                query += ' AND network = ?'
                params.append(network)
            if action:
                query += ' AND action = ?'
                params.append(action)
            
            query += ' ORDER BY created_at DESC LIMIT ?'
            params.append(limit)
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            
            return [self._row_to_record(row) for row in rows]
    
    def get_recent_decisions(self, hours: int = 24, limit: int = 100) -> List[AIDecisionRecord]:
        """Get decisions from the last N hours"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM ai_decisions 
                WHERE created_at > datetime('now', ? || ' hours')
                ORDER BY created_at DESC
                LIMIT ?
            ''', (f'-{hours}', limit))
            
            return [self._row_to_record(row) for row in cursor.fetchall()]
    
    def update_outcome(
        self,
        decision_id: int,
        outcome: str,
        outcome_pct: Optional[float] = None
    ):
        """Update the outcome of a decision (for tracking accuracy)"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE ai_decisions 
                SET outcome = ?, outcome_pct = ?, outcome_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (outcome, outcome_pct, decision_id))
    
    def get_accuracy_stats(self, days: int = 30) -> Dict[str, Any]:
        """Get accuracy statistics for decisions with outcomes"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Total decisions with outcomes
            cursor.execute('''
                SELECT 
                    action,
                    COUNT(*) as total,
                    SUM(CASE WHEN outcome = 'profit' THEN 1 ELSE 0 END) as wins,
                    AVG(outcome_pct) as avg_pct
                FROM ai_decisions
                WHERE outcome IS NOT NULL
                AND created_at > datetime('now', ? || ' days')
                GROUP BY action
            ''', (f'-{days}',))
            
            results = {}
            for row in cursor.fetchall():
                action = row['action']
                total = row['total']
                wins = row['wins']
                results[action] = {
                    'total': total,
                    'wins': wins,
                    'win_rate': wins / total if total > 0 else 0,
                    'avg_return_pct': row['avg_pct']
                }
            
            return results
    
    def get_decision_by_id(self, decision_id: int) -> Optional[AIDecisionRecord]:
        """Get a specific decision by ID"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM ai_decisions WHERE id = ?', (decision_id,))
            row = cursor.fetchone()
            return self._row_to_record(row) if row else None
    
    def _row_to_record(self, row) -> AIDecisionRecord:
        """Convert database row to AIDecisionRecord"""
        return AIDecisionRecord(
            id=row['id'],
            symbol=row['symbol'],
            network=row['network'],
            action=row['action'],
            confidence=row['confidence'],
            total_score=row['total_score'],
            sentiment_score=row['sentiment_score'],
            volume_score=row['volume_score'],
            price_score=row['price_score'],
            reason=row['reason'] or '',
            input_data=json.loads(row['input_data']) if row['input_data'] else {},
            created_at=datetime.fromisoformat(row['created_at']) if row['created_at'] else datetime.now(),
            outcome=row['outcome'],
            outcome_pct=row['outcome_pct'],
            outcome_at=datetime.fromisoformat(row['outcome_at']) if row['outcome_at'] else None
        )
    
    def save_config(self, config_type: str, config_data: Dict[str, Any]):
        """Save a configuration snapshot"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO ai_config_history (config_type, config_data)
                VALUES (?, ?)
            ''', (config_type, json.dumps(config_data)))
    
    def get_stats_summary(self) -> Dict[str, Any]:
        """Get overall stats summary"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Total decisions
            cursor.execute('SELECT COUNT(*) as count FROM ai_decisions')
            total = cursor.fetchone()['count']
            
            # By action
            cursor.execute('''
                SELECT action, COUNT(*) as count 
                FROM ai_decisions 
                GROUP BY action
            ''')
            by_action = {row['action']: row['count'] for row in cursor.fetchall()}
            
            # Last 24h
            cursor.execute('''
                SELECT COUNT(*) as count FROM ai_decisions
                WHERE created_at > datetime('now', '-1 day')
            ''')
            last_24h = cursor.fetchone()['count']
            
            # Average confidence
            cursor.execute('SELECT AVG(confidence) as avg FROM ai_decisions')
            avg_confidence = cursor.fetchone()['avg'] or 0
            
            return {
                'total_decisions': total,
                'by_action': by_action,
                'last_24h': last_24h,
                'avg_confidence': round(avg_confidence, 3)
            }


# Singleton instance
_db_instance: Optional[AIDecisionDB] = None


def get_ai_db() -> AIDecisionDB:
    """Get the AI decision database singleton"""
    global _db_instance
    if _db_instance is None:
        _db_instance = AIDecisionDB()
    return _db_instance
