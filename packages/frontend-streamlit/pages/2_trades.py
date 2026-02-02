"""
📈 Trades - Historique des Trades
"""

import streamlit as st
import pandas as pd
import json
import os
from datetime import datetime, timedelta

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
        trade['wallet_id'] = wallet_id
        trade['wallet_name'] = wallet_name
        trade['wallet_type'] = wallet_type
        all_trades.append(trade)
    
    # Add closed positions
    for pos in data.get('closed_positions', []):
        pos['wallet_id'] = wallet_id
        pos['wallet_name'] = wallet_name
        pos['wallet_type'] = wallet_type
        all_closed.append(pos)

# Sort by date (newest first)
all_trades.sort(key=lambda x: x.get('ts', ''), reverse=True)
all_closed.sort(key=lambda x: x.get('exit_date', ''), reverse=True)

# ========== TITRE ==========
st.title("📈 Historique des Trades")

# ========== SIDEBAR FILTRES ==========
st.sidebar.header("🔍 Filtres")

# Filtre par type de wallet
st.sidebar.subheader("💼 Type de Wallet")
show_sim = st.sidebar.checkbox("🎮 Simulation", value=True)
show_real = st.sidebar.checkbox("💳 Réel", value=True)

# Filtre par wallet spécifique
st.sidebar.subheader("👛 Wallet")
wallet_names = list(set([t.get('wallet_name', '?') for t in all_trades + all_closed]))
wallet_names.sort()
if wallet_names:
    selected_wallets = st.sidebar.multiselect(
        "Sélectionner les wallets",
        options=wallet_names,
        default=wallet_names,
        help="Filtrer par wallet spécifique"
    )
else:
    selected_wallets = []

# Filtre par type d'action
st.sidebar.subheader("📊 Type d'action")
show_buy = st.sidebar.checkbox("🟢 Achats (BUY)", value=True)
show_sell = st.sidebar.checkbox("🔴 Ventes (SELL)", value=True)

# Filtre par date
st.sidebar.subheader("📅 Période")
date_options = {
    "Tout": None,
    "Aujourd'hui": 1,
    "7 derniers jours": 7,
    "30 derniers jours": 30,
    "90 derniers jours": 90,
}
selected_period = st.sidebar.selectbox("Période", list(date_options.keys()), index=0)
days_filter = date_options[selected_period]

# Filtre par statut P&L (pour positions clôturées)
st.sidebar.subheader("💰 Statut P&L")
pnl_filter = st.sidebar.radio(
    "Résultat",
    options=["Tous", "✅ Gagnants", "❌ Perdants"],
    index=0,
    horizontal=True
)

# ========== FONCTIONS DE FILTRAGE ==========
def filter_trades(items):
    """Filtre les trades selon les critères sélectionnés"""
    filtered = []
    now = datetime.now()
    
    for item in items:
        # Filtre type wallet
        wtype = item.get('wallet_type', 'paper')
        if wtype in ['paper', 'simulation'] and not show_sim:
            continue
        if wtype == 'real' and not show_real:
            continue
        
        # Filtre wallet spécifique
        if item.get('wallet_name') not in selected_wallets and selected_wallets:
            continue
        
        # Filtre action (BUY/SELL)
        action = item.get('action', '')
        if action == 'BUY' and not show_buy:
            continue
        if action == 'SELL' and not show_sell:
            continue
        
        # Filtre date
        if days_filter:
            ts = item.get('ts', '')
            if ts:
                try:
                    trade_date = datetime.fromisoformat(ts.replace('Z', '+00:00')).replace(tzinfo=None)
                    if (now - trade_date).days > days_filter:
                        continue
                except:
                    pass
        
        filtered.append(item)
    
    return filtered


def filter_closed(items):
    """Filtre les positions clôturées selon les critères sélectionnés"""
    filtered = []
    now = datetime.now()
    
    for item in items:
        # Filtre type wallet
        wtype = item.get('wallet_type', 'paper')
        if wtype in ['paper', 'simulation'] and not show_sim:
            continue
        if wtype == 'real' and not show_real:
            continue
        
        # Filtre wallet spécifique
        if item.get('wallet_name') not in selected_wallets and selected_wallets:
            continue
        
        # Filtre P&L
        pnl = item.get('pnl_usd', 0)
        if pnl_filter == "✅ Gagnants" and pnl <= 0:
            continue
        if pnl_filter == "❌ Perdants" and pnl >= 0:
            continue
        
        # Filtre date
        if days_filter:
            exit_date = item.get('exit_date', '')
            if exit_date:
                try:
                    pos_date = datetime.fromisoformat(exit_date.replace('Z', '+00:00')).replace(tzinfo=None)
                    if (now - pos_date).days > days_filter:
                        continue
                except:
                    pass
        
        filtered.append(item)
    
    return filtered


