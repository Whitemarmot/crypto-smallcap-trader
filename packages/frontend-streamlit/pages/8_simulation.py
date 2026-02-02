"""
📝 Trading Automatique - Paper Trading
L'IA analyse, décide, et le système exécute
"""

import streamlit as st
import json
import os
import time
from datetime import datetime
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

st.set_page_config(
    page_title="📝 Trading Auto | SmallCap Trader",
    page_icon="📝",
    layout="wide"
)

# Imports
try:
    from utils.social_signals import get_fear_greed_index, get_trending_tokens, get_tokens_by_market_cap
    from utils.config import load_config, AI_PROFILES, SUPPORTED_NETWORKS
    from utils.llm_providers import get_available_providers, LLM_MODELS, call_llm
    from utils.database import get_db
    import requests
    MODULES_OK = True
except ImportError as e:
    MODULES_OK = False
    st.error(f"❌ Module error: {e}")
    st.stop()

# Simulation database
SIM_DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'simulation.json')

# Market cap presets
MARKET_CAP_PRESETS = {
    'micro_cap': {'min': 0, 'max': 1_000_000},
    'small_cap': {'min': 1_000_000, 'max': 100_000_000},
    'mid_cap': {'min': 100_000_000, 'max': 1_000_000_000},
    'large_cap': {'min': 1_000_000_000, 'max': 0},
    'all': {'min': 0, 'max': 0},
}


def load_sim():
    if os.path.exists(SIM_DB_PATH):
        with open(SIM_DB_PATH, 'r') as f:
            return json.load(f)
    return {'portfolio': {'USD': 10000}, 'positions': {}, 'history': [], 'settings': {'initial_capital': 10000}}


def save_sim(data):
    os.makedirs(os.path.dirname(SIM_DB_PATH), exist_ok=True)
    with open(SIM_DB_PATH, 'w') as f:
        json.dump(data, f, indent=2, default=str)


def get_token_price(symbol: str) -> float:
    """Get price from CoinGecko"""
    try:
        symbol_map = {
            'BTC': 'bitcoin', 'ETH': 'ethereum', 'SOL': 'solana',
            'PEPE': 'pepe', 'DOGE': 'dogecoin', 'XRP': 'ripple'
        }
        cg_id = symbol_map.get(symbol.upper(), symbol.lower())
        resp = requests.get(
            f'https://api.coingecko.com/api/v3/simple/price',
            params={'ids': cg_id, 'vs_currencies': 'usd'},
            timeout=10
        )
        return resp.json().get(cg_id, {}).get('usd', 0)
    except:
        return 0


def execute_trade(sim_data: dict, action: str, symbol: str, amount_usd: float, price: float) -> dict:
    """Execute simulated trade"""
    ts = datetime.now().isoformat()
    
    if action == 'BUY':
        if sim_data['portfolio'].get('USD', 0) < amount_usd:
            return {'error': 'Pas assez de USD'}
        
        sim_data['portfolio']['USD'] -= amount_usd
        token_amount = amount_usd / price if price > 0 else 0
        
        if symbol in sim_data['positions']:
            pos = sim_data['positions'][symbol]
            total = pos['amount'] + token_amount
            cost = (pos['amount'] * pos['avg_price']) + amount_usd
            sim_data['positions'][symbol] = {'amount': total, 'avg_price': cost / total, 'entry_date': pos['entry_date']}
        else:
            sim_data['positions'][symbol] = {'amount': token_amount, 'avg_price': price, 'entry_date': ts}
        
        sim_data['history'].append({'ts': ts, 'action': 'BUY', 'symbol': symbol, 'amount': token_amount, 'price': price, 'usd': amount_usd})
        return {'success': True}
    
    elif action == 'SELL':
        if symbol not in sim_data['positions']:
            return {'error': f'Pas de position {symbol}'}
        
        pos = sim_data['positions'][symbol]
        sell_amount = pos['amount']
        sell_value = sell_amount * price
        pnl = (price - pos['avg_price']) * sell_amount
        
        sim_data['portfolio']['USD'] += sell_value
        del sim_data['positions'][symbol]
        
        sim_data['history'].append({'ts': ts, 'action': 'SELL', 'symbol': symbol, 'amount': sell_amount, 'price': price, 'usd': sell_value, 'pnl': pnl})
        return {'success': True, 'pnl': pnl}
    
    return {'error': 'Action inconnue'}


