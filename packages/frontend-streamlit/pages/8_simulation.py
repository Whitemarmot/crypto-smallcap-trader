"""
📝 Trading Automatique
Configure: Market Cap + Chain + Fréquence → L'IA fait le reste
"""

import streamlit as st
import json
import os
from datetime import datetime
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

st.set_page_config(
    page_title="📝 Trading Auto | SmallCap Trader",
    page_icon="📝",
    layout="wide"
)

try:
    from utils.social_signals import get_fear_greed_index, get_tokens_by_market_cap
    from utils.config import load_config, AI_PROFILES
    from utils.llm_providers import get_available_providers, LLM_MODELS, call_llm
    from utils.database import get_db
    import requests
    MODULES_OK = True
except ImportError as e:
    MODULES_OK = False
    st.error(f"❌ {e}")
    st.stop()

# Paths
DATA_DIR = os.path.join(os.path.dirname(__file__), '..', 'data')
SIM_DB_PATH = os.path.join(DATA_DIR, 'simulation.json')
BOT_CONFIG_PATH = os.path.join(DATA_DIR, 'bot_config.json')

# Market cap presets
MCAP_PRESETS = {
    'micro': {'name': '🔬 Micro (<$1M)', 'min': 0, 'max': 1_000_000},
    'small': {'name': '🐟 Small ($1M-$100M)', 'min': 1_000_000, 'max': 100_000_000},
    'mid': {'name': '🦈 Mid ($100M-$1B)', 'min': 100_000_000, 'max': 1_000_000_000},
    'large': {'name': '🐋 Large (>$1B)', 'min': 1_000_000_000, 'max': 0},
}

CHAINS = {
    'ethereum': '🔷 Ethereum',
    'base': '🔵 Base', 
    'arbitrum': '🔶 Arbitrum',
    'bsc': '🟡 BSC',
}

FREQUENCIES = {
    '15min': {'name': '⏱️ 15 minutes', 'cron': '*/15 * * * *', 'ms': 15*60*1000},
    '1h': {'name': '⏱️ 1 heure', 'cron': '0 * * * *', 'ms': 60*60*1000},
    '4h': {'name': '⏱️ 4 heures', 'cron': '0 */4 * * *', 'ms': 4*60*60*1000},
    '1d': {'name': '⏱️ 1 jour', 'cron': '0 9 * * *', 'ms': 24*60*60*1000},
    'off': {'name': '⏸️ Désactivé', 'cron': None, 'ms': 0},
}


def load_sim():
    if os.path.exists(SIM_DB_PATH):
        with open(SIM_DB_PATH, 'r') as f:
            return json.load(f)
    return {'portfolio': {'USD': 10000}, 'positions': {}, 'history': []}


def save_sim(data):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(SIM_DB_PATH, 'w') as f:
        json.dump(data, f, indent=2, default=str)


def load_bot_config():
    if os.path.exists(BOT_CONFIG_PATH):
        with open(BOT_CONFIG_PATH, 'r') as f:
            return json.load(f)
    return {'enabled': False, 'frequency': 'off', 'mcap': 'small', 'chain': 'base', 'profile': 'modere', 'provider': 'openclaw'}


def save_bot_config(cfg):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(BOT_CONFIG_PATH, 'w') as f:
        json.dump(cfg, f, indent=2)


def get_price(symbol: str) -> float:
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
        sim['history'].append({'ts': ts, 'action': 'BUY', 'symbol': symbol, 'qty': qty, 'price': price})
        return True
    elif action == 'SELL' and symbol in sim['positions'] and price > 0:
        p = sim['positions'][symbol]
        val = p['amount'] * price
        pnl = (price - p['avg_price']) * p['amount']
        sim['portfolio']['USD'] += val
        del sim['positions'][symbol]
        sim['history'].append({'ts': ts, 'action': 'SELL', 'symbol': symbol, 'qty': p['amount'], 'price': price, 'pnl': pnl})
        return True
    return False


# ========== PAGE ==========
st.title("📝 Trading Auto")
st.caption("Configure market cap + chain + fréquence → L'IA analyse et trade")

sim = load_sim()
bot_cfg = load_bot_config()
config = load_config()
providers = get_available_providers()