# Appliquer les filtres
filtered_trades = filter_trades(all_trades)
filtered_closed = filter_closed(all_closed)

# ========== STATS RÉSUMÉES ==========
total_trades = len(filtered_trades)
wins = sum(1 for p in filtered_closed if p.get('pnl_usd', 0) > 0)
losses = sum(1 for p in filtered_closed if p.get('pnl_usd', 0) < 0)
neutral = sum(1 for p in filtered_closed if p.get('pnl_usd', 0) == 0)
total_pnl = sum(p.get('pnl_usd', 0) for p in filtered_closed)
win_rate = round(wins / len(filtered_closed) * 100) if filtered_closed else 0

# Best/Worst trades
best_trade = max(filtered_closed, key=lambda x: x.get('pnl_usd', 0)) if filtered_closed else None
worst_trade = min(filtered_closed, key=lambda x: x.get('pnl_usd', 0)) if filtered_closed else None

# Affichage stats
st.subheader("📊 Statistiques")
col1, col2, col3, col4, col5 = st.columns(5)

with col1:
    st.metric("📈 Total Trades", total_trades)
    
with col2:
    st.metric("🏁 Positions Clôturées", len(filtered_closed))

with col3:
    st.metric("✅ Wins / ❌ Losses", f"{wins} / {losses}")

with col4:
    st.metric("🎯 Win Rate", f"{win_rate}%")

with col5:
    delta_color = "normal" if total_pnl >= 0 else "inverse"
    st.metric("💰 P&L Total", f"${total_pnl:+,.2f}", delta_color=delta_color)

# Best/Worst trade
if best_trade or worst_trade:
    col_best, col_worst = st.columns(2)
    
    with col_best:
        if best_trade and best_trade.get('pnl_usd', 0) > 0:
            st.success(f"🏆 **Meilleur trade:** {best_trade.get('symbol', '?')} → **${best_trade.get('pnl_usd', 0):+.2f}** ({best_trade.get('pnl_pct', 0):+.1f}%)")
        else:
            st.info("🏆 Meilleur trade: Aucun trade gagnant")
    
    with col_worst:
        if worst_trade and worst_trade.get('pnl_usd', 0) < 0:
            st.error(f"💀 **Pire trade:** {worst_trade.get('symbol', '?')} → **${worst_trade.get('pnl_usd', 0):+.2f}** ({worst_trade.get('pnl_pct', 0):+.1f}%)")
        else:
            st.info("💀 Pire trade: Aucun trade perdant")

st.divider()

# ========== TABS ==========
tab1, tab2 = st.tabs(["📜 Tous les Trades", "🏁 Positions Clôturées"])

# ========== TAB 1: TOUS LES TRADES ==========
with tab1:
    st.subheader(f"📜 Historique ({len(filtered_trades)} trades)")
    
    if filtered_trades:
        # Préparer les données pour le DataFrame
        trades_data = []
        for trade in filtered_trades[:100]:  # Limiter à 100
            ts = trade.get('ts', '')[:16].replace('T', ' ')
            action = trade.get('action', '?')
            symbol = trade.get('symbol', '?')
            qty = trade.get('qty', 0)
            price = trade.get('price', 0)
            usd = trade.get('usd', 0)
            wallet_name = trade.get('wallet_name', '?')
            wtype = trade.get('wallet_type', 'paper')
            pnl = trade.get('pnl_usd', None)
            
            # Emoji pour action
            action_display = "🟢 BUY" if action == 'BUY' else "🔴 SELL" if action == 'SELL' else f"⚪ {action}"
            
            # Emoji pour type wallet
            wtype_display = "🎮 Sim" if wtype in ['paper', 'simulation'] else "💳 Réel"
            
            # P&L formaté
            pnl_display = f"${pnl:+.2f}" if pnl is not None else "-"
            
            trades_data.append({
                "📅 Date": ts,
                "💼 Wallet": wallet_name,
                "🏷️ Type": wtype_display,
                "📊 Action": action_display,
                "🪙 Token": symbol,
                "📦 Quantité": f"{qty:,.4f}",
                "💵 Prix": f"${price:.6f}",
                "💰 Valeur": f"${usd:.2f}",
                "📈 P&L": pnl_display,
            })
        
        df_trades = pd.DataFrame(trades_data)
        
        # Coloriser le P&L
        def color_pnl(val):
            if val == "-":
                return ""
            try:
                num = float(val.replace('$', '').replace(',', '').replace('+', ''))
                if num > 0:
                    return "color: #00FF88; font-weight: bold"
                elif num < 0:
                    return "color: #FF4444; font-weight: bold"
            except:
                pass
            return ""
        
        # Afficher le DataFrame
        st.dataframe(
            df_trades.style.applymap(color_pnl, subset=["📈 P&L"]),
            use_container_width=True,
            hide_index=True,
            height=500
        )
        
        if len(filtered_trades) > 100:
            st.info(f"⚠️ Affichage limité aux 100 premiers trades (total: {len(filtered_trades)})")
    else:
        st.info("📭 Aucun trade trouvé avec ces filtres")

