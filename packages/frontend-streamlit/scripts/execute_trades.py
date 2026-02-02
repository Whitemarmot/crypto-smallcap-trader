#!/usr/bin/env python3
"""
🎯 Execute Trades from Jean-Michel's Decisions
Takes JSON input with trade decisions and executes them.
Supports both paper trading (simulation) and real trading via 1inch.
"""

import json
import os
import sys
import argparse
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from utils.social_signals import get_tokens_by_market_cap_cmc

# Real trading imports
try:
    from utils.kyberswap import buy_token_kyber, KyberSwap
    from utils.wallet_keys import has_private_key, get_private_key
    REAL_TRADING_AVAILABLE = True
    SWAP_PROVIDER = "kyberswap"
except ImportError as e:
    try:
        from utils.real_trader import buy_token, sell_token
        from utils.wallet_keys import has_private_key
        REAL_TRADING_AVAILABLE = True
        SWAP_PROVIDER = "paraswap"
    except ImportError as e2:
        print(f"⚠️ Real trading not available: {e2}", file=sys.stderr)
        REAL_TRADING_AVAILABLE = False
        SWAP_PROVIDER = None

DATA_DIR = os.path.join(os.path.dirname(__file__), '..', 'data')
WALLETS_DIR = os.path.join(DATA_DIR, 'wallets')
WALLETS_CONFIG = os.path.join(WALLETS_DIR, 'config.json')
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
    avg_price = pos.get('avg_price', price)
    entry_date = pos.get('entry_date', '')
    
    # Calculate values
    entry_value = qty * avg_price
    exit_value = qty * price
    pnl_usd = exit_value - entry_value
    pnl_pct = ((price / avg_price) - 1) * 100 if avg_price > 0 else 0
    
    # Calculate holding duration
    holding_hours = 0
    if entry_date:
        try:
            entry_dt = datetime.fromisoformat(entry_date.replace('Z', '+00:00'))
            holding_hours = round((datetime.now() - entry_dt.replace(tzinfo=None)).total_seconds() / 3600, 1)
        except:
            pass
    
    # Add cash
    sim['portfolio']['USDC'] = sim.get('portfolio', {}).get('USDC', 0) + exit_value
    
    # Add to closed positions list
    if 'closed_positions' not in sim:
        sim['closed_positions'] = []
    
    closed_pos = {
        'symbol': symbol,
        'entry_date': entry_date,
        'exit_date': datetime.now().isoformat(),
        'holding_hours': holding_hours,
        'qty': qty,
        'entry_price': avg_price,
        'exit_price': price,
        'entry_value': round(entry_value, 2),
        'exit_value': round(exit_value, 2),
        'pnl_usd': round(pnl_usd, 2),
        'pnl_pct': round(pnl_pct, 2),
        'reason': reason,
        'stop_loss': pos.get('stop_loss'),
        'tp1': pos.get('tp1'),
        'tp2': pos.get('tp2'),
    }
    sim['closed_positions'].append(closed_pos)
    
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
        'usd': exit_value,
        'pnl_usd': round(pnl_usd, 2),
        'pnl_pct': round(pnl_pct, 2),
        'auto': True,
        'reason': reason,
    })
    
    pnl_emoji = "🟢" if pnl_usd >= 0 else "🔴"
    return True, f"Sold {qty:.4f} {symbol} @ ${price:.6f} = ${exit_value:.2f} | P&L: {pnl_emoji} ${pnl_usd:+.2f} ({pnl_pct:+.2f}%)"

def get_wallet_config(wallet_id: str) -> dict:
    """Get wallet configuration"""
    config = load_json(WALLETS_CONFIG, {'wallets': []})
    for w in config.get('wallets', []):
        if w['id'] == wallet_id:
            return w
    return {}


def execute_real_buy(wallet_cfg: dict, symbol: str, token_address: str, amount_usd: float) -> tuple:
    """Execute a real buy - tries multiple DEXes in sequence"""
    if not REAL_TRADING_AVAILABLE:
        return False, "Real trading module not available", None, 0
    
    address = wallet_cfg.get('address', '')
    chain = wallet_cfg.get('chain', 'base')
    
    if not address:
        return False, "Wallet has no address", None, 0
    
    if not has_private_key(address):
        return False, "No private key stored for this wallet", None, 0
    
    errors = []
    
    # 1. Try KyberSwap first (aggregator, best prices)
    if SWAP_PROVIDER == "kyberswap":
        try:
            success, msg, tx_hash, amount_out = buy_token_kyber(
                wallet_address=address,
                token_address=token_address,
                amount_usd=amount_usd,
                use_usdc=True,
            )
            if success:
                return True, f"[KyberSwap] {msg}", tx_hash, amount_out
            errors.append(f"KyberSwap: {msg}")
        except Exception as e:
            errors.append(f"KyberSwap: {str(e)}")
    
    # 2. Try Paraswap (aggregator)
    try:
        from utils.real_trader import buy_token
        success, msg, tx_hash = buy_token(
            chain=chain,
            wallet_address=address,
            token_symbol=symbol,
            token_address=token_address,
            amount_usd=amount_usd,
            use_aerodrome=False,  # Try Paraswap first
        )
        if success:
            return True, f"[Paraswap] {msg}", tx_hash, 0
        errors.append(f"Paraswap: {msg}")
    except Exception as e:
        errors.append(f"Paraswap: {str(e)}")
    
    # 3. Try Aerodrome directly (native Base DEX)
    try:
        from utils.real_trader import buy_token
        success, msg, tx_hash = buy_token(
            chain=chain,
            wallet_address=address,
            token_symbol=symbol,
            token_address=token_address,
            amount_usd=amount_usd,
            use_aerodrome=True,  # Force Aerodrome
        )
        if success:
            return True, f"[Aerodrome] {msg}", tx_hash, 0
        errors.append(f"Aerodrome: {msg}")
    except Exception as e:
        errors.append(f"Aerodrome: {str(e)}")
    
    # All DEXes failed
    return False, f"All DEXes failed: {'; '.join(errors)}", None, 0