# Portfolio summary
col1, col2, col3, col4 = st.columns(4)
usd = sim['portfolio'].get('USD', 0)
pos_val = sum(p['amount'] * get_price(s) for s, p in sim['positions'].items())
total = usd + pos_val

col1.metric("💰 Total", f"${total:,.0f}")
col2.metric("💵 Cash", f"${usd:,.0f}")
col3.metric("📈 Positions", len(sim['positions']))

# Bot status
bot_status = "🟢 Actif" if bot_cfg.get('enabled') and bot_cfg.get('frequency') != 'off' else "⏸️ Arrêté"
col4.metric("🤖 Bot", bot_status)

if sim['positions']:
    for s, p in sim['positions'].items():
        px = get_price(s)
        pnl = (px - p['avg_price']) * p['amount']
        st.caption(f"• {s}: {p['amount']:.4f} @ ${p['avg_price']:.4f} → ${px:.4f} ({'+' if pnl>=0 else ''}{pnl:.2f}$)")

st.markdown("---")

# ========== CONFIG ==========
st.subheader("⚙️ Configuration Bot")

c1, c2, c3 = st.columns(3)

with c1:
    mcap_key = st.selectbox("💰 Market Cap", list(MCAP_PRESETS.keys()), 
                            format_func=lambda x: MCAP_PRESETS[x]['name'], 
                            index=list(MCAP_PRESETS.keys()).index(bot_cfg.get('mcap', 'small')))

with c2:
    chain = st.selectbox("⛓️ Chain", list(CHAINS.keys()), 
                        format_func=lambda x: CHAINS[x],
                        index=list(CHAINS.keys()).index(bot_cfg.get('chain', 'base')) if bot_cfg.get('chain', 'base') in CHAINS else 0)

with c3:
    profile = st.selectbox("🎯 Risque", list(AI_PROFILES.keys()), 
                          format_func=lambda x: AI_PROFILES[x].name, 
                          index=list(AI_PROFILES.keys()).index(bot_cfg.get('profile', 'modere')))

c4, c5 = st.columns(2)

with c4:
    if providers:
        provider_list = list(providers.keys())
        current_provider = bot_cfg.get('provider', 'openclaw')
        provider_idx = provider_list.index(current_provider) if current_provider in provider_list else 0
        provider = st.selectbox("🤖 IA", provider_list, 
                               format_func=lambda x: LLM_MODELS[x]['icon'] + ' ' + LLM_MODELS[x]['name'].split('(')[0],
                               index=provider_idx)
    else:
        provider = None
        st.warning("Aucune IA")

with c5:
    freq_list = list(FREQUENCIES.keys())
    current_freq = bot_cfg.get('frequency', 'off')
    freq_idx = freq_list.index(current_freq) if current_freq in freq_list else 4
    frequency = st.selectbox("🔄 Fréquence", freq_list, 
                            format_func=lambda x: FREQUENCIES[x]['name'],
                            index=freq_idx)

# Save config button
st.markdown("---")

col_save, col_run = st.columns(2)

with col_save:
    if st.button("💾 Sauvegarder Config", use_container_width=True):
        new_cfg = {
            'enabled': frequency != 'off',
            'frequency': frequency,
            'mcap': mcap_key,
            'chain': chain,
            'profile': profile,
            'provider': provider or 'openclaw',
            'updated_at': datetime.now().isoformat()
        }
        save_bot_config(new_cfg)
        st.success(f"✅ Config sauvegardée! Bot {'actif' if new_cfg['enabled'] else 'désactivé'}")
        st.rerun()

