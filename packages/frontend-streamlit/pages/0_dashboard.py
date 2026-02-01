"""
🏠 Dashboard Principal - Vue Multi-Wallet
Vue globale de tous les wallets, stratégies actives et performance
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import random
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
    .strategy-badge {
        background: linear-gradient(135deg, #00b894 0%, #00cec9 100%);
        padding: 4px 12px;
        border-radius: 20px;
        font-size: 0.8rem;
        display: inline-block;
    }
    .strategy-badge-inactive {
        background: linear-gradient(135deg, #636e72 0%, #2d3436 100%);
    }
    .metric-box {
        background: linear-gradient(135deg, #2d2d44 0%, #1e1e2e 100%);
        border-radius: 10px;
        padding: 1rem;
        border: 1px solid #404060;
        text-align: center;
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
    st.caption(f"🌐 Réseau actif: {config.active_network.upper()} | ⏰ Dernière MAJ: {datetime.now().strftime('%H:%M:%S')}")

with col_refresh:
    if st.button("🔄 Rafraîchir", use_container_width=True):
        st.rerun()

st.markdown("---")

# ========== PORTFOLIO STATS ==========
stats = db.get_portfolio_stats()
wallets = db.get_wallets()
active_strategies = db.get_active_strategies()
recent_trades = db.get_trades(limit=10)

# Simulation de valeurs portfolio (à remplacer par vraies données)
total_portfolio_value = sum([random.uniform(1000, 5000) for _ in wallets]) if wallets else 0
daily_pnl = random.uniform(-500, 800)
daily_pnl_pct = (daily_pnl / total_portfolio_value * 100) if total_portfolio_value > 0 else 0

# Row 1: Métriques principales
col1, col2, col3, col4, col5 = st.columns(5)

with col1:
    st.metric(
        label="💰 Portfolio Total",
        value=f"${total_portfolio_value:,.2f}",
        delta=f"${daily_pnl:+,.2f} ({daily_pnl_pct:+.1f}%)" if total_portfolio_value > 0 else None,
        delta_color="normal" if daily_pnl >= 0 else "inverse"
    )

with col2:
    st.metric(
        label="👛 Wallets",
        value=str(stats['total_wallets']),
        delta=f"{len([w for w in wallets if w.is_active])} actif" if wallets else None
    )

with col3:
    st.metric(
        label="🎯 Stratégies Actives",
        value=str(stats['active_strategies']),
        delta="En cours" if stats['active_strategies'] > 0 else "Aucune"
    )

with col4:
    st.metric(
        label="📊 Trades (24h)",
        value=str(stats['recent_trades_24h']),
        delta=f"Total: {stats['total_trades']}"
    )

with col5:
    win_rate = random.uniform(55, 85)  # À remplacer par vraies données
    st.metric(
        label="🎯 Win Rate",
        value=f"{win_rate:.1f}%",
        delta=f"+{random.uniform(0.5, 3):.1f}%" if win_rate > 60 else f"-{random.uniform(0.5, 2):.1f}%"
    )

st.markdown("---")

# ========== VUE WALLETS & GRAPHIQUE ==========
col_wallets, col_chart = st.columns([1, 2])

with col_wallets:
    st.subheader("👛 Vue Wallets")
    
    if wallets:
        for wallet in wallets:
            # Simulation balance
            balance = random.uniform(500, 5000)
            pnl_24h = random.uniform(-10, 15)
            
            with st.container():
                network_icon = SUPPORTED_NETWORKS.get(wallet.network, {}).get('icon', '🔗')
                status_icon = "🟢" if wallet.is_active else "⚪"
                
                st.markdown(f"""
                <div class="wallet-card">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <span>{status_icon} <strong>{wallet.name}</strong></span>
                        <span>{network_icon} {wallet.network.upper()}</span>
                    </div>
                    <div style="font-size: 0.8rem; color: #888; margin: 5px 0;">
                        {wallet.address[:8]}...{wallet.address[-6:]}
                    </div>
                    <div style="display: flex; justify-content: space-between; margin-top: 8px;">
                        <span style="font-size: 1.2rem; font-weight: bold;">${balance:,.2f}</span>
                        <span class="{'profit-green' if pnl_24h >= 0 else 'loss-red'}">{pnl_24h:+.2f}%</span>
                    </div>
                </div>
                """, unsafe_allow_html=True)
    else:
        st.info("👛 Aucun wallet configuré. Allez dans la page Wallet pour en ajouter un.")
        if st.button("➕ Ajouter un Wallet", use_container_width=True):
            st.switch_page("pages/1_wallet.py")

with col_chart:
    st.subheader("📈 Performance Globale (30j)")
    
    # Génération données de démo
    dates = pd.date_range(start=datetime.now() - timedelta(days=30), end=datetime.now(), freq='D')
    base_value = total_portfolio_value * 0.85 if total_portfolio_value > 0 else 10000
    values = [base_value]
    for i in range(1, len(dates)):
        change = random.uniform(-0.025, 0.035)
        values.append(values[-1] * (1 + change))
    
    df_perf = pd.DataFrame({
        'Date': dates,
        'Valeur ($)': values
    })
    
    fig = go.Figure()
    
    # Area chart avec gradient
    fig.add_trace(go.Scatter(
        x=df_perf['Date'],
        y=df_perf['Valeur ($)'],
        fill='tozeroy',
        fillcolor='rgba(102, 126, 234, 0.2)',
        line=dict(color='#667eea', width=3),
        name='Portfolio'
    ))
    
    # Ligne de départ (benchmark)
    fig.add_hline(y=base_value, line_dash="dot", line_color="rgba(255,255,255,0.3)",
                  annotation_text="Start", annotation_position="right")
    
    fig.update_layout(
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        xaxis=dict(showgrid=False, title=None),
        yaxis=dict(showgrid=True, gridcolor='rgba(255,255,255,0.05)', title="$"),
        height=350,
        margin=dict(l=0, r=0, t=10, b=0),
        showlegend=False
    )
    st.plotly_chart(fig, use_container_width=True)

st.markdown("---")

# ========== STRATEGIES ACTIVES ==========
col_strats, col_trades = st.columns(2)

with col_strats:
    st.subheader("🎯 Stratégies Actives")
    
    if active_strategies:
        for strategy in active_strategies:
            wallet = next((w for w in wallets if w.id == strategy.wallet_id), None)
            wallet_name = wallet.name if wallet else "N/A"
            
            config_info = strategy.config
            
            # Type icons
            type_icons = {
                'DCA': '📊',
                'GRID': '📐',
                'LIMIT': '🎯',
                'SNIPER': '🔫',
                'ARBITRAGE': '⚡'
            }
            icon = type_icons.get(strategy.strategy_type.upper(), '🤖')
            
            # Last run info
            if strategy.last_run:
                last_run_str = strategy.last_run.strftime("%H:%M:%S")
            else:
                last_run_str = "Jamais"
            
            with st.container():
                cols = st.columns([3, 2, 2, 1])
                
                with cols[0]:
                    st.markdown(f"**{icon} {strategy.name}**")
                    st.caption(f"Type: {strategy.strategy_type} | Wallet: {wallet_name}")
                
                with cols[1]:
                    if strategy.strategy_type.upper() == 'DCA':
                        amount = config_info.get('amount', 0)
                        freq = config_info.get('frequency', 'daily')
                        st.caption(f"💵 ${amount}/{freq}")
                    elif strategy.strategy_type.upper() == 'GRID':
                        orders = config_info.get('num_orders', 0)
                        st.caption(f"📐 {orders} ordres")
                
                with cols[2]:
                    st.caption(f"⏱️ {last_run_str}")
                
                with cols[3]:
                    st.markdown("🟢 ON")
            
            st.markdown("---")
    else:
        st.info("🎯 Aucune stratégie active.")
        if st.button("➕ Créer une Stratégie", use_container_width=True):
            st.switch_page("pages/4_strategies.py")

with col_trades:
    st.subheader("📜 Derniers Trades")
    
    if recent_trades:
        for trade in recent_trades[:7]:
            trade_type = trade.get('trade_type', 'swap')
            token_in = trade.get('token_in', 'ETH')
            token_out = trade.get('token_out', 'USDC')
            amount = trade.get('amount_in', '0')
            status = trade.get('status', 'pending')
            
            status_icons = {
                'pending': '⏳',
                'confirmed': '✅',
                'failed': '❌'
            }
            
            type_colors = {
                'buy': '🟢',
                'sell': '🔴',
                'swap': '🔄'
            }
            
            cols = st.columns([1, 3, 2, 1])
            
            with cols[0]:
                st.write(type_colors.get(trade_type, '🔄'))
            
            with cols[1]:
                st.markdown(f"**{token_in} → {token_out}**")
            
            with cols[2]:
                st.caption(amount)
            
            with cols[3]:
                st.write(status_icons.get(status, '⏳'))
    else:
        # Générer trades demo
        demo_trades = [
            {"type": "🟢", "pair": "ETH → PEPE", "amount": "0.5 ETH", "status": "✅"},
            {"type": "🔴", "pair": "BONK → USDC", "amount": "$250", "status": "✅"},
            {"type": "🟢", "pair": "USDC → WIF", "amount": "$100", "status": "✅"},
            {"type": "🔄", "pair": "SHIB → PEPE", "amount": "$75", "status": "⏳"},
            {"type": "🟢", "pair": "ETH → JUP", "amount": "0.2 ETH", "status": "✅"},
        ]
        
        for trade in demo_trades:
            cols = st.columns([1, 3, 2, 1])
            cols[0].write(trade["type"])
            cols[1].markdown(f"**{trade['pair']}**")
            cols[2].caption(trade["amount"])
            cols[3].write(trade["status"])

st.markdown("---")

# ========== ALLOCATION PIE CHART ==========
st.subheader("🪙 Allocation Globale du Portfolio")

col_pie, col_perf = st.columns(2)

with col_pie:
    # Données d'allocation simulées
    allocation_data = {
        'Token': ['ETH', 'USDC', 'PEPE', 'BONK', 'WIF', 'Autres'],
        'Valeur': [4500, 2000, 800, 600, 400, 300]
    }
    df_alloc = pd.DataFrame(allocation_data)
    
    fig_pie = px.pie(
        df_alloc,
        values='Valeur',
        names='Token',
        color_discrete_sequence=['#667eea', '#00b894', '#fdcb6e', '#e17055', '#74b9ff', '#636e72'],
        hole=0.4
    )
    fig_pie.update_layout(
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        height=350,
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=-0.3)
    )
    fig_pie.update_traces(textposition='inside', textinfo='percent+label')
    st.plotly_chart(fig_pie, use_container_width=True)

with col_perf:
    # Performance par wallet
    st.markdown("**📊 Performance par Wallet**")
    
    if wallets:
        wallet_perf = []
        for wallet in wallets:
            perf = random.uniform(-15, 35)
            wallet_perf.append({
                'Wallet': wallet.name,
                'Performance (%)': perf,
                'Color': '#00ff88' if perf >= 0 else '#ff4757'
            })
        
        df_wallet_perf = pd.DataFrame(wallet_perf)
        
        fig_bar = go.Figure(data=[
            go.Bar(
                x=df_wallet_perf['Wallet'],
                y=df_wallet_perf['Performance (%)'],
                marker_color=df_wallet_perf['Color'],
                text=[f"{p:+.1f}%" for p in df_wallet_perf['Performance (%)']],
                textposition='outside'
            )
        ])
        
        fig_bar.add_hline(y=0, line_dash="solid", line_color="rgba(255,255,255,0.3)")
        
        fig_bar.update_layout(
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)',
            xaxis=dict(showgrid=False),
            yaxis=dict(showgrid=True, gridcolor='rgba(255,255,255,0.05)', title="% Change"),
            height=350,
            margin=dict(t=40)
        )
        st.plotly_chart(fig_bar, use_container_width=True)
    else:
        st.info("Ajoutez des wallets pour voir leurs performances.")

# ========== FOOTER ACTIONS ==========
st.markdown("---")
st.subheader("⚡ Actions Rapides")

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
    if st.button("🎯 Stratégies", use_container_width=True):
        st.switch_page("pages/4_strategies.py")

with action_cols[4]:
    if st.button("⚙️ Settings", use_container_width=True):
        st.switch_page("pages/5_settings.py")
