#!/usr/bin/env python3
"""
🤖 Auto-Trading Bot Script v2
Amélioré avec les suggestions de Kempfr (Dev Lead)
- Lock file, rate limiting, SELL logic, max trades, atomic writes
"""

import json
import os
import sys
import time
import tempfile
import shutil
import fcntl
from datetime import datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from utils.social_signals import get_fear_greed_index, get_tokens_by_market_cap
from utils.config import AI_PROFILES
from utils.llm_providers import call_llm, LLM_MODELS

# Paths
DATA_DIR = os.path.join(os.path.dirname(__file__), '..', 'data')
SIM_DB_PATH = os.path.join(DATA_DIR, 'simulation.json')
BOT_CONFIG_PATH = os.path.join(DATA_DIR, 'bot_config.json')
LOG_PATH = os.path.join(DATA_DIR, 'bot_log.json')
LOCK_PATH = os.path.join(DATA_DIR, 'bot.lock')
STATE_PATH = os.path.join(DATA_DIR, 'bot_state.json')

# Config
COOLDOWN_SECONDS = 300  # 5 min minimum entre runs
MAX_DAILY_TRADES = 10
TAKE_PROFIT_PCT = 20  # +20% = vendre
STOP_LOSS_PCT = -15   # -15% = vendre

MCAP_PRESETS = {
    'micro': {'min': 0, 'max': 1_000_000},
    'small': {'min': 1_000_000, 'max': 100_000_000},
    'mid': {'min': 100_000_000, 'max': 1_000_000_000},
    'large': {'min': 1_000_000_000, 'max': float('inf')},  # Fixed!
}


def load_json(path, default):
    try:
        if os.path.exists(path):
            with open(path, 'r') as f:
                return json.load(f)
    except:
        pass
    return default


def save_json_atomic(path, data):
    """Atomic write to avoid corruption"""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with tempfile.NamedTemporaryFile('w', dir=os.path.dirname(path), delete=False) as tmp:
        json.dump(data, tmp, indent=2, default=str)
        tmp_path = tmp.name
    shutil.move(tmp_path, path)


def log(msg, level="INFO", context=None):
    """Structured logging"""
    ts = datetime.now().isoformat()
    entry = {
        'ts': ts,
        'level': level,
        'msg': msg,
        'context': context or {}
    }
    print(f"[{ts}] [{level}] {msg}")
    
    logs = load_json(LOG_PATH, [])
    logs.append(entry)
    logs = logs[-200:]  # Keep last 200
    save_json_atomic(LOG_PATH, logs)


def acquire_lock():
    """Prevent concurrent execution"""
    try:
        lock_file = open(LOCK_PATH, 'w')
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        lock_file.write(str(os.getpid()))
        lock_file.flush()
        return lock_file
    except (IOError, OSError):
        return None


def release_lock(lock_file):
    """Release lock"""
    if lock_file:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
        lock_file.close()
        try:
            os.remove(LOCK_PATH)
        except:
            pass


def check_cooldown():
    """Check if enough time passed since last run"""
    state = load_json(STATE_PATH, {})
    last_run = state.get('last_run')
    if last_run:
        last_dt = datetime.fromisoformat(last_run)
        elapsed = (datetime.now() - last_dt).total_seconds()
        if elapsed < COOLDOWN_SECONDS:
            return False, COOLDOWN_SECONDS - elapsed
    return True, 0


def get_daily_trade_count():
    """Count trades today"""
    sim = load_json(SIM_DB_PATH, {})
    today = datetime.now().date().isoformat()
    count = 0
    for h in sim.get('history', []):
        if h.get('ts', '').startswith(today):
            count += 1
    return count