def build_analysis_prompt(tokens_data: list, profile: str, fg_value: int) -> str:
    """Build prompt for AI analysis"""
    token_list = "\n".join([
        f"- {t['symbol']}: ${t.get('price', 0):.6f} | 24h: {t.get('change_24h', 0):+.1f}% | MCap: ${t.get('market_cap', 0)/1e6:.1f}M"
        for t in tokens_data[:15]
    ])
    
    profile_desc = {
        'conservateur': 'Très prudent, uniquement les opportunités évidentes (score 80+)',
        'modere': 'Équilibré entre risque et opportunité (score 65+)',
        'agressif': 'Prendre plus de risques pour plus de gains (score 50+)',
        'degen': 'YOLO mode, on cherche les moonshots (score 40+)'
    }
    
    return f"""Tu es un trader crypto. Analyse ces tokens et donne tes décisions.

## Contexte marché
- Fear & Greed Index: {fg_value}/100

## Tokens à analyser
{token_list}

## Ton profil de trading: {profile.upper()}
{profile_desc.get(profile, 'Modéré')}

## Instructions
Pour chaque token intéressant, donne ta décision.
Réponds UNIQUEMENT avec un JSON array (pas de texte avant/après):

[
  {{"symbol": "XXX", "action": "BUY", "confidence": 75, "reason": "..."}},
  {{"symbol": "YYY", "action": "HOLD", "confidence": 50, "reason": "..."}}
]

Si aucun token n'est intéressant, retourne un array vide: []
Actions possibles: BUY, SELL, HOLD
"""


# ==================== PAGE ====================

st.title("📝 Trading Automatique")
st.caption("L'IA analyse → décide → le système exécute")

config = load_config()
sim_data = load_sim()
db = get_db()

# Get wallets with configs
wallets = db.get_wallets()
wallet_configs = []

for w in wallets:
    cfg = config.trading.wallets.get(w.address, {})
    if cfg.get('enabled', True):
        wallet_configs.append({
            'name': w.name,
            'address': w.address,
            'profile': cfg.get('ai_profile', 'modere'),
            'provider': cfg.get('llm_provider', 'openclaw'),
            'mcap_preset': cfg.get('market_cap_preset', 'small_cap'),
            'network': cfg.get('network', w.network)
        })

# ========== PORTFOLIO ==========
st.subheader("💼 Portfolio Simulation")

col1, col2, col3, col4 = st.columns(4)

usd = sim_data['portfolio'].get('USD', 0)
positions_value = sum(p['amount'] * get_token_price(s) for s, p in sim_data['positions'].items())
total = usd + positions_value
initial = sim_data['settings'].get('initial_capital', 10000)
pnl = total - initial

col1.metric("💰 Total", f"${total:,.2f}", f"{(pnl/initial)*100:+.1f}%")
col2.metric("💵 USD", f"${usd:,.2f}")
col3.metric("📈 Positions", f"${positions_value:,.2f}")
col4.metric("🎯 Trades", len(sim_data['history']))

# Show positions
if sim_data['positions']:
    st.markdown("**Positions ouvertes:**")
    for symbol, pos in sim_data['positions'].items():
        price = get_token_price(symbol)
        pnl = (price - pos['avg_price']) * pos['amount']
        pnl_pct = ((price / pos['avg_price']) - 1) * 100 if pos['avg_price'] > 0 else 0
        color = "green" if pnl >= 0 else "red"
        st.markdown(f"- **{symbol}**: {pos['amount']:.4f} @ ${pos['avg_price']:.4f} → ${price:.4f} (:{color}[{pnl:+.2f}$ / {pnl_pct:+.1f}%])")

st.markdown("---")

# ========== WALLET SELECTOR ==========
st.subheader("🎯 Lancer une analyse")

if not wallet_configs:
    st.warning("⚠️ Configure d'abord un wallet dans la page Wallets")
