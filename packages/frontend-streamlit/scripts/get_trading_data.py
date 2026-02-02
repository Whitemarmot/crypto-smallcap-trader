#!/usr/bin/env python3
"""
📊 Get Trading Data for Jean-Michel
Outputs JSON with all data needed for trading decisions.
Jean-Michel will do web research and make decisions.
"""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from utils.social_signals import get_fear_greed_index, get_tokens_by_market_cap_cmc

DATA_DIR = os.path.join(os.path.dirname(__file__), '..', 'data')
SIM_PATH = os.path.join(DATA_DIR, 'simulation.json')
CONFIG_PATH = os.path.join(DATA_DIR, 'bot_config.json')

def load_json(path, default):
    try:
        if os.path.exists(path):
            with open(path, 'r') as f:
                return json.load(f)
    except:
        pass
    return default

def main():
    # Load config
    config = load_json(CONFIG_PATH, {})
    sim = load_json(SIM_PATH, {'portfolio': {'USDC': 10000}, 'positions': {}, 'history': []})
    
    # Get market data
    fg = get_fear_greed_index()
    fg_val = fg.value if fg else 50
    fg_class = fg.classification if fg else 'Neutral'
    
    # Get tokens based on config
    mcap = config.get('mcap', 'small')
    chain = config.get('chain', 'all')
    
    mcap_ranges = {
        'micro': (0, 1_000_000),
        'small': (1_000_000, 100_000_000),
        'mid': (100_000_000, 1_000_000_000),
        'large': (1_000_000_000, float('inf')),
    }
    min_mcap, max_mcap = mcap_ranges.get(mcap, (1_000_000, 100_000_000))
    
    tokens = get_tokens_by_market_cap_cmc(min_mcap, max_mcap, limit=200)
    
    # Sort by 24h performance
    sorted_tokens = sorted(tokens, key=lambda x: x.get('price_change_24h', 0) or 0, reverse=True)
    
    # Calculate portfolio
    cash = sim.get('portfolio', {}).get('USDC', 0)
    positions = sim.get('positions', {})
    
    positions_data = []
    total_value = cash
    
    for symbol, pos in positions.items():
        # Find current price
        price = pos.get('avg_price', 0)
        for t in tokens:
            if t.get('symbol', '').upper() == symbol.upper():
                price = t.get('price', price)
                break
        
        value = pos.get('amount', 0) * price
        pnl_pct = ((price / pos['avg_price']) - 1) * 100 if pos.get('avg_price', 0) > 0 else 0
        total_value += value
        
        positions_data.append({
            'symbol': symbol,
            'amount': pos.get('amount', 0),
            'avg_price': pos.get('avg_price', 0),
            'current_price': price,
            'value': round(value, 2),
            'pnl_pct': round(pnl_pct, 2),
            'stop_loss': pos.get('stop_loss'),
            'tp1': pos.get('tp1'),
            'tp2': pos.get('tp2'),
            'entry_date': pos.get('entry_date')
        })
    
    # Output
    output = {
        'market': {
            'fear_greed': fg_val,
            'fear_greed_class': fg_class,
        },
        'config': {
            'mcap': mcap,
            'chain': chain,
            'profile': config.get('profile', 'moderate'),
            'max_positions': config.get('max_positions', 10),
            'provider': config.get('provider', 'openclaw'),
        },
        'portfolio': {
            'cash': round(cash, 2),
            'total_value': round(total_value, 2),
            'positions_count': len(positions),
            'exposure_pct': round((total_value - cash) / total_value * 100, 1) if total_value > 0 else 0,
        },
        'positions': positions_data,
        'candidates': [
            {
                'symbol': t.get('symbol'),
                'name': t.get('name'),
                'price': t.get('price'),
                'change_24h': t.get('price_change_24h'),
                'mcap': t.get('market_cap'),
            }
            for t in sorted_tokens[:20]  # Top 20 by momentum
        ]
    }
    
    print(json.dumps(output, indent=2))

if __name__ == '__main__':
    main()