def get_price(symbol: str) -> float:
    """Get current price from CoinGecko with fallback search"""
    import requests
    try:
        # Extended mappings
        maps = {
            'BTC': 'bitcoin', 'ETH': 'ethereum', 'SOL': 'solana',
            'PEPE': 'pepe', 'DOGE': 'dogecoin', 'XRP': 'ripple',
            'ADA': 'cardano', 'AVAX': 'avalanche-2', 'LINK': 'chainlink',
            'DOT': 'polkadot', 'MATIC': 'matic-network', 'SHIB': 'shiba-inu',
            'UNI': 'uniswap', 'ATOM': 'cosmos', 'LTC': 'litecoin',
            'BRETT': 'brett', 'XVG': 'verge', 'SUI': 'sui',
            'ARB': 'arbitrum', 'OP': 'optimism', 'APT': 'aptos',
            'INJ': 'injective-protocol', 'SEI': 'sei-network',
            'WIF': 'dogwifcoin', 'BONK': 'bonk', 'FLOKI': 'floki',
            'YFI': 'yearn-finance', 'KSM': 'kusama', 'ZRX': '0x',
            'CKB': 'nervos-network', 'RVN': 'ravencoin', 'CORE': 'coredaoorg',
        }
        cg_id = maps.get(symbol.upper(), symbol.lower())
        
        r = requests.get(
            'https://api.coingecko.com/api/v3/simple/price',
            params={'ids': cg_id, 'vs_currencies': 'usd'},
            timeout=10
        )
        price = r.json().get(cg_id, {}).get('usd', 0)
        
        # Fallback: search if not found
        if price == 0:
            search = requests.get(
                'https://api.coingecko.com/api/v3/search',
                params={'query': symbol},
                timeout=10
            )
            coins = search.json().get('coins', [])
            if coins:
                cg_id = coins[0]['id']
                r = requests.get(
                    'https://api.coingecko.com/api/v3/simple/price',
                    params={'ids': cg_id, 'vs_currencies': 'usd'},
                    timeout=10
                )
                price = r.json().get(cg_id, {}).get('usd', 0)
        
        return price
    except Exception as e:
        log(f"Price fetch error: {e}", "WARN")
        return 0


def check_positions_for_sell(sim, fg_val):
    """Check existing positions for take profit or stop loss (using AI levels)"""
    sells = []
    for symbol, pos in list(sim.get('positions', {}).items()):
        current_price = get_price(symbol)
        if current_price <= 0:
            continue
        
        avg_price = pos.get('avg_price', 0)
        if avg_price <= 0:
            continue
        
        pnl_pct = ((current_price / avg_price) - 1) * 100
        
        # Get AI-defined levels or use defaults
        stop_loss = pos.get('stop_loss')
        tp1 = pos.get('tp1')
        tp2 = pos.get('tp2')
        
        # Stop loss hit
        if stop_loss and current_price <= stop_loss:
            sells.append({
                'symbol': symbol,
                'reason': f'🛑 stop_loss @ ${stop_loss:.4f} ({pnl_pct:.1f}%)',
                'price': current_price,
                'pnl_pct': pnl_pct
            })
        # TP2 hit (full exit)
        elif tp2 and current_price >= tp2:
            sells.append({
                'symbol': symbol,
                'reason': f'🎯 tp2 @ ${tp2:.4f} ({pnl_pct:.1f}%)',
                'price': current_price,
                'pnl_pct': pnl_pct
            })
        # TP1 hit (partial exit - TODO: implement partial sells)
        elif tp1 and current_price >= tp1:
            sells.append({
                'symbol': symbol,
                'reason': f'🎯 tp1 @ ${tp1:.4f} ({pnl_pct:.1f}%)',
                'price': current_price,
                'pnl_pct': pnl_pct
            })
        # Fallback: percentage-based (if no AI levels)
        elif not stop_loss and not tp1:
            if pnl_pct >= TAKE_PROFIT_PCT:
                sells.append({
                    'symbol': symbol,
                    'reason': f'take_profit ({pnl_pct:.1f}%)',
                    'price': current_price,
                    'pnl_pct': pnl_pct
                })
            elif pnl_pct <= STOP_LOSS_PCT:
                sells.append({
                    'symbol': symbol,
                    'reason': f'stop_loss ({pnl_pct:.1f}%)',
                    'price': current_price,
                    'pnl_pct': pnl_pct
                })
        # Extreme fear + loss = cut
        if fg_val < 20 and pnl_pct < -5 and symbol not in [s['symbol'] for s in sells]:
            sells.append({
                'symbol': symbol,
                'reason': f'😰 extreme_fear_exit ({pnl_pct:.1f}%)',
                'price': current_price,
                'pnl_pct': pnl_pct
            })
    
    return sells


