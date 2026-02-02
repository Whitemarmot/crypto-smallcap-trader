"""
Crypto SmallCap Trader - Dashboard Principal
"""

import streamlit as st
from datetime import datetime
import json
import os

st.set_page_config(
    page_title="🚀 SmallCap Trader",
    page_icon="🚀",
    layout="wide"
)

# Paths
DATA_DIR = os.path.join(os.path.dirname(__file__), 'data')
WALLETS_DIR = os.path.join(DATA_DIR, 'wallets')
WALLETS_CONFIG = os.path.join(WALLETS_DIR, 'config.json')
BOT_CONFIG = os.path.join(DATA_DIR, 'bot_config.json')

def load_json(path, default):
    try:
        if os.path.exists(path):
            with open(path, 'r') as f:
                return json.load(f)
    except:
        pass
    return default

# Load data
wallets_config = load_json(WALLETS_CONFIG, {'wallets': []})
bot_config = load_json(BOT_CONFIG, {})
wallets = wallets_config.get('wallets', [])

# Calculate totals from all wallets
total_value = 0
total_positions = 0
total_cash = 0
win_count = 0
total_trades = 0

for w in wallets:
    wallet_path = os.path.join(WALLETS_DIR, f"{w['id']}.json")
    data = load_json(wallet_path, {'portfolio': {'USDC': 0}, 'positions': {}, 'closed_positions': []})
    
    cash = data.get('portfolio', {}).get('USDC', 0)
    positions = data.get('positions', {})
    closed = data.get('closed_positions', [])
    
    # Calculate position value
    pos_value = 0
    for sym, pos in positions.items():
        pos_value += pos.get('amount', 0) * pos.get('avg_price', 0)
    
    total_value += cash + pos_value
    total_cash += cash
    total_positions += len(positions)
    
    # Win rate stats
    win_count += sum(1 for p in closed if p.get('pnl_usd', 0) > 0)
    total_trades += len(closed)

win_rate = round(win_count / total_trades * 100) if total_trades > 0 else 0

# Sidebar
with st.sidebar:
    st.title("🚀 SmallCap Trader")
    st.markdown("---")
    
    st.page_link("pages/1_wallet.py", label="👛 Wallets", icon="👛")
    st.page_link("pages/9_positions.py", label="📊 Positions", icon="📊")
    st.page_link("pages/2_trades.py", label="📈 Trades", icon="📈")
    st.page_link("pages/9_logs_ia.py", label="🤖 Logs IA", icon="🤖")
    
    st.markdown("---")
    st.caption("v0.2.0 | " + datetime.now().strftime("%d/%m/%Y %H:%M"))

# Header
st.title("🚀 Crypto SmallCap Trader")

# Métriques principales
col1, col2, col3, col4 = st.columns(4)

col1.metric("💰 Valeur Portfolio", f"${total_value:,.2f}")
col2.metric("📊 Positions", f"{total_positions}")
col3.metric("💵 Cash", f"${total_cash:,.2f}")
col4.metric("🎯 Win Rate", f"{win_rate}%" if total_trades > 0 else "--", 
            delta=f"{total_trades} trades" if total_trades > 0 else None)

st.divider()

# Status
col_left, col_right = st.columns([2, 1])

with col_left:
    st.subheader("📊 Wallets")
    
    if wallets:
        for w in wallets:
            wallet_path = os.path.join(WALLETS_DIR, f"{w['id']}.json")
            data = load_json(wallet_path, {'portfolio': {'USDC': 0}, 'positions': {}})
            cash = data.get('portfolio', {}).get('USDC', 0)
            positions = data.get('positions', {})
            
            pos_value = sum(p.get('amount', 0) * p.get('avg_price', 0) for p in positions.values())
            total = cash + pos_value
            
            type_badge = "🎮" if w.get('type') == 'paper' else "💳"
            status = "🟢" if w.get('enabled') else "⚪"
            
            st.markdown(f"{status} {type_badge} **{w['name']}** — ${total:,.2f} | {len(positions)} pos | {w.get('chain', 'base').upper()}")
            
            if w.get('address'):
                st.caption(f"└─ `{w['address'][:10]}...{w['address'][-6:]}`")
    else:
        st.warning("⚠️ Aucun wallet configuré")
    
    st.divider()
    st.subheader("🤖 Bot Status")
    
    # Le bot tourne via cron - vérifier si enabled
    bot_enabled = bot_config.get('enabled', False)
    if bot_enabled:
        st.success("✅ Bot actif (cron toutes les heures)")
        st.caption(f"Dernière config: {bot_config.get('updated_at', 'N/A')}")
    else:
        st.info("⏸️ Bot en pause")

with col_right:
    st.subheader("✅ Checklist")
    
    has_wallet = len(wallets) > 0
    has_sim_funds = total_value > 0
    has_config = any(w.get('ai_profile') for w in wallets)
    bot_running = bot_config.get('enabled', False)
    
    steps = [
        ("👛 Créer un wallet", has_wallet),
        ("💰 Fonds disponibles", has_sim_funds),
        ("⚙️ Config wallet", has_config),
        ("🤖 Bot actif", bot_running),
    ]
    
    for step, done in steps:
        if done:
            st.markdown(f"✅ ~~{step}~~")
        else:
            st.markdown(f"⬜ {step}")
    
    if all(done for _, done in steps):
        st.success("🎉 Tout est prêt!")

st.divider()

# Navigation
st.subheader("📍 Navigation")
nav_cols = st.columns(4)

with nav_cols[0]:
    if st.button("👛 Wallets", use_container_width=True, type="primary"):
        st.switch_page("pages/1_wallet.py")

with nav_cols[1]:
    if st.button("📊 Positions", use_container_width=True):
        st.switch_page("pages/9_positions.py")

with nav_cols[2]:
    if st.button("📈 Trades", use_container_width=True):
        st.switch_page("pages/2_trades.py")

with nav_cols[3]:
    if st.button("🤖 Logs IA", use_container_width=True):
        st.switch_page("pages/9_logs_ia.py")

st.divider()
st.caption("SmallCap Trader v0.2.0 - Bot trading IA par Jean-Michel 🥖")
