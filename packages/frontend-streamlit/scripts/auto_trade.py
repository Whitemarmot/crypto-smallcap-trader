#!/usr/bin/env python3
"""
🤖 Auto-Trading Bot Script
Lit la config, analyse, trade automatiquement
Appelé par cron ou manuellement
"""

import json
import os
import sys
from datetime import datetime

# Add parent to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from utils.social_signals import get_fear_greed_index, get_tokens_by_market_cap
from utils.config import AI_PROFILES
from utils.llm_providers import call_llm, LLM_MODELS

# Paths
DATA_DIR = os.path.join(os.path.dirname(__file__), '..', 'data')
SIM_DB_PATH = os.path.join(DATA_DIR, 'simulation.json')
BOT_CONFIG_PATH = os.path.join(DATA_DIR, 'bot_config.json')
LOG_PATH = os.path.join(DATA_DIR, 'bot_log.json')

MCAP_PRESETS = {
    'micro': {'min': 0, 'max': 1_000_000},
    'small': {'min': 1_000_000, 'max': 100_000_000},
    'mid': {'min': 100_000_000, 'max': 1_000_000_000},
    'large': {'min': 1_000_000_000, 'max': 0},
}


def load_json(path, default):
    if os.path.exists(path):
        with open(path, 'r') as f:
            return json.load(f)
    return default


def save_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w') as f:
        json.dump(data, f, indent=2, default=str)


def log(msg, level="INFO"):
    ts = datetime.now().isoformat()
    print(f"[{ts}] [{level}] {msg}")
    
    # Append to log file
    logs = load_json(LOG_PATH, [])
    logs.append({'ts': ts, 'level': level, 'msg': msg})
    logs = logs[-100:]  # Keep last 100
    save_json(LOG_PATH, logs)


def get_price(symbol: str) -> float:
    import requests
    try:
        maps = {'BTC': 'bitcoin', 'ETH': 'ethereum', 'SOL': 'solana', 'PEPE': 'pepe', 'DOGE': 'dogecoin'}
        cg_id = maps.get(symbol.upper(), symbol.lower())
        r = requests.get(f'https://api.coingecko.com/api/v3/simple/price', params={'ids': cg_id, 'vs_currencies': 'usd'}, timeout=10)
        return r.json().get(cg_id, {}).get('usd', 0)
    except:
        return 0


def trade(sim, action, symbol, amount_usd, price):
    ts = datetime.now().isoformat()
    if action == 'BUY' and sim['portfolio'].get('USD', 0) >= amount_usd and price > 0:
        sim['portfolio']['USD'] -= amount_usd
        qty = amount_usd / price
        if symbol in sim['positions']:
            p = sim['positions'][symbol]
            total = p['amount'] + qty
            sim['positions'][symbol] = {'amount': total, 'avg_price': ((p['amount']*p['avg_price'])+amount_usd)/total}
        else:
            sim['positions'][symbol] = {'amount': qty, 'avg_price': price}
        sim['history'].append({'ts': ts, 'action': 'BUY', 'symbol': symbol, 'qty': qty, 'price': price, 'auto': True})
        return True
    return False


def run_bot():
    log("🤖 Bot starting...")
    
    # Load config
    cfg = load_json(BOT_CONFIG_PATH, {})
    
    if not cfg.get('enabled'):
        log("Bot disabled, exiting")
        return {'status': 'disabled'}
    
    mcap_key = cfg.get('mcap', 'small')
    chain = cfg.get('chain', 'base')
    profile_key = cfg.get('profile', 'modere')
    provider = cfg.get('provider', 'openclaw')
    
    mcap = MCAP_PRESETS.get(mcap_key, MCAP_PRESETS['small'])
    profile = AI_PROFILES.get(profile_key, AI_PROFILES['modere'])
    
    log(f"Config: {mcap_key} / {chain} / {profile_key} / {provider}")
    
    # Load simulation
    sim = load_json(SIM_DB_PATH, {'portfolio': {'USD': 10000}, 'positions': {}, 'history': []})
    usd = sim['portfolio'].get('USD', 0)
    
    if usd < 50:
        log("Not enough USD, skipping", "WARN")
        return {'status': 'low_funds', 'usd': usd}
    
    # Get Fear & Greed
    fg = get_fear_greed_index()
    fg_val = fg.value if fg else 50
    log(f"Fear & Greed: {fg_val}")
    
    # Get tokens
    tokens = get_tokens_by_market_cap(mcap['min'], mcap['max'], limit=20)
    if not tokens:
        log("No tokens found", "WARN")
        return {'status': 'no_tokens'}
    
    log(f"Found {len(tokens)} tokens")
    
    # Build prompt
    token_list = "\n".join([f"- {t['symbol']}: ${t.get('price',0):.4f} | 24h: {t.get('price_change_24h',0) or 0:+.1f}% | MCap: ${(t.get('market_cap',0) or 0)/1e6:.1f}M" for t in tokens[:15]])
    
    prompt = f"""Tu es un trader crypto expert. Analyse et donne tes décisions.

MARCHÉ: Fear & Greed = {fg_val}/100
CHAIN: {chain}
PROFIL: {profile_key.upper()} (score min: {profile.min_score})

TOKENS:
{token_list}

INSTRUCTIONS:
- Donne des décisions BUY pour les meilleurs (max 3)
- Confidence doit être >= {profile.min_score}

Réponds UNIQUEMENT avec un JSON array:
[{{"symbol": "XXX", "action": "BUY", "confidence": 75, "reason": "..."}}]

Si rien d'intéressant: []
"""
    
    # Call AI
    log(f"Calling {provider}...")
    model = LLM_MODELS.get(provider, {}).get('default', 'openclaw:main')
    response = call_llm(prompt, provider, model)
    
    if not response:
        log("No AI response", "ERROR")
        return {'status': 'ai_error'}
    
    # Parse response
    import re
    try:
        match = re.search(r'\[.*\]', response, re.DOTALL)
        decisions = json.loads(match.group()) if match else []
    except:
        log("Parse error", "ERROR")
        return {'status': 'parse_error'}
    
    log(f"Got {len(decisions)} decisions")
    
    # Execute
    executed = []
    for d in decisions:
        sym = d.get('symbol', '?')
        act = d.get('action', 'HOLD')
        conf = d.get('confidence', 0)
        reason = d.get('reason', '')
        
        if act == 'BUY' and conf >= profile.min_score:
            price = get_price(sym)
            amount = usd * (profile.trade_amount_pct / 100)
            if amount >= 10 and price > 0:
                if trade(sim, 'BUY', sym, amount, price):
                    log(f"✅ BUY {sym} @ ${price:.4f} ({conf}%): {reason}")
                    executed.append(sym)
                    usd -= amount
    
    # Save
    if executed:
        save_json(SIM_DB_PATH, sim)
        log(f"Executed: {', '.join(executed)}")
    else:
        log("No trades executed")
    
    return {'status': 'ok', 'executed': executed, 'decisions': len(decisions)}


if __name__ == '__main__':
    result = run_bot()
    print(json.dumps(result, indent=2))
