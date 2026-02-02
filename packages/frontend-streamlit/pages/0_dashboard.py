"""
🏠 Dashboard Principal - Vue Multi-Wallet
Vue globale de tous les wallets et status
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import sys
import os

# Add utils to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from utils.database import get_db
from utils.config import load_config, SUPPORTED_NETWORKS

st.set_page_config(
    page_title="🏠 Dashboard | SmallCap Trader",
    page_icon="🏠",
    layout="wide"
)

# ========== STYLES ==========
st.markdown("""
<style>
    .main-title {
        font-size: 2.2rem;
        font-weight: bold;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 50%, #f093fb 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.5rem;
    }
    .wallet-card {
        background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
        border-radius: 12px;
        padding: 1.2rem;
        border: 1px solid #333366;
        margin-bottom: 0.5rem;
    }
    .profit-green { color: #00ff88 !important; }
    .loss-red { color: #ff4757 !important; }
</style>
""", unsafe_allow_html=True)

# ========== DATABASE & CONFIG ==========
db = get_db()
config = load_config()

# ========== HEADER ==========
col_header, col_refresh = st.columns([4, 1])

with col_header:
    st.markdown('<p class="main-title">🏠 Dashboard Multi-Wallet</p>', unsafe_allow_html=True)
    st.caption(f"🌐 Réseau actif: {config.active_network.upper()} | ⏰ {datetime.now().strftime('%H:%M:%S')}")

with col_refresh:
    if st.button("🔄 Rafraîchir", use_container_width=True):
        st.rerun()

st.markdown("---")

# ========== BOT TRADING STATUS ==========
import requests
import time

OPENCLAW_API = "http://localhost:18789"
OPENCLAW_TOKEN = "354943dd82e0b4e2860dd25a7fcebdfcfc2b079c2a5bf34e"
CRON_JOB_ID = "d6ead671-90b7-4329-9d9b-28c033e29a30"

def get_cron_status():
    """Get cron job status from OpenClaw API"""
    try:
        resp = requests.get(
            f"{OPENCLAW_API}/api/cron",
            headers={"Authorization": f"Bearer {OPENCLAW_TOKEN}"},
            timeout=5
        )
        if resp.status_code == 200:
            data = resp.json()
            for job in data.get('jobs', []):
                if job.get('id') == CRON_JOB_ID:
                    return job
    except:
        pass
    return None

def trigger_cron_now():
    """Trigger cron job manually"""
    try:
        resp = requests.post(
            f"{OPENCLAW_API}/api/cron/{CRON_JOB_ID}/run",
            headers={"Authorization": f"Bearer {OPENCLAW_TOKEN}"},
            timeout=10
        )
        return resp.status_code == 200
    except:
        return False

# Bot status section
st.subheader("🤖 Bot Trading")

cron_status = get_cron_status()

if cron_status:
    col_countdown, col_last, col_trigger = st.columns([2, 2, 1])
    
    with col_countdown:
        next_run_ms = cron_status.get('state', {}).get('nextRunAtMs', 0)
        now_ms = int(time.time() * 1000)
        remaining_ms = max(0, next_run_ms - now_ms)
        remaining_sec = remaining_ms // 1000
        
        minutes = remaining_sec // 60
        seconds = remaining_sec % 60
        
        if remaining_sec > 0:
            st.metric(
                "⏱️ Prochain Run",
                f"{minutes:02d}:{seconds:02d}",
                delta="En attente" if cron_status.get('enabled') else "⏸️ Désactivé"
            )
        else:
            st.metric("⏱️ Prochain Run", "Imminent", delta="🔄 En cours...")
    
    with col_last:
        last_run_ms = cron_status.get('state', {}).get('lastRunAtMs', 0)
        last_status = cron_status.get('state', {}).get('lastStatus', 'unknown')
        last_duration = cron_status.get('state', {}).get('lastDurationMs', 0)
        
        if last_run_ms > 0:
            last_run_time = datetime.fromtimestamp(last_run_ms / 1000)
            time_ago = datetime.now() - last_run_time
            mins_ago = int(time_ago.total_seconds() / 60)
            
            status_icon = "✅" if last_status == "ok" else "❌"
            st.metric(
                "📊 Dernier Run",
                f"il y a {mins_ago}min",
                delta=f"{status_icon} {last_duration/1000:.1f}s"
            )
        else:
            st.metric("📊 Dernier Run", "Jamais", delta=None)
    
    with col_trigger:
        st.write("")  # Spacing
        if st.button("🚀 Run Now", use_container_width=True, type="primary"):
            with st.spinner("Déclenchement..."):
                if trigger_cron_now():
                    st.success("✅ Bot lancé!")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error("❌ Erreur")
else:
    st.warning("⚠️ Bot non configuré - Cron job introuvable")

st.markdown("---")

# ========== FETCH REAL DATA ==========
wallets = db.get_wallets()
stats = db.get_portfolio_stats()
paper_trades = db.get_paper_trades()
recent_trades = db.get_trades(limit=10)

# Calculate real portfolio value
total_portfolio_value = 0
wallet_balances = {}

# Try to get paper trading wallet values
import os
import json

WALLETS_DIR = os.path.join(os.path.dirname(__file__), '..', 'data', 'wallets')
WALLETS_CONFIG = os.path.join(WALLETS_DIR, 'config.json')
SIM_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'simulation.json')

def load_wallet_config():
    try:
        if os.path.exists(WALLETS_CONFIG):
            with open(WALLETS_CONFIG, 'r') as f:
                return json.load(f)
    except:
        pass
    return {'wallets': []}

def load_wallet_data(wallet_id):
    # Try wallets folder first
    wallet_path = os.path.join(WALLETS_DIR, f"{wallet_id}.json")
    if os.path.exists(wallet_path):
        with open(wallet_path, 'r') as f:
            return json.load(f)
    # Fallback to legacy simulation.json
    if wallet_id == 'simulation' and os.path.exists(SIM_PATH):
        with open(SIM_PATH, 'r') as f:
            return json.load(f)
    return {'portfolio': {'USDC': 0}, 'positions': {}}

# Load wallets from config
paper_wallet_config = load_wallet_config()
paper_wallets_data = []
real_wallets_data = []

for pw in paper_wallet_config.get('wallets', []):
    if not pw.get('enabled', True):
        continue
    
    wallet_id = pw.get('id', '')
    wallet_type = pw.get('type', 'paper')
    wallet_data = load_wallet_data(wallet_id)
    
    cash = wallet_data.get('portfolio', {}).get('USDC', 0)
    positions = wallet_data.get('positions', {})
    
    # Estimate positions value (use avg_price as fallback)
    positions_value = sum(
        p.get('amount', 0) * p.get('avg_price', 0) 
        for p in positions.values()
    )
    wallet_value = cash + positions_value
    
    wallet_info = {
        'id': wallet_id,
        'name': pw.get('name', wallet_id),
        'type': wallet_type,
        'address': pw.get('address', ''),
        'chain': pw.get('chain', 'base'),
        'cash': cash,
        'positions': positions,
        'positions_count': len(positions),
        'total_value': wallet_value,
        'max_positions': pw.get('max_positions', 10),
    }
    
    # Separate by type
    if wallet_type == 'real':
        real_wallets_data.append(wallet_info)
    else:
        paper_wallets_data.append(wallet_info)
    
    total_portfolio_value += wallet_value

# Also try on-chain balances for real wallets
try:
    from utils.balance import get_all_balances, get_prices
    BALANCE_AVAILABLE = True
except ImportError:
    BALANCE_AVAILABLE = False

if BALANCE_AVAILABLE and wallets:
    for wallet in wallets:
        try:
            if not wallet.address:
                continue
            balances = get_all_balances(wallet.address, wallet.network)
            if balances:
                symbols = [b.symbol for b in balances]
                prices = get_prices(symbols)
                wallet_value = sum(b.balance * prices.get(b.symbol, 0) for b in balances)
                wallet_balances[wallet.id] = {
                    'balances': balances,
                    'prices': prices,
                    'total_value': wallet_value
                }
                total_portfolio_value += wallet_value
        except Exception:
            wallet_balances[wallet.id] = {'balances': [], 'prices': {}, 'total_value': 0}

# Row 1: Métriques principales
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric(
        label="💰 Portfolio Total",
        value=f"${total_portfolio_value:,.2f}",
        delta=None
    )

with col2:
    total_wallets = len(paper_wallets_data) + stats.get('total_wallets', 0)
    st.metric(
        label="👛 Wallets",
        value=str(total_wallets),
        delta=f"{len(paper_wallets_data)} paper" if paper_wallets_data else None
    )

with col3:
    total_positions = sum(pw.get('positions_count', 0) for pw in paper_wallets_data)
    st.metric(
        label="📈 Positions",
        value=str(total_positions),
        delta="Paper trading" if paper_wallets_data else None
    )

with col4:
    recent_trades = stats.get('recent_trades_24h', 0)
    total_trades = stats.get('total_trades', 0)
    st.metric(
        label="📊 Trades (24h)",
        value=str(recent_trades),
        delta=f"Total: {total_trades}" if total_trades > 0 else None
    )

st.markdown("---")

# ========== PAPER TRADING WALLETS ==========
if paper_wallets_data:
    st.subheader("🎮 Paper Trading Wallets")
    
    for pw in paper_wallets_data:
        with st.container():
            col_info, col_cash, col_positions, col_value = st.columns([3, 2, 2, 2])
            
            with col_info:
                st.markdown(f"**{pw['name']}**")
                st.caption(f"ID: {pw['id']} | Max: {pw['max_positions']} positions")
            
            with col_cash:
                st.metric("💵 Cash", f"${pw['cash']:,.2f}")
            
            with col_positions:
                st.metric("📊 Positions", f"{pw['positions_count']}/{pw['max_positions']}")
            
            with col_value:
                st.metric("💰 Total", f"${pw['total_value']:,.2f}")
        
        st.markdown("---")

# ========== WALLETS RÉELS ==========
st.subheader("💳 Wallets Réels")

if real_wallets_data:
    for rw in real_wallets_data:
        with st.container():
            col_info, col_cash, col_positions, col_value = st.columns([3, 2, 2, 2])
            
            with col_info:
                chain_icon = {'base': '🔵', 'ethereum': '🔷', 'arbitrum': '🔶'}.get(rw['chain'], '⛓️')
                st.markdown(f"**🟢 {rw['name']}**")
                st.caption(f"{chain_icon} {rw['chain'].upper()} | `{rw['address'][:10]}...{rw['address'][-6:]}`")
            
            with col_cash:
                st.metric("💵 Balance", f"${rw['cash']:,.2f}")
            
            with col_positions:
                st.metric("📊 Positions", f"{rw['positions_count']}/{rw['max_positions']}")
            
            with col_value:
                st.metric("💰 Total", f"${rw['total_value']:,.2f}")
            
            # Show positions tokens if any
            if rw['positions']:
                tokens_str = ", ".join([f"{sym}: {p.get('amount', 0):.2f}" for sym, p in list(rw['positions'].items())[:3]])
                st.caption(f"🪙 {tokens_str}")
        
        st.markdown("---")
else:
    st.info("💳 Aucun wallet réel configuré.")

# ========== VUE WALLETS (Database - legacy) ==========
if wallets:
    st.subheader("👛 Wallets On-Chain (DB)")
    
    for wallet in wallets:
        wallet_data = wallet_balances.get(wallet.id, {'total_value': 0, 'balances': []})
        balance_value = wallet_data['total_value']
        balances = wallet_data.get('balances', [])
        
        with st.container():
            col_info, col_balance, col_tokens, col_action = st.columns([3, 2, 3, 1])
            
            with col_info:
                network_icon = SUPPORTED_NETWORKS.get(wallet.network, {}).get('icon', '🔗')
                status_icon = "🟢" if wallet.is_active else "⚪"
                st.markdown(f"**{status_icon} {wallet.name}**")
                st.caption(f"{network_icon} {wallet.network.upper()} | `{wallet.address[:10]}...{wallet.address[-6:]}`")
            
            with col_balance:
                st.metric("Balance", f"${balance_value:,.2f}")
            
            with col_tokens:
                if balances:
                    prices = wallet_data.get('prices', {})
                    tokens_str = ", ".join([f"{b.symbol}: {b.balance:.4f}" for b in balances[:3]])
                    st.caption(f"🪙 {tokens_str}")
                else:
                    st.caption("📭 Aucun token")
            
            with col_action:
                if st.button("👁️", key=f"view_{wallet.id}", help="Voir détails"):
                    st.switch_page("pages/1_wallet.py")
        
        st.markdown("---")

# ========== ALLOCATION PIE CHART ==========
if total_portfolio_value > 0 and BALANCE_AVAILABLE:
    st.subheader("🪙 Allocation du Portfolio")
    
    # Aggregate all tokens across wallets
    all_tokens = {}
    for wallet_id, data in wallet_balances.items():
        for b in data.get('balances', []):
            price = data['prices'].get(b.symbol, 0)
            value = b.balance * price
            if b.symbol in all_tokens:
                all_tokens[b.symbol] += value
            else:
                all_tokens[b.symbol] = value
    
    if all_tokens:
        allocation_data = pd.DataFrame({
            'Token': list(all_tokens.keys()),
            'Valeur': list(all_tokens.values())
        })
        
        fig_pie = px.pie(
            allocation_data,
            values='Valeur',
            names='Token',
            color_discrete_sequence=['#667eea', '#00b894', '#fdcb6e', '#e17055', '#74b9ff', '#636e72'],
            hole=0.4
        )
        fig_pie.update_layout(
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)',
            height=350,
            showlegend=True
        )
        fig_pie.update_traces(textposition='inside', textinfo='percent+label')
        st.plotly_chart(fig_pie, use_container_width=True)

# ========== STRATEGIES ACTIVES ==========
st.markdown("---")
col_strats, col_trades = st.columns(2)

with col_strats:
    st.subheader("📝 Paper Trading")
    
    if paper_trades:
        for strategy in paper_trades:
            wallet = next((w for w in wallets if w.id == strategy.wallet_id), None)
            wallet_name = wallet.name if wallet else "N/A"
            
            type_icons = {
                'DCA': '📊',
                'GRID': '📐',
                'LIMIT': '🎯',
                'SNIPER': '🔫',
            }
            icon = type_icons.get(strategy.strategy_type.upper(), '🤖')
            
            last_run_str = strategy.last_run.strftime("%H:%M:%S") if strategy.last_run else "Jamais"
            
            cols = st.columns([3, 2, 1])
            with cols[0]:
                st.markdown(f"**{icon} {strategy.name}**")
                st.caption(f"{strategy.strategy_type} | {wallet_name}")
            with cols[1]:
                st.caption(f"⏱️ {last_run_str}")
            with cols[2]:
                st.markdown("🟢")
            st.markdown("---")
    else:
        st.info("🎯 Aucune stratégie active.")
        if st.button("➕ Créer une Stratégie", use_container_width=True):
            st.switch_page("pages/8_simulation.py")

with col_trades:
    st.subheader("📜 Derniers Trades")
    
    if recent_trades:
        for trade in recent_trades[:7]:
            trade_type = trade.get('trade_type', 'swap')
            token_in = trade.get('token_in', '?')
            token_out = trade.get('token_out', '?')
            amount = trade.get('amount_in', '0')
            status = trade.get('status', 'pending')
            
            status_icons = {'pending': '⏳', 'confirmed': '✅', 'failed': '❌'}
            type_colors = {'buy': '🟢', 'sell': '🔴', 'swap': '🔄'}
            
            cols = st.columns([1, 3, 2, 1])
            cols[0].write(type_colors.get(trade_type, '🔄'))
            cols[1].markdown(f"**{token_in} → {token_out}**")
            cols[2].caption(amount)
            cols[3].write(status_icons.get(status, '⏳'))
    else:
        st.info("📭 Aucun trade enregistré")
        st.caption("Les trades apparaîtront ici une fois que le bot sera actif")

# ========== FOOTER ACTIONS ==========
st.markdown("---")
st.subheader("⚡ Navigation")

action_cols = st.columns(5)

with action_cols[0]:
    if st.button("👛 Wallets", use_container_width=True, type="primary"):
        st.switch_page("pages/1_wallet.py")

with action_cols[1]:
    if st.button("📈 Trades", use_container_width=True):
        st.switch_page("pages/2_trades.py")

with action_cols[2]:
    if st.button("📡 Signaux", use_container_width=True):
        st.switch_page("pages/3_signals.py")

with action_cols[3]:
    if st.button("📝 Simulation", use_container_width=True):
        st.switch_page("pages/8_simulation.py")

with action_cols[4]:
    if st.button("⚙️ Settings", use_container_width=True):
        st.switch_page("pages/5_settings.py")
