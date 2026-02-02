#!/usr/bin/env python3
"""
📊 Position Price Tracker
Enregistre les prix des positions ouvertes pour les graphiques d'évolution.
Appelé périodiquement (cron ou après chaque run du bot).
"""

import json
import os
import sys
import requests
import time
from datetime import datetime

CMC_API_KEY = os.getenv('CMC_API_KEY', '849ddcc694a049708d0b5392486d6eaa')

def get_price_cmc(symbol: str) -> float:
    """Get price from CMC API"""
    symbol = symbol.upper()
    try:
        resp = requests.get(
            'https://pro-api.coinmarketcap.com/v1/cryptocurrency/quotes/latest',
            headers={'X-CMC_PRO_API_KEY': CMC_API_KEY},
            params={'symbol': symbol, 'convert': 'USD'},
            timeout=10
        )
        data = resp.json()
        if 'data' in data and symbol in data['data']:
            return data['data'][symbol]['quote']['USD']['price']
    except Exception as e:
        print(f"CMC error for {symbol}: {e}")
    return 0

DATA_DIR = os.path.join(os.path.dirname(__file__), '..', 'data')
SIM_PATH = os.path.join(DATA_DIR, 'simulation.json')
HISTORY_PATH = os.path.join(DATA_DIR, 'position_history.json')

def load_json(path, default):
    try:
        if os.path.exists(path):
            with open(path, 'r') as f:
                return json.load(f)
    except:
        pass
    return default

def save_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w') as f:
        json.dump(data, f, indent=2, default=str)

def track_positions():
    """Record current prices for all open positions."""
    sim = load_json(SIM_PATH, {})
    history = load_json(HISTORY_PATH, {'snapshots': {}})
    
    positions = sim.get('positions', {})
    if not positions:
        print("No open positions to track")
        return
    
    timestamp = datetime.now().isoformat()
    
    for symbol, pos in positions.items():
        # Get current price
        price = get_price_cmc(symbol)
        if price <= 0:
            price = pos.get('avg_price', 0)
        time.sleep(0.2)  # Rate limit protection
        
        # Calculate PnL
        avg_price = pos.get('avg_price', 0)
        pnl_pct = ((price / avg_price) - 1) * 100 if avg_price > 0 else 0
        value = pos.get('amount', 0) * price
        
        # Initialize symbol history if needed
        if symbol not in history['snapshots']:
            history['snapshots'][symbol] = []
        
        # Add snapshot
        history['snapshots'][symbol].append({
            'ts': timestamp,
            'price': price,
            'pnl_pct': round(pnl_pct, 2),
            'value': round(value, 2)
        })
        
        # Keep only last 168 snapshots per symbol (7 days at 1h intervals)
        history['snapshots'][symbol] = history['snapshots'][symbol][-168:]
        
        print(f"📊 {symbol}: ${price:.6f} ({pnl_pct:+.2f}%) = ${value:.2f}")
    
    history['last_update'] = timestamp
    save_json(HISTORY_PATH, history)
    print(f"✅ Tracked {len(positions)} positions at {timestamp}")

if __name__ == '__main__':
    track_positions()