def execute_buy(sim, symbol, amount_usd, price, stop_loss=None, tp1=None, tp2=None):
    """Execute a BUY trade with TP/SL levels"""
    ts = datetime.now().isoformat()
    if sim['portfolio'].get('USD', 0) < amount_usd or price <= 0:
        return False
    
    sim['portfolio']['USD'] -= amount_usd
    qty = amount_usd / price
    
    if symbol in sim['positions']:
        p = sim['positions'][symbol]
        total = p['amount'] + qty
        new_avg = ((p['amount'] * p['avg_price']) + amount_usd) / total
        sim['positions'][symbol] = {
            'amount': total, 'avg_price': new_avg,
            'stop_loss': stop_loss or p.get('stop_loss'),
            'tp1': tp1 or p.get('tp1'),
            'tp2': tp2 or p.get('tp2')
        }
    else:
        sim['positions'][symbol] = {
            'amount': qty, 'avg_price': price,
            'stop_loss': stop_loss, 'tp1': tp1, 'tp2': tp2
        }
    
    sim['history'].append({
        'ts': ts, 'action': 'BUY', 'symbol': symbol,
        'qty': qty, 'price': price, 'usd': amount_usd, 'auto': True,
        'stop_loss': stop_loss, 'tp1': tp1, 'tp2': tp2
    })
    return True


def execute_sell(sim, symbol, price, reason):
    """Execute a SELL trade"""
    ts = datetime.now().isoformat()
    if symbol not in sim['positions'] or price <= 0:
        return False
    
    pos = sim['positions'][symbol]
    qty = pos['amount']
    usd_value = qty * price
    pnl = (price - pos['avg_price']) * qty
    
    sim['portfolio']['USD'] += usd_value
    del sim['positions'][symbol]
    
    sim['history'].append({
        'ts': ts, 'action': 'SELL', 'symbol': symbol,
        'qty': qty, 'price': price, 'usd': usd_value,
        'pnl': pnl, 'reason': reason, 'auto': True
    })
    return True


