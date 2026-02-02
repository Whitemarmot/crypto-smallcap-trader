#!/usr/bin/env python3
"""
🤖 Auto-Trading Bot Script v3
- Money management intégré
- Logs détaillés avec TP/SL
- Position sizing basé sur valeur totale du wallet
"""

import json
import os
import sys
import time
import tempfile
import shutil
import fcntl
import requests
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
TAKE_PROFIT_PCT = 20    # +20% = vendre (fallback)
STOP_LOSS_PCT = -15     # -15% = vendre (fallback)

# Money Management
MAX_POSITION_PCT = 10       # Max 10% du portfolio par position
MAX_TOTAL_EXPOSURE_PCT = 80 # Max 80% investi (garder 20% cash)
MIN_TRADE_USD = 10          # Minimum $10 par trade

MCAP_PRESETS = {
    'micro': {'min': 0, 'max': 1_000_000},
    'small': {'min': 1_000_000, 'max': 100_000_000},
    'mid': {'min': 100_000_000, 'max': 1_000_000_000},
    'large': {'min': 1_000_000_000, 'max': float('inf')},
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
    if context:
        print(f"  → {json.dumps(context, default=str)}")
    
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
        ts = h.get('ts') or h.get('timestamp', '')
        if ts.startswith(today):
            count += 1
    return count


# Price cache to avoid rate limits
PRICE_CACHE = {}
PRICE_CACHE_TTL = 300  # 5 minutes

def get_price(symbol: str, tokens_data: list = None) -> float:
    """Get price from cached tokens data or CMC API"""
    global PRICE_CACHE
    symbol = symbol.upper()
    
    # Check cache first
    cached = PRICE_CACHE.get(symbol)
    if cached and (time.time() - cached['ts']) < PRICE_CACHE_TTL:
        return cached['price']
    
    # Check tokens_data if provided
    if tokens_data:
        for t in tokens_data:
            if t.get('symbol', '').upper() == symbol:
                price = t.get('price', 0)
                if price and price > 0:
                    PRICE_CACHE[symbol] = {'price': price, 'ts': time.time()}
                    return price
    
    # Fallback: Use CMC API directly (more reliable)
    try:
        cmc_key = os.getenv('CMC_API_KEY', '849ddcc694a049708d0b5392486d6eaa')
        resp = requests.get(
            'https://pro-api.coinmarketcap.com/v1/cryptocurrency/quotes/latest',
            headers={'X-CMC_PRO_API_KEY': cmc_key},
            params={'symbol': symbol, 'convert': 'USD'},
            timeout=10
        )
        data = resp.json()
        if 'data' in data and symbol in data['data']:
            price = data['data'][symbol]['quote']['USD']['price']
            if price and price > 0:
                PRICE_CACHE[symbol] = {'price': price, 'ts': time.time()}
                return price
    except Exception as e:
        log(f"CMC price error for {symbol}: {e}", "WARN")
    
    # Last resort: CoinGecko (may hit rate limits)
    try:
        maps = {
            'BTC': 'bitcoin', 'ETH': 'ethereum', 'SOL': 'solana',
            'PEPE': 'pepe', 'DOGE': 'dogecoin', 'XRP': 'ripple',
            'BRETT': 'brett', 'XVG': 'verge', 'SUI': 'sui',
            'ZRX': '0x', 'YFI': 'yearn-finance', 'KSM': 'kusama',
        }
        cg_id = maps.get(symbol, symbol.lower())
        time.sleep(1)  # Rate limit protection
        r = requests.get(
            'https://api.coingecko.com/api/v3/simple/price',
            params={'ids': cg_id, 'vs_currencies': 'usd'},
            timeout=10
        )
        if r.status_code == 200:
            price = r.json().get(cg_id, {}).get('usd', 0)
            if price and price > 0:
                PRICE_CACHE[symbol] = {'price': price, 'ts': time.time()}
                return price
    except:
        pass
    
    return 0


def calculate_portfolio_value(sim, tokens_data: list = None) -> dict:
    """Calculate total portfolio value"""
    usd = sim['portfolio'].get('USD', 0)
    positions_value = 0
    position_details = {}
    
    for symbol, pos in sim.get('positions', {}).items():
        price = get_price(symbol, tokens_data)
        # Use avg_price as fallback if can't get current price
        if price <= 0:
            price = pos['avg_price']
        value = pos['amount'] * price
        positions_value += value
        pnl_pct = ((price / pos['avg_price']) - 1) * 100 if pos['avg_price'] > 0 and price > 0 else 0
        position_details[symbol] = {
            'value': value,
            'price': price,
            'pnl_pct': pnl_pct
        }
    
    return {
        'cash': usd,
        'positions_value': positions_value,
        'total': usd + positions_value,
        'exposure_pct': (positions_value / (usd + positions_value)) * 100 if (usd + positions_value) > 0 else 0,
        'details': position_details
    }


def calculate_position_size(portfolio_value: float, existing_position_value: float = 0) -> float:
    """Calculate optimal position size based on money management rules"""
    max_position = portfolio_value * (MAX_POSITION_PCT / 100)
    available = max_position - existing_position_value
    return max(0, min(available, portfolio_value * 0.05))  # 5% par trade par défaut


def check_positions_for_sell(sim, fg_val, tokens_data: list = None):
    """Check existing positions for take profit or stop loss (using AI levels)"""
    sells = []
    for symbol, pos in list(sim.get('positions', {}).items()):
        current_price = get_price(symbol, tokens_data)
        if current_price <= 0:
            log(f"⚠️ Cannot get price for {symbol}, using avg_price", "WARN")
            current_price = pos.get('avg_price', 0)
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
        
        log(f"📊 {symbol}: ${current_price:.4f} (entry: ${avg_price:.4f}, PnL: {pnl_pct:+.1f}%) SL:{stop_loss} TP1:{tp1} TP2:{tp2}")
        
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
        # TP1 hit (for now, full exit - TODO: partial)
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
        log(f"❌ Cannot buy {symbol}: USD={sim['portfolio'].get('USD',0):.2f}, price={price}", "WARN")
        return False
    
    sim['portfolio']['USD'] -= amount_usd
    qty = amount_usd / price
    
    if symbol in sim['positions']:
        p = sim['positions'][symbol]
        total = p['amount'] + qty
        new_avg = ((p['amount'] * p['avg_price']) + amount_usd) / total
        sim['positions'][symbol] = {
            'amount': total, 
            'avg_price': new_avg,
            'stop_loss': stop_loss or p.get('stop_loss'),
            'tp1': tp1 or p.get('tp1'),
            'tp2': tp2 or p.get('tp2'),
            'entry_date': p.get('entry_date', ts)
        }
    else:
        sim['positions'][symbol] = {
            'amount': qty, 
            'avg_price': price,
            'stop_loss': stop_loss, 
            'tp1': tp1, 
            'tp2': tp2,
            'entry_date': ts
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
    log("🤖 Bot v3 starting...")
    
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
        
        # Get tokens early to use for price lookups
        tokens = get_tokens_by_market_cap(mcap['min'], mcap['max'], limit=50)
        
        # Pre-populate price cache with token data
        for t in tokens:
            sym = t.get('symbol', '').upper()
            price = t.get('price', 0)
            if sym and price and price > 0:
                PRICE_CACHE[sym] = {'price': price, 'ts': time.time()}
        
        # Also fetch prices for existing positions
        for symbol in sim.get('positions', {}).keys():
            if symbol.upper() not in PRICE_CACHE:
                get_price(symbol.upper(), tokens)  # This will try CMC
        
        # Calculate portfolio value
        portfolio = calculate_portfolio_value(sim, tokens)
        log(f"💰 Portfolio: ${portfolio['total']:.2f} (Cash: ${portfolio['cash']:.2f}, Positions: ${portfolio['positions_value']:.2f}, Exposure: {portfolio['exposure_pct']:.1f}%)")
        
        # Get Fear & Greed
        fg = get_fear_greed_index()
        fg_val = fg.value if fg else 50
        log(f"😱 Fear & Greed: {fg_val}")
        
        executed = []
        
        # === SELL LOGIC ===
        sells = check_positions_for_sell(sim, fg_val, tokens)
        for sell in sells:
            if execute_sell(sim, sell['symbol'], sell['price'], sell['reason']):
                log(f"🔴 SELL {sell['symbol']} - {sell['reason']}", "INFO", sell)
                executed.append(f"SELL:{sell['symbol']}")
        
        # Refresh portfolio after sells
        portfolio = calculate_portfolio_value(sim, tokens)
        
        # === BUY LOGIC ===
        if portfolio['cash'] < MIN_TRADE_USD:
            log(f"Low cash (${portfolio['cash']:.2f}), skipping buys", "INFO")
        elif portfolio['exposure_pct'] >= MAX_TOTAL_EXPOSURE_PCT:
            log(f"Max exposure reached ({portfolio['exposure_pct']:.1f}%), skipping buys", "INFO")
        else:
            # Tokens already fetched above
            if not tokens:
                log("No tokens found", "WARN")
            else:
                log(f"Found {len(tokens)} tokens")
                
                # Build prompt
                token_list = "\n".join([
                    f"- {t['symbol']}: ${t.get('price',0):.6f} | 24h: {t.get('price_change_24h',0) or 0:+.1f}% | MCap: ${(t.get('market_cap',0) or 0)/1e6:.1f}M"
                    for t in tokens[:15]
                ])
                
                prompt = f"""Tu es un trader crypto expert. Analyse et donne tes décisions de trading.

MARCHÉ: Fear & Greed = {fg_val}/100 {'(EXTREME FEAR - opportunité?)' if fg_val < 25 else ''}
CHAIN: {chain}
PROFIL: {profile_key.upper()} (score min: {profile.min_score})

TOKENS ({mcap_key} cap, ${mcap['min']/1e6:.0f}M - ${mcap['max']/1e6:.0f}M):
{token_list}

INSTRUCTIONS IMPORTANTES:
1. Analyse la tendance 24h de chaque token
2. Pour chaque BUY, DONNE OBLIGATOIREMENT les niveaux en PRIX (pas en %):
   - stop_loss: prix de protection (environ -10% à -15% du prix actuel)
   - tp1: premier objectif (environ +15% à +25%)
   - tp2: objectif ambitieux (environ +40% à +60%)
3. Confidence doit être >= {profile.min_score}
4. Max 3 décisions

Réponds UNIQUEMENT avec un JSON array valide:
[{{"symbol": "XXX", "action": "BUY", "confidence": 75, "stop_loss": 0.0045, "tp1": 0.0058, "tp2": 0.0072, "reason": "..."}}]

Si aucune opportunité intéressante, réponds: []
"""
                
                # Call AI
                log(f"🧠 Calling {provider}...")
                model = LLM_MODELS.get(provider, {}).get('default', 'openclaw:main')
                response = call_llm(prompt, provider, model)
                
                if response:
                    # Parse response
                    import re
                    try:
                        match = re.search(r'\[.*\]', response, re.DOTALL)
                        decisions = json.loads(match.group()) if match else []
                    except Exception as e:
                        decisions = []
                        log(f"Parse error: {e}", "ERROR")
                        log(f"Raw response: {response[:500]}", "DEBUG")
                    
                    log(f"📋 Got {len(decisions)} decisions")
                    
                    # Log each decision
                    for i, d in enumerate(decisions):
                        log(f"  Decision {i+1}: {d.get('action')} {d.get('symbol')} @ confidence {d.get('confidence')}% | SL:{d.get('stop_loss')} TP1:{d.get('tp1')} TP2:{d.get('tp2')}", "DEBUG", d)
                    
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
                        
                        log(f"🔍 Evaluating {sym}: action={act}, confidence={conf}, min_score={profile.min_score}")
                        
                        if act == 'BUY' and conf >= profile.min_score:
                            price = get_price(sym, tokens)
                            log(f"💵 Price for {sym}: ${price:.6f}")
                            
                            if price <= 0:
                                log(f"❌ Cannot get price for {sym}, skipping", "WARN")
                                continue
                            
                            # Money management: calculate position size
                            existing_value = portfolio['details'].get(sym, {}).get('value', 0)
                            max_amount = calculate_position_size(portfolio['total'], existing_value)
                            amount = min(max_amount, portfolio['cash'] * (profile.trade_amount_pct / 100))
                            
                            log(f"💰 Position sizing: max={max_amount:.2f}, profile_pct={profile.trade_amount_pct}%, final={amount:.2f}")
                            
                            if amount >= MIN_TRADE_USD:
                                if execute_buy(sim, sym, amount, price, stop_loss, tp1, tp2):
                                    levels = ""
                                    if stop_loss:
                                        levels = f" | SL:${stop_loss:.4f} TP1:${tp1:.4f} TP2:${tp2:.4f}"
                                    log(f"🟢 BUY {sym} ${amount:.2f} @ ${price:.6f} ({conf}%){levels}", "INFO", d)
                                    log(f"   Reason: {reason}")
                                    executed.append(f"BUY:{sym}")
                                    portfolio['cash'] -= amount
                            else:
                                log(f"⚠️ Amount too small: ${amount:.2f} < ${MIN_TRADE_USD}", "WARN")
                        else:
                            if act == 'BUY':
                                log(f"⚠️ {sym} rejected: confidence {conf} < {profile.min_score}", "INFO")
                else:
                    log("No AI response", "ERROR")
        
        # Save state
        save_json_atomic(SIM_DB_PATH, sim)
        save_json_atomic(STATE_PATH, {
            'last_run': datetime.now().isoformat(),
            'last_result': {'executed': executed}
        })
        
        log(f"✅ Done. Executed: {executed or 'none'}")
        return {'status': 'ok', 'executed': executed}
    
    finally:
        release_lock(lock)


if __name__ == '__main__':
    result = run_bot()
    print(json.dumps(result, indent=2))
