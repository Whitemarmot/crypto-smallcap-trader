"""
Trending Tracker - Track token trending position changes over time
Stores snapshots in SQLite and calculates deltas (24h, 7d, 30d)
"""

import sqlite3
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import os

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'trending.db')


@dataclass
class TrendingDelta:
    """Token with trending position deltas"""
    symbol: str
    name: str
    current_rank: int
    market_cap_rank: Optional[int]
    delta_24h: Optional[int]  # Positive = gained ranks, Negative = lost ranks
    delta_7d: Optional[int]
    delta_30d: Optional[int]
    is_new_24h: bool  # First time in trending in 24h
    is_new_7d: bool
    is_new_30d: bool
    thumb: Optional[str] = None


def get_db():
    """Get database connection, create tables if needed"""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    
    # Create tables
    conn.execute("""
        CREATE TABLE IF NOT EXISTS trending_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            data TEXT NOT NULL
        )
    """)
    
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_trending_timestamp 
        ON trending_snapshots(timestamp)
    """)
    
    conn.commit()
    return conn


def save_snapshot(tokens: List[Dict]):
    """Save current trending snapshot to DB"""
    if not tokens:
        return
    
    conn = get_db()
    
    # Prepare data
    snapshot_data = {
        'tokens': [
            {
                'symbol': t.get('symbol', '').upper(),
                'name': t.get('name', ''),
                'rank': i + 1,  # Trending position
                'market_cap_rank': t.get('market_cap_rank'),
                'thumb': t.get('thumb')
            }
            for i, t in enumerate(tokens)
        ]
    }
    
    conn.execute(
        "INSERT INTO trending_snapshots (data) VALUES (?)",
        (json.dumps(snapshot_data),)
    )
    conn.commit()
    conn.close()


def get_snapshot_at(hours_ago: int) -> Optional[Dict]:
    """Get the closest snapshot from X hours ago"""
    conn = get_db()
    
    target_time = datetime.now() - timedelta(hours=hours_ago)
    # Allow 2 hour window
    min_time = target_time - timedelta(hours=2)
    max_time = target_time + timedelta(hours=2)
    
    cursor = conn.execute("""
        SELECT data, timestamp FROM trending_snapshots
        WHERE timestamp BETWEEN ? AND ?
        ORDER BY ABS(strftime('%s', timestamp) - strftime('%s', ?))
        LIMIT 1
    """, (min_time, max_time, target_time))
    
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return json.loads(row[0])
    return None


def get_token_rank_from_snapshot(snapshot: Dict, symbol: str) -> Optional[int]:
    """Get token's trending rank from a snapshot"""
    if not snapshot or 'tokens' not in snapshot:
        return None
    
    for token in snapshot['tokens']:
        if token.get('symbol', '').upper() == symbol.upper():
            return token.get('rank')
    
    return None  # Token wasn't in trending


def calculate_deltas(current_tokens: List[Dict]) -> List[TrendingDelta]:
    """Calculate trending position deltas for current tokens"""
    
    # Get historical snapshots
    snapshot_24h = get_snapshot_at(24)
    snapshot_7d = get_snapshot_at(24 * 7)
    snapshot_30d = get_snapshot_at(24 * 30)
    
    results = []
    
    for i, token in enumerate(current_tokens):
        symbol = token.get('symbol', '').upper()
        current_rank = i + 1
        
        # Get historical ranks
        rank_24h = get_token_rank_from_snapshot(snapshot_24h, symbol)
        rank_7d = get_token_rank_from_snapshot(snapshot_7d, symbol)
        rank_30d = get_token_rank_from_snapshot(snapshot_30d, symbol)
        
        # Calculate deltas (positive = moved up = good)
        delta_24h = (rank_24h - current_rank) if rank_24h else None
        delta_7d = (rank_7d - current_rank) if rank_7d else None
        delta_30d = (rank_30d - current_rank) if rank_30d else None
        
        results.append(TrendingDelta(
            symbol=symbol,
            name=token.get('name', ''),
            current_rank=current_rank,
            market_cap_rank=token.get('market_cap_rank'),
            delta_24h=delta_24h,
            delta_7d=delta_7d,
            delta_30d=delta_30d,
            is_new_24h=rank_24h is None and snapshot_24h is not None,
            is_new_7d=rank_7d is None and snapshot_7d is not None,
            is_new_30d=rank_30d is None and snapshot_30d is not None,
            thumb=token.get('thumb')
        ))
    
    return results


def format_delta(delta: Optional[int], is_new: bool) -> str:
    """Format delta for display"""
    if is_new:
        return "🆕 NEW"
    if delta is None:
        return "—"
    if delta > 0:
        return f"↑{delta}"
    if delta < 0:
        return f"↓{abs(delta)}"
    return "="


def format_delta_color(delta: Optional[int], is_new: bool) -> str:
    """Get color for delta"""
    if is_new:
        return "#00ff88"  # Green for new
    if delta is None:
        return "#888888"
    if delta > 0:
        return "#00ff88"  # Green for up
    if delta < 0:
        return "#ff4444"  # Red for down
    return "#888888"  # Gray for unchanged


def get_trending_with_deltas() -> List[TrendingDelta]:
    """
    Fetch current trending and calculate deltas
    Also saves snapshot for future comparisons
    """
    from utils.social_signals import get_trending_tokens
    
    # Get current trending
    trending = get_trending_tokens()
    
    if not trending:
        return []
    
    # Convert to dict format
    tokens = [
        {
            'symbol': t.symbol,
            'name': t.name,
            'market_cap_rank': t.market_cap_rank,
            'thumb': t.thumb
        }
        for t in trending
    ]
    
    # Save snapshot
    save_snapshot(tokens)
    
    # Calculate deltas
    return calculate_deltas(tokens)


def get_snapshot_count() -> Dict[str, int]:
    """Get number of snapshots in different time periods"""
    conn = get_db()
    
    now = datetime.now()
    
    counts = {}
    
    # Last 24h
    cursor = conn.execute("""
        SELECT COUNT(*) FROM trending_snapshots
        WHERE timestamp > ?
    """, (now - timedelta(hours=24),))
    counts['24h'] = cursor.fetchone()[0]
    
    # Last 7d
    cursor = conn.execute("""
        SELECT COUNT(*) FROM trending_snapshots
        WHERE timestamp > ?
    """, (now - timedelta(days=7),))
    counts['7d'] = cursor.fetchone()[0]
    
    # Last 30d
    cursor = conn.execute("""
        SELECT COUNT(*) FROM trending_snapshots
        WHERE timestamp > ?
    """, (now - timedelta(days=30),))
    counts['30d'] = cursor.fetchone()[0]
    
    # Total
    cursor = conn.execute("SELECT COUNT(*) FROM trending_snapshots")
    counts['total'] = cursor.fetchone()[0]
    
    conn.close()
    return counts


def cleanup_old_snapshots(keep_days: int = 60):
    """Remove snapshots older than X days"""
    conn = get_db()
    cutoff = datetime.now() - timedelta(days=keep_days)
    
    conn.execute(
        "DELETE FROM trending_snapshots WHERE timestamp < ?",
        (cutoff,)
    )
    conn.commit()
    conn.close()