else:
    selected_wallet = st.selectbox(
        "Wallet",
        options=range(len(wallet_configs)),
        format_func=lambda i: f"{wallet_configs[i]['name']} ({wallet_configs[i]['profile']})"
    )
    
    wc = wallet_configs[selected_wallet]
    
    # Show config
    col1, col2, col3, col4 = st.columns(4)
    col1.caption(f"🎯 {AI_PROFILES[wc['profile']].name}")
    col2.caption(f"🤖 {LLM_MODELS.get(wc['provider'], {}).get('name', wc['provider'])}")
    col3.caption(f"💰 {wc['mcap_preset']}")
    col4.caption(f"⛓️ {wc['network']}")
    
    # Auto-execute toggle
    auto_execute = st.toggle("⚡ Exécuter automatiquement les trades", value=True)
    
    # Run analysis
    if st.button("🚀 Analyser et Trader", type="primary", use_container_width=True):
        profile = AI_PROFILES[wc['profile']]
        mcap = MARKET_CAP_PRESETS.get(wc['mcap_preset'], MARKET_CAP_PRESETS['small_cap'])
        
        # 1. Get Fear & Greed
        with st.spinner("📊 Récupération Fear & Greed..."):
            fg = get_fear_greed_index()
            fg_value = fg.value if fg else 50
            st.caption(f"😱 Fear & Greed: {fg_value}")
        
        # 2. Get tokens
        with st.spinner("🔍 Récupération des tokens..."):
            tokens = get_tokens_by_market_cap(mcap['min'], mcap['max'], limit=20)
            
            if not tokens:
                # Fallback to trending
                trending = get_trending_tokens()
                if trending:
                    tokens = [{'symbol': t.symbol, 'name': t.name, 'price': 0, 'change_24h': 0, 'market_cap': 0} for t in trending[:15]]
            
            # Enrich with prices
            for t in tokens[:10]:
                if not t.get('price'):
                    t['price'] = get_token_price(t['symbol'])
            
            st.caption(f"📋 {len(tokens)} tokens à analyser")
        
        # 3. Ask AI
        with st.spinner(f"🧠 {LLM_MODELS.get(wc['provider'], {}).get('name', 'IA')} analyse..."):
            prompt = build_analysis_prompt(tokens, wc['profile'], fg_value)
            
            provider = wc['provider']
            model = LLM_MODELS.get(provider, {}).get('default', 'openclaw:main')
            
            response = call_llm(prompt, provider, model)
            
            if response:
                st.caption("✅ Réponse IA reçue")
                
                # Parse response
                try:
                    import re
                    json_match = re.search(r'\[.*\]', response, re.DOTALL)
                    if json_match:
                        decisions = json.loads(json_match.group())
                    else:
                        decisions = []
                except:
                    decisions = []
                    st.warning("⚠️ Impossible de parser la réponse IA")
            else:
                decisions = []
                st.error("❌ Pas de réponse de l'IA")
        
        # 4. Show decisions and execute
        if decisions:
            st.markdown("### 📋 Décisions IA")
            
            executed = []
            for d in decisions:
                symbol = d.get('symbol', '?')
                action = d.get('action', 'HOLD')
                confidence = d.get('confidence', 50)
                reason = d.get('reason', '')
                
                emoji = {'BUY': '🟢', 'SELL': '🔴', 'HOLD': '🟡'}.get(action, '⚪')
                
                cols = st.columns([1, 2, 1, 4])
                cols[0].markdown(f"{emoji} **{action}**")
                cols[1].markdown(f"**{symbol}**")
                cols[2].markdown(f"{confidence}%")
                cols[3].caption(reason)
                
                # Execute if auto-execute and confidence >= profile min
                if auto_execute and action == 'BUY' and confidence >= profile.min_score:
                    price = get_token_price(symbol)
                    if price > 0:
                        trade_amount = usd * (profile.trade_amount_pct / 100)
                        trade_amount = min(trade_amount, usd)  # Don't exceed available
                        
                        if trade_amount >= 10:
                            result = execute_trade(sim_data, 'BUY', symbol, trade_amount, price)
                            if result.get('success'):
                                executed.append(f"BUY {symbol}")
                                usd -= trade_amount
                
                elif auto_execute and action == 'SELL' and symbol in sim_data['positions']:
                    price = get_token_price(symbol)
                    if price > 0:
                        result = execute_trade(sim_data, 'SELL', symbol, 0, price)
                        if result.get('success'):
                            executed.append(f"SELL {symbol}")
            
            if executed:
                save_sim(sim_data)
                st.success(f"✅ Exécuté: {', '.join(executed)}")
                st.rerun()
        else:
            st.info("📭 Aucune décision de l'IA")

# ========== HISTORY ==========
st.markdown("---")
st.subheader("📜 Historique")

history = sim_data.get('history', [])[-20:][::-1]
if history:
    for h in history:
        emoji = '🟢' if h['action'] == 'BUY' else '🔴'
        pnl_str = f" → PnL: {h.get('pnl', 0):+.2f}$" if 'pnl' in h else ""
        st.caption(f"{h['ts'][:16]} | {emoji} {h['action']} {h['symbol']} | {h['amount']:.4f} @ ${h['price']:.4f}{pnl_str}")
else:
    st.caption("Aucun trade")

# Reset
st.markdown("---")
if st.button("🔄 Reset simulation"):
    sim_data = {'portfolio': {'USD': 10000}, 'positions': {}, 'history': [], 'settings': {'initial_capital': 10000}}
    save_sim(sim_data)
    st.success("Reset!")
    st.rerun()

# Navigation
st.markdown("---")
cols = st.columns(4)
with cols[0]:
    if st.button("👛 Wallets", use_container_width=True):
        st.switch_page("pages/1_wallet.py")
with cols[1]:
    if st.button("📜 Logs IA", use_container_width=True):
        st.switch_page("pages/9_logs_ia.py")
with cols[2]:
    if st.button("📡 Signals", use_container_width=True):
        st.switch_page("pages/3_signals.py")
with cols[3]:
    if st.button("🏠 Dashboard", use_container_width=True):
        st.switch_page("pages/0_dashboard.py")
