#!/usr/bin/env python3
"""
Snapshot CoinGecko Trending - Called by cron
Saves trending tokens to SQLite for delta tracking
"""

import sys
import os

# Add parent to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from utils.social_signals import get_trending_tokens
from utils.trending_tracker import save_snapshot, get_snapshot_count

def main():
    print("📸 Capturing trending snapshot...")
    
    # Get current trending from CoinGecko
    trending = get_trending_tokens()
    
    if trending:
        # Convert to dict format expected by save_snapshot
        tokens = [
            {
                'symbol': t.symbol,
                'name': t.name,
                'market_cap_rank': t.market_cap_rank,
                'thumb': getattr(t, 'thumb', None)
            }
            for t in trending
        ]
        
        save_snapshot(tokens)
        
        counts = get_snapshot_count()
        print(f"✅ Saved {len(tokens)} tokens | Total snapshots: {counts['total']} ({counts['24h']} last 24h)")
    else:
        print("❌ Failed to fetch trending tokens")
        return 1
    
    return 0

if __name__ == '__main__':
    sys.exit(main())