def execute_real_sell(wallet_cfg: dict, symbol: str, token_address: str, amount: float, decimals: int = 18) -> tuple:
    """Execute a real sell via KyberSwap"""
    if not REAL_TRADING_AVAILABLE:
        return False, "Real trading module not available", None
    
    address = wallet_cfg.get('address', '')
    
    if not address:
        return False, "Wallet has no address", None
    
    if not has_private_key(address):
        return False, "No private key stored for this wallet", None
    
    # Use KyberSwap for selling (token -> USDC)
    if SWAP_PROVIDER == "kyberswap":
        private_key = get_private_key(address)
        kyber = KyberSwap(private_key)
        
        usdc = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"
        amount_wei = int(amount * (10 ** decimals))
        
        result = kyber.execute_swap(token_address, usdc, amount_wei)
        
        if result["success"]:
            usdc_out = int(result.get("amount_out", 0)) / 1e6
            return True, f"Sold {amount:.4f} {symbol} for ${usdc_out:.2f}", result["tx_hash"]
        else:
            return False, result.get("error", "Sell failed"), result.get("tx_hash")
    else:
        # Fallback
        from utils.real_trader import sell_token
        success, msg, tx_hash = sell_token(
            chain=wallet_cfg.get('chain', 'base'),
            wallet_address=address,
            token_symbol=symbol,
            token_address=token_address,
            amount=amount,
        )
        if tx_hash:
            msg += f" (tx: {tx_hash})"
        return success, msg, tx_hash


def main():
    parser = argparse.ArgumentParser(description='Execute trades from JSON decisions')
    parser.add_argument('--decisions', type=str, help='JSON string with decisions')
    parser.add_argument('--file', type=str, help='JSON file with decisions')
    parser.add_argument('--wallet', type=str, default='simulation', help='Wallet ID to use')
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
    
    # Get wallet config
    wallet_cfg = get_wallet_config(args.wallet)
    wallet_type = wallet_cfg.get('type', 'paper')
    is_real = wallet_type == 'real'
    
    # Load wallet data
    wallet_path = os.path.join(WALLETS_DIR, f'{args.wallet}.json')
    if not os.path.exists(wallet_path):
        wallet_path = SIM_PATH  # Fallback
    
    sim = load_json(wallet_path, {'portfolio': {'USDC': 10000}, 'positions': {}, 'history': []})
    
    print(f"🎯 Executing trades for wallet: {args.wallet} ({'REAL' if is_real else 'PAPER'})", file=sys.stderr)
    
    # Get current prices
    tokens = get_tokens_by_market_cap_cmc(0, float('inf'), limit=200)
    
    executed = []
    errors = []
    
    for d in decisions:
        action = d.get('action', '').upper()
        symbol = d.get('symbol', '').upper()
        token_address = d.get('token_address', '')  # For real trading
        
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
            
            if is_real and token_address:
                # Real trading via KyberSwap
                result = execute_real_buy(wallet_cfg, symbol, token_address, usd)
                success, msg = result[0], result[1]
                tx_hash = result[2] if len(result) > 2 else None
                amount_out = result[3] if len(result) > 3 else 0
                if success:
                    # Update local tracking with actual amount received
                    actual_price = usd / amount_out if amount_out > 0 else price
                    execute_buy(sim, symbol, usd, actual_price, stop_loss, tp1, tp2)
                    # Update position with token address for future sells
                    if symbol in sim.get('positions', {}):
                        sim['positions'][symbol]['token_address'] = token_address
                        sim['positions'][symbol]['amount'] = amount_out if amount_out > 0 else sim['positions'][symbol].get('amount', 0)
            else:
                # Paper trading
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
                    'real': is_real,
                })
                print(f"✅ BUY {symbol}: {msg}", file=sys.stderr)
            else:
                errors.append(f"BUY {symbol}: {msg}")
                print(f"❌ BUY {symbol}: {msg}", file=sys.stderr)
        
        elif action == 'SELL':
            reason = d.get('reason', '')
            
            if is_real and token_address:
                # Real trading - get amount from position
                pos = sim.get('positions', {}).get(symbol, {})
                amount = pos.get('amount', 0)
                # Get token address from position if available
                token_addr = pos.get('token_address', token_address)
                if amount > 0:
                    result = execute_real_sell(wallet_cfg, symbol, token_addr, amount)
                    success, msg = result[0], result[1]
                    if success:
                        # Also update local tracking
                        execute_sell(sim, symbol, price, reason)
                else:
                    success, msg = False, "No position to sell"
            else:
                # Paper trading
                success, msg = execute_sell(sim, symbol, price, reason)
            
            if success:
                executed.append({
                    'action': 'SELL',
                    'symbol': symbol,
                    'price': price,
                    'reason': reason,
                    'real': is_real,
                })
                print(f"✅ SELL {symbol}: {msg}", file=sys.stderr)
            else:
                errors.append(f"SELL {symbol}: {msg}")
                print(f"❌ SELL {symbol}: {msg}", file=sys.stderr)
    
    # Save wallet data
    save_json(wallet_path, sim)
    
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