with col_run:
    if st.button("🚀 Lancer Maintenant", type="primary", use_container_width=True):
        if not provider:
            st.error("Configure une IA d'abord")
        else:
            mcap = MCAP_PRESETS[mcap_key]
            prof = AI_PROFILES[profile]
            
            # 1. Fear & Greed
            with st.spinner("📊 Sentiment..."):
                fg = get_fear_greed_index()
                fg_val = fg.value if fg else 50
            
            # 2. Get tokens
            with st.spinner("🔍 Tokens..."):
                tokens = get_tokens_by_market_cap(mcap['min'], mcap['max'], limit=20)
                if not tokens:
                    st.warning("Aucun token trouvé pour ce range")
                    st.stop()
            
            st.info(f"😱 F&G: {fg_val} | 📋 {len(tokens)} tokens | 💰 {MCAP_PRESETS[mcap_key]['name']}")
            
            # 3. Build prompt
            token_list = "\n".join([f"- {t['symbol']}: ${t.get('price',0):.4f} | 24h: {t.get('price_change_24h',0) or 0:+.1f}% | MCap: ${(t.get('market_cap',0) or 0)/1e6:.1f}M" for t in tokens[:15]])
            
            prompt = f"""Tu es un trader crypto expert. Analyse et donne tes décisions.

MARCHÉ: Fear & Greed = {fg_val}/100
CHAIN: {chain}
PROFIL: {profile.upper()} (score min: {prof.min_score}, trade: {prof.trade_amount_pct}% du portfolio)

TOKENS ({MCAP_PRESETS[mcap_key]['name']}):
{token_list}

INSTRUCTIONS:
- Analyse chaque token
- Donne des décisions BUY pour les meilleurs (max 3)
- Confidence doit être >= {prof.min_score} pour un BUY

Réponds UNIQUEMENT avec un JSON array:
[{{"symbol": "XXX", "action": "BUY", "confidence": 75, "reason": "..."}}]

Si rien d'intéressant: []
"""
            
            # 4. Call AI
            with st.spinner(f"🧠 {LLM_MODELS[provider]['name']} réfléchit..."):
                model = LLM_MODELS[provider].get('default')
                response = call_llm(prompt, provider, model)
            
            # 5. Parse & Execute
            if response:
                try:
                    import re
                    match = re.search(r'\[.*\]', response, re.DOTALL)
                    decisions = json.loads(match.group()) if match else []
                except:
                    decisions = []
                    st.warning("Parse error")
                
                if decisions:
                    st.subheader("📋 Décisions")
                    executed = []
                    
                    for d in decisions:
                        sym = d.get('symbol', '?')
                        act = d.get('action', 'HOLD')
                        conf = d.get('confidence', 0)
                        reason = d.get('reason', '')
                        
                        emoji = {'BUY': '🟢', 'SELL': '🔴', 'HOLD': '🟡'}.get(act, '⚪')
                        st.markdown(f"{emoji} **{act} {sym}** ({conf}%) - {reason}")
                        
                        # Execute BUY if confidence >= min_score
                        if act == 'BUY' and conf >= prof.min_score:
                            price = get_price(sym)
                            amount = usd * (prof.trade_amount_pct / 100)
                            if amount >= 10 and price > 0:
                                if trade(sim, 'BUY', sym, amount, price):
                                    executed.append(sym)
                                    usd -= amount
                    
                    if executed:
                        save_sim(sim)
                        st.success(f"✅ Acheté: {', '.join(executed)}")
                        st.rerun()
                else:
                    st.info("📭 Aucune opportunité selon l'IA")
            else:
                st.error("❌ Pas de réponse IA")

# ========== HISTORY ==========
st.markdown("---")
with st.expander("📜 Historique"):
    for h in sim.get('history', [])[-20:][::-1]:
        em = '🟢' if h.get('action') == 'BUY' else '🔴'
        pnl = f" PnL: {h.get('pnl',0):+.2f}$" if 'pnl' in h else ""
        ts = h.get('ts') or h.get('timestamp', '?')
        qty = h.get('qty') or h.get('amount', 0)
        symbol = h.get('symbol', '?')
        price = h.get('price', 0)
        st.caption(f"{str(ts)[:16]} {em} {h.get('action','?')} {symbol} {qty:.4f} @ ${price:.4f}{pnl}")

# Reset
if st.button("🔄 Reset Simulation"):
    save_sim({'portfolio': {'USD': 10000}, 'positions': {}, 'history': []})
    st.rerun()

# Info
st.markdown("---")
st.caption(f"💡 Le bot utilise la config sauvegardée. Fréquence actuelle: {FREQUENCIES.get(bot_cfg.get('frequency', 'off'), {}).get('name', 'off')}")