# ========== TAB 2: POSITIONS CLÔTURÉES ==========
with tab2:
    st.subheader(f"🏁 Positions Clôturées ({len(filtered_closed)})")
    
    if filtered_closed:
        # Préparer les données pour le DataFrame
        closed_data = []
        for pos in filtered_closed[:50]:  # Limiter à 50
            symbol = pos.get('symbol', '?')
            entry = pos.get('entry_price', 0)
            exit_p = pos.get('exit_price', 0)
            pnl = pos.get('pnl_usd', 0)
            pnl_pct = pos.get('pnl_pct', 0)
            reason = pos.get('reason', '')
            wallet_name = pos.get('wallet_name', '?')
            wtype = pos.get('wallet_type', 'paper')
            holding = pos.get('holding_hours', 0)
            
            # Entry/exit dates
            entry_date = pos.get('entry_date', '')[:10]
            exit_date = pos.get('exit_date', '')[:10]
            
            # Emoji pour résultat
            result_emoji = "🟢" if pnl >= 0 else "🔴"
            
            # Emoji pour type wallet
            wtype_display = "🎮 Sim" if wtype in ['paper', 'simulation'] else "💳 Réel"
            
            # Holding formaté
            if holding < 1:
                holding_str = f"{int(holding * 60)}min"
            elif holding < 24:
                holding_str = f"{holding:.1f}h"
            else:
                holding_str = f"{holding / 24:.1f}j"
            
            closed_data.append({
                "🪙 Token": symbol,
                "💼 Wallet": wallet_name,
                "🏷️ Type": wtype_display,
                "📅 Entrée": entry_date,
                "📅 Sortie": exit_date,
                "⏱️ Durée": holding_str,
                "💵 Prix Entrée": f"${entry:.6f}",
                "💵 Prix Sortie": f"${exit_p:.6f}",
                "💰 P&L ($)": f"${pnl:+.2f}",
                "📊 P&L (%)": f"{pnl_pct:+.1f}%",
                "📝 Raison": reason,
            })
        
        df_closed = pd.DataFrame(closed_data)
        
        # Coloriser le P&L
        def color_pnl_cell(val):
            if isinstance(val, str):
                try:
                    # Extraire le nombre
                    num_str = val.replace('$', '').replace('%', '').replace(',', '').replace('+', '')
                    num = float(num_str)
                    if num > 0:
                        return "color: #00FF88; font-weight: bold"
                    elif num < 0:
                        return "color: #FF4444; font-weight: bold"
                except:
                    pass
            return ""
        
        # Afficher le DataFrame avec style
        st.dataframe(
            df_closed.style.applymap(color_pnl_cell, subset=["💰 P&L ($)", "📊 P&L (%)"]),
            use_container_width=True,
            hide_index=True,
            height=500
        )
        
        if len(filtered_closed) > 50:
            st.info(f"⚠️ Affichage limité aux 50 premières positions (total: {len(filtered_closed)})")
        
        # Résumé des raisons de sortie
        st.subheader("📝 Raisons de sortie")
        reasons = {}
        for pos in filtered_closed:
            r = pos.get('reason', 'unknown')
            if r not in reasons:
                reasons[r] = {'count': 0, 'pnl': 0}
            reasons[r]['count'] += 1
            reasons[r]['pnl'] += pos.get('pnl_usd', 0)
        
        if reasons:
            reason_data = []
            for reason, stats in sorted(reasons.items(), key=lambda x: x[1]['count'], reverse=True):
                emoji = "🎯" if "tp" in reason.lower() or "profit" in reason.lower() else "🛑" if "sl" in reason.lower() or "stop" in reason.lower() else "📋"
                reason_data.append({
                    "📝 Raison": f"{emoji} {reason}",
                    "📊 Nombre": stats['count'],
                    "💰 P&L Total": f"${stats['pnl']:+.2f}"
                })
            
            df_reasons = pd.DataFrame(reason_data)
            st.dataframe(df_reasons, use_container_width=True, hide_index=True)
    else:
        st.info("📭 Aucune position clôturée trouvée avec ces filtres")

# ========== NAVIGATION ==========
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
