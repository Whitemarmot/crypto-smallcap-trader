"""
📈 Trades - Historique des Trades
"""

import streamlit as st
import json
import os
from datetime import datetime

st.set_page_config(
    page_title="📈 Trades | SmallCap Trader",
    page_icon="📈",
    layout="wide"
)

# Paths
DATA_DIR = os.path.join(os.path.dirname(__file__), '..', 'data')
WALLETS_DIR = os.path.join(DATA_DIR, 'wallets')
WALLETS_CONFIG = os.path.join(WALLETS_DIR, 'config.json')


def load_json(path, default):
    try:
        if os.path.exists(path):
            with open(path, 'r') as f:
                return json.load(f)
    except:
        pass
    return default


# Load all wallets
config = load_json(WALLETS_CONFIG, {'wallets': []})
wallets = config.get('wallets', [])

# Collect all trades from all wallets
all_trades = []
all_closed = []

for w in wallets:
    wallet_id = w['id']
    wallet_name = w['name']
    wallet_type = w.get('type', 'paper')
    
    wallet_path = os.path.join(WALLETS_DIR, f'{wallet_id}.json')
    data = load_json(wallet_path, {'history': [], 'closed_positions': []})
    
    # Add history trades
    for trade in data.get('history', []):
        trade['wallet_name'] = wallet_name
        trade['wallet_type'] = wallet_type
        all_trades.append(trade)
    
    # Add closed positions
    for pos in data.get('closed_positions', []):
        pos['wallet_name'] = wallet_name
        pos['wallet_type'] = wallet_type
        all_closed.append(pos)

# Sort by date (newest first)
all_trades.sort(key=lambda x: x.get('ts', ''), reverse=True)
all_closed.sort(key=lambda x: x.get('exit_date', ''), reverse=True)

# Calculate stats
total_trades = len(all_trades)
wins = sum(1 for p in all_closed if p.get('pnl_usd', 0) > 0)
losses = sum(1 for p in all_closed if p.get('pnl_usd', 0) < 0)
total_pnl = sum(p.get('pnl_usd', 0) for p in all_closed)
win_rate = round(wins / len(all_closed) * 100) if all_closed else 0

st.title("📈 Historique des Trades")

# Filters
col_filter1, col_filter2 = st.columns([1, 3])
with col_filter1:
    show_sim = st.checkbox("🎮 Simulation", value=True)
    show_real = st.checkbox("💳 Réel", value=True)

# Filter trades based on selection
def filter_by_type(items):
    filtered = []
    for item in items:
        wtype = item.get('wallet_type', 'paper')
        if wtype in ['paper', 'simulation'] and show_sim:
            filtered.append(item)
        elif wtype == 'real' and show_real:
            filtered.append(item)
    return filtered

filtered_trades = filter_by_type(all_trades)
filtered_closed = filter_by_type(all_closed)

# Recalculate stats based on filter
total_trades = len(filtered_trades)
wins = sum(1 for p in filtered_closed if p.get('pnl_usd', 0) > 0)
losses = sum(1 for p in filtered_closed if p.get('pnl_usd', 0) < 0)
total_pnl = sum(p.get('pnl_usd', 0) for p in filtered_closed)
win_rate = round(wins / len(filtered_closed) * 100) if filtered_closed else 0

# Stats
col1, col2, col3, col4 = st.columns(4)
col1.metric("📊 Total Trades", total_trades)
col2.metric("✅ Wins / ❌ Losses", f"{wins} / {losses}")
col3.metric("🎯 Win Rate", f"{win_rate}%")
col4.metric("💰 P&L Total", f"${total_pnl:+,.2f}", delta_color="normal" if total_pnl >= 0 else "inverse")

st.divider()

# Tabs
tab1, tab2 = st.tabs(["📜 Tous les Trades", "🏁 Positions Clôturées"])

with tab1:
    st.subheader(f"📜 Historique ({len(filtered_trades)} trades)")
    
    if filtered_trades:
        for trade in filtered_trades[:50]:  # Limit to 50
            ts = trade.get('ts', '')[:16].replace('T', ' ')
            action = trade.get('action', '?')
            symbol = trade.get('symbol', '?')
            qty = trade.get('qty', 0)
            price = trade.get('price', 0)
            usd = trade.get('usd', 0)
            wallet_name = trade.get('wallet_name', '?')
            wtype = trade.get('wallet_type', 'paper')
            wtype_icon = "🎮" if wtype in ['paper', 'simulation'] else "💳"
            
            # Color based on action
            if action == 'BUY':
                icon = "🟢"
            elif action == 'SELL':
                icon = "🔴"
            else:
                icon = "⚪"
            
            pnl_str = ""
            if action == 'SELL' and 'pnl_usd' in trade:
                pnl = trade['pnl_usd']
                pnl_str = f" | **${pnl:+.2f}**"
            
            st.markdown(f"{icon} `{ts}` {wtype_icon} `{wallet_name}` **{action}** {qty:.4f} **{symbol}** @ ${price:.6f} = ${usd:.2f}{pnl_str}")
    else:
        st.info("📭 Aucun trade enregistré (ou tous filtrés)")

with tab2:
    st.subheader(f"🏁 Positions Clôturées ({len(filtered_closed)})")
    
    if filtered_closed:
        for pos in filtered_closed[:30]:  # Limit to 30
            symbol = pos.get('symbol', '?')
            entry = pos.get('entry_price', 0)
            exit_p = pos.get('exit_price', 0)
            pnl = pos.get('pnl_usd', 0)
            pnl_pct = pos.get('pnl_pct', 0)
            reason = pos.get('reason', '')
            wallet_name = pos.get('wallet_name', '?')
            wtype = pos.get('wallet_type', 'paper')
            wtype_icon = "🎮" if wtype in ['paper', 'simulation'] else "💳"
            holding = pos.get('holding_hours', 0)
            
            # Entry/exit dates
            entry_date = pos.get('entry_date', '')[:10]
            exit_date = pos.get('exit_date', '')[:10]
            
            # Icon based on P&L
            icon = "🟢" if pnl >= 0 else "🔴"
            
            col1, col2, col3 = st.columns([2, 1, 1])
            
            with col1:
                st.markdown(f"{icon} {wtype_icon} **{symbol}** `{wallet_name}`")
                st.caption(f"{entry_date} → {exit_date} ({holding:.0f}h)")
            
            with col2:
                st.markdown(f"${entry:.6f} → ${exit_p:.6f}")
                if reason:
                    st.caption(f"📝 {reason}")
            
            with col3:
                st.markdown(f"**${pnl:+.2f}** ({pnl_pct:+.1f}%)")
            
            st.divider()
    else:
        st.info("📭 Aucune position clôturée (ou toutes filtrées)")

# Navigation
st.markdown("---")
cols = st.columns(4)
if cols[0].button("🏠 Home", use_container_width=True):
    st.switch_page("app.py")
if cols[1].button("👛 Wallets", use_container_width=True):
    st.switch_page("pages/1_wallet.py")
if cols[2].button("📊 Positions", use_container_width=True):
    st.switch_page("pages/9_positions.py")
if cols[3].button("🤖 Logs IA", use_container_width=True):
    st.switch_page("pages/9_logs_ia.py")
