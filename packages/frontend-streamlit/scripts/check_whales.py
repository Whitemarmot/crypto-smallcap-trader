#!/usr/bin/env python3
"""
🐋 Check Whales - Periodic whale monitoring script
Run via cron to check for whale activity
"""

import os
import sys
import json
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from utils.whale_api import (
    load_tracked_whales,
    check_all_whales,
    get_whale_transactions_sync,
    get_token_transfers
)

DATA_DIR = os.path.join(os.path.dirname(__file__), '..', 'data', 'whales')
LAST_CHECK_FILE = os.path.join(DATA_DIR, 'last_check.json')


def main():
    """Check all tracked whales for new activity"""
    
    tracked = load_tracked_whales()
    
    if not tracked:
        print(json.dumps({
            "status": "ok",
            "message": "No whales being tracked",
            "checked_at": datetime.now().isoformat()
        }))
        return
    
    print(f"🐋 Checking {len(tracked)} tracked whales...", file=sys.stderr)
    
    # Check all whales
    results = check_all_whales()
    
    # Format output
    output = {
        "status": "ok",
        "checked_at": results.get('checked_at'),
        "whales_checked": results.get('whales_checked', 0),
        "summary": []
    }
    
    # Summarize new transactions
    if results.get('new_transactions'):
        for whale_txs in results['new_transactions']:
            whale_name = whale_txs.get('whale', 'Unknown')
            count = whale_txs.get('count', 0)
            txs = whale_txs.get('transactions', [])
            
            summary_entry = {
                "whale": whale_name,
                "new_transactions": count,
                "highlights": []
            }
            
            for tx in txs[:3]:  # Top 3 transactions
                direction = tx.get('swap_direction', 'transfer')
                symbol = tx.get('token_symbol', 'ETH')
                value = tx.get('value', 0)
                
                emoji = "🟢" if direction == 'buy' else "🔴" if direction == 'sell' else "➡️"
                summary_entry["highlights"].append(
                    f"{emoji} {direction.upper()} {value:.4f} {symbol}"
                )
            
            output["summary"].append(summary_entry)
    
    # Add alerts
    if results.get('alerts'):
        output["alerts"] = []
        for alert in results['alerts']:
            output["alerts"].append({
                "message": alert.get('message'),
                "importance": alert.get('importance'),
                "tx_hash": alert.get('tx_hash')
            })
    
    # Save last check timestamp
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(LAST_CHECK_FILE, 'w') as f:
        json.dump({
            "last_check": datetime.now().isoformat(),
            "whales_checked": len(tracked)
        }, f)
    
    # Output JSON
    print(json.dumps(output, indent=2))
    
    # Return summary for Jean-Michel
    if output.get("summary") or output.get("alerts"):
        return output
    
    return None


if __name__ == '__main__':
    main()
