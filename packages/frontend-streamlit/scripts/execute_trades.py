#!/usr/bin/env python3
"""
🎯 Execute Trades from Jean-Michel's Decisions
Takes JSON input with trade decisions and executes them.
"""

import json
import os
import sys
import argparse
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from utils.social_signals import get_tokens_by_market_cap_cmc

DATA_DIR = os.path.join(os.path.dirname(__file__), '..', 'data')
SIM_PATH = os.path.join(DATA_DIR, 'simulation.json')

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

def get_price(symbol, tokens=None):
    """Get current price for a symbol"""
    if tokens:
        for t in tokens:
            if t.get('symbol', '').upper() == symbol.upper():
                return t.get('price', 0)
    # Fallback: fetch from CMC
    try:
        import requests
        cmc_key = os.getenv('CMC_API_KEY', '849ddcc694a049708d0b5392486d6eaa')
        resp = requests.get(
            'https://pro-api.coinmarketcap.com/v1/cryptocurrency/quotes/latest',
            headers={'X-CMC_PRO_API_KEY': cmc_key},
            params={'symbol': symbol.upper(), 'convert': 'USD'},
            timeout=10
        )
        data = resp.json()
        if 'data' in data and symbol.upper() in data['data']:
            return data['data'][symbol.upper()]['quote']['USD']['price']
    except:
        pass
    return 0

def execute_buy(sim, symbol, usd_amount, price, stop_loss=None, tp1=None, tp2=None):
    """Execute a buy order"""
    if price <= 0:
        return False, "Invalid price"
    
    cash = sim.get('portfolio', {}).get('USDC', 0)
    if usd_amount > cash:
        return False, f"Insufficient cash (${cash:.2f} < ${usd_amount:.2f})"
    
    qty = usd_amount / price
    
    # Update or create position
    if 'positions' not in sim:
        sim['positions'] = {}
    
    if symbol in sim['positions']:
        # Average into existing position
        pos = sim['positions'][symbol]
        total_qty = pos['amount'] + qty
        total_cost = (pos['amount'] * pos['avg_price']) + (qty * price)
        pos['amount'] = total_qty
        pos['avg_price'] = total_cost / total_qty
        if stop_loss:
            pos['stop_loss'] = stop_loss
        if tp1:
            pos['tp1'] = tp1
        if tp2:
            pos['tp2'] = tp2
    else:
        sim['positions'][symbol] = {
            'amount': qty,
            'avg_price': price,
            'entry_date': datetime.now().isoformat(),
            'stop_loss': stop_loss,
            'tp1': tp1,
            'tp2': tp2,
        }
    
    # Deduct cash
    sim['portfolio']['USDC'] = cash - usd_amount
    
    # Add to history
    if 'history' not in sim:
        sim['history'] = []
    sim['history'].append({
        'ts': datetime.now().isoformat(),
        'action': 'BUY',
        'symbol': symbol,
        'qty': qty,
        'price': price,
        'usd': usd_amount,
        'auto': True,
        'stop_loss': stop_loss,
        'tp1': tp1,
        'tp2': tp2,
    })
    
    return True, f"Bought {qty:.4f} {symbol} @ ${price:.6f}"

def execute_sell(sim, symbol, price, reason=""):
    """Execute a sell order"""
    if symbol not in sim.get('positions', {}):
        return False, f"No position in {symbol}"
    
    pos = sim['positions'][symbol]
    qty = pos['amount']
    usd_value = qty * price
    
    # Add cash
    sim['portfolio']['USDC'] = sim.get('portfolio', {}).get('USDC', 0) + usd_value
    
    # Remove position
    del sim['positions'][symbol]
    
    # Add to history
    if 'history' not in sim:
        sim['history'] = []
    sim['history'].append({
        'ts': datetime.now().isoformat(),
        'action': 'SELL',
        'symbol': symbol,
        'qty': qty,
        'price': price,
        'usd': usd_value,
        'auto': True,
        'reason': reason,
    })
    
    return True, f"Sold {qty:.4f} {symbol} @ ${price:.6f} = ${usd_value:.2f}"

def main():
    parser = argparse.ArgumentParser(description='Execute trades from JSON decisions')
    parser.add_argument('--decisions', type=str, help='JSON string with decisions')
    parser.add_argument('--file', type=str, help='JSON file with decisions')
    args = parser.parse_args()
    
    # Get decisions
    if args.file:
        decisions = load_json(args.file, [])
    elif args.decisions:
        decisions = json.loads(args.decisions)
    else:
        # Read from stdin
        decisions = json.loads(sys.stdin.read())
    
    if not decisions:
        print(json.dumps({'status': 'ok', 'message': 'No decisions to execute', 'executed': []}))
        return
    
    # Load simulation
    sim = load_json(SIM_PATH, {'portfolio': {'USDC': 10000}, 'positions': {}, 'history': []})
    
    # Get current prices
    tokens = get_tokens_by_market_cap_cmc(0, float('inf'), limit=200)
    
    executed = []
    errors = []
    
    for d in decisions:
        action = d.get('action', '').upper()
        symbol = d.get('symbol', '').upper()
        
        if not symbol:
            continue
        
        price = get_price(symbol, tokens)
        if price <= 0:
            errors.append(f"Could not get price for {symbol}")
            continue
        
        if action == 'BUY':
            usd = d.get('amount_usd', 500)  # Default $500
            stop_loss = d.get('stop_loss')
            tp1 = d.get('tp1')
            tp2 = d.get('tp2')
            
            success, msg = execute_buy(sim, symbol, usd, price, stop_loss, tp1, tp2)
            if success:
                executed.append({
                    'action': 'BUY',
                    'symbol': symbol,
                    'amount_usd': usd,
                    'price': price,
                    'stop_loss': stop_loss,
                    'tp1': tp1,
                    'tp2': tp2,
                })
            else:
                errors.append(f"BUY {symbol}: {msg}")
        
        elif action == 'SELL':
            reason = d.get('reason', '')
            success, msg = execute_sell(sim, symbol, price, reason)
            if success:
                executed.append({
                    'action': 'SELL',
                    'symbol': symbol,
                    'price': price,
                    'reason': reason,
                })
            else:
                errors.append(f"SELL {symbol}: {msg}")
    
    # Save
    save_json(SIM_PATH, sim)
    
    # Output result
    result = {
        'status': 'ok',
        'executed': executed,
        'errors': errors,
        'portfolio': {
            'cash': round(sim['portfolio'].get('USDC', 0), 2),
            'positions': len(sim.get('positions', {})),
        }
    }
    print(json.dumps(result, indent=2))

if __name__ == '__main__':
    main()