def run_bot():
    """Main bot execution"""
    log("🤖 Bot v2 starting...")
    
    # Acquire lock
    lock = acquire_lock()
    if not lock:
        log("Another instance running, exiting", "WARN")
        return {'status': 'locked'}
    
    try:
        # Check cooldown
        can_run, wait_time = check_cooldown()
        if not can_run:
            log(f"Cooldown active, wait {wait_time:.0f}s", "INFO")
            return {'status': 'cooldown', 'wait': wait_time}
        
        # Check daily limit
        daily_trades = get_daily_trade_count()
        if daily_trades >= MAX_DAILY_TRADES:
            log(f"Max daily trades reached ({daily_trades})", "INFO")
            return {'status': 'max_trades', 'count': daily_trades}
        
        # Load config
        cfg = load_json(BOT_CONFIG_PATH, {})
        if not cfg.get('enabled'):
            log("Bot disabled")
            return {'status': 'disabled'}
        
        mcap_key = cfg.get('mcap', 'small')
        chain = cfg.get('chain', 'base')
        profile_key = cfg.get('profile', 'modere')
        provider = cfg.get('provider', 'openclaw')
        
        mcap = MCAP_PRESETS.get(mcap_key, MCAP_PRESETS['small'])
        profile = AI_PROFILES.get(profile_key, AI_PROFILES['modere'])
        
        log(f"Config: {mcap_key}/{chain}/{profile_key}/{provider}")
        
        # Load simulation
        sim = load_json(SIM_DB_PATH, {'portfolio': {'USD': 10000}, 'positions': {}, 'history': []})
        usd = sim['portfolio'].get('USD', 0)
        
        # Get Fear & Greed
        fg = get_fear_greed_index()
        fg_val = fg.value if fg else 50
        log(f"Fear & Greed: {fg_val}")
        
        executed = []
        
        # === SELL LOGIC ===
        sells = check_positions_for_sell(sim, fg_val)
        for sell in sells:
            if execute_sell(sim, sell['symbol'], sell['price'], sell['reason']):
                log(f"🔴 SELL {sell['symbol']} - {sell['reason']}", "INFO", sell)
                executed.append(f"SELL:{sell['symbol']}")
        
        # === BUY LOGIC ===
        if usd < 50:
            log("Low USD, skipping buys", "INFO")
        else:
            # Get tokens
            tokens = get_tokens_by_market_cap(mcap['min'], mcap['max'], limit=20)
            if not tokens:
                log("No tokens found", "WARN")
            else:
                log(f"Found {len(tokens)} tokens")
                
                # Build prompt
                token_list = "\n".join([
                    f"- {t['symbol']}: ${t.get('price',0):.4f} | 24h: {t.get('price_change_24h',0) or 0:+.1f}% | MCap: ${(t.get('market_cap',0) or 0)/1e6:.1f}M"
                    for t in tokens[:15]
                ])
                
                prompt = f"""Tu es un trader crypto expert. Analyse et donne tes décisions de trading.

MARCHÉ: Fear & Greed = {fg_val}/100
CHAIN: {chain}
PROFIL: {profile_key.upper()} (score min: {profile.min_score})

TOKENS:
{token_list}

INSTRUCTIONS:
- Analyse chaque token et donne des décisions BUY pour les meilleurs (max 3)
- Pour chaque BUY, donne les niveaux de sortie:
  • stop_loss: prix de vente si ça baisse (protection)
  • tp1: premier take profit (sortie partielle recommandée)
  • tp2: second take profit (objectif optimiste)
- Confidence doit être >= {profile.min_score}

Réponds UNIQUEMENT avec un JSON array:
[{{"symbol": "XXX", "action": "BUY", "confidence": 75, "stop_loss": 0.0045, "tp1": 0.0058, "tp2": 0.0072, "reason": "..."}}]

Si rien d'intéressant: []
"""
                
                # Call AI
                log(f"Calling {provider}...")
                model = LLM_MODELS.get(provider, {}).get('default', 'openclaw:main')
                response = call_llm(prompt, provider, model)
                
                if response:
                    # Parse response
                    import re
                    try:
                        match = re.search(r'\[.*\]', response, re.DOTALL)
                        decisions = json.loads(match.group()) if match else []
                    except:
                        decisions = []
                        log("Parse error", "ERROR")
                    
                    log(f"Got {len(decisions)} decisions")
                    
                    # Execute buys
                    remaining_trades = MAX_DAILY_TRADES - daily_trades - len(executed)
                    for d in decisions[:remaining_trades]:
                        sym = d.get('symbol', '?')
                        act = d.get('action', 'HOLD')
                        conf = d.get('confidence', 0)
                        reason = d.get('reason', '')
                        stop_loss = d.get('stop_loss')
                        tp1 = d.get('tp1')
                        tp2 = d.get('tp2')
                        
                        if act == 'BUY' and conf >= profile.min_score:
                            price = get_price(sym)
                            amount = usd * (profile.trade_amount_pct / 100)
                            if amount >= 10 and price > 0:
                                if execute_buy(sim, sym, amount, price, stop_loss, tp1, tp2):
                                    levels = f"SL:${stop_loss:.4f} TP1:${tp1:.4f} TP2:${tp2:.4f}" if stop_loss else ""
                                    log(f"🟢 BUY {sym} @ ${price:.4f} ({conf}%) {levels}: {reason}", "INFO", d)
                                    executed.append(f"BUY:{sym}")
                                    usd -= amount
                else:
                    log("No AI response", "ERROR")
        
        # Save state
        save_json_atomic(SIM_DB_PATH, sim)
        save_json_atomic(STATE_PATH, {
            'last_run': datetime.now().isoformat(),
            'last_result': {'executed': executed}
        })
        
        log(f"Done. Executed: {executed or 'none'}")
        return {'status': 'ok', 'executed': executed}
    
    finally:
        release_lock(lock)


if __name__ == '__main__':
    result = run_bot()
    print(json.dumps(result, indent=2))
