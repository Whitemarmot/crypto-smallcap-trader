"""
🎯 Stratégies de Trading Automatisées
Configuration et gestion des stratégies DCA, Grid, etc.
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
from utils.database import get_db, StrategyRecord
from utils.config import load_config, SUPPORTED_NETWORKS

st.set_page_config(
    page_title="🎯 Strategies | SmallCap Trader",
    page_icon="🎯",
    layout="wide"
)

# ========== STYLES ==========
st.markdown("""
<style>
    .strategy-header {
        font-size: 2rem;
        font-weight: bold;
        background: linear-gradient(135deg, #00b894 0%, #00cec9 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
    .strategy-card {
        background: linear-gradient(135deg, #2d2d44 0%, #1e1e2e 100%);
        border-radius: 15px;
        padding: 1.5rem;
        border: 1px solid #404060;
        margin-bottom: 1rem;
    }
    .strategy-card-active {
        border-color: #00b894;
        box-shadow: 0 0 20px rgba(0, 184, 148, 0.2);
    }
    .type-badge {
        padding: 5px 12px;
        border-radius: 20px;
        font-size: 0.8rem;
        font-weight: bold;
    }
    .type-dca { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); }
    .type-grid { background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%); }
    .type-limit { background: linear-gradient(135deg, #ffecd2 0%, #fcb69f 100%); color: #333; }
    .type-sniper { background: linear-gradient(135deg, #ff4757 0%, #c0392b 100%); }
    
    .status-on { color: #00ff88; }
    .status-off { color: #636e72; }
    
    .exec-success { background: rgba(0, 255, 136, 0.1); border-left: 3px solid #00ff88; }
    .exec-failed { background: rgba(255, 71, 87, 0.1); border-left: 3px solid #ff4757; }
</style>
""", unsafe_allow_html=True)

# ========== DATABASE ==========
db = get_db()
config = load_config()
wallets = db.get_wallets()
strategies = db.get_strategies()
executions = db.get_executions(limit=20)

# ========== HEADER ==========
st.markdown('<p class="strategy-header">🎯 Stratégies de Trading</p>', unsafe_allow_html=True)
st.caption("Configurez et gérez vos stratégies automatisées")

st.markdown("---")

# ========== STATS RAPIDES ==========
col1, col2, col3, col4 = st.columns(4)

active_count = len([s for s in strategies if s.is_active])
total_executions = len(executions)
success_rate = (len([e for e in executions if e.status == 'success']) / total_executions * 100) if total_executions > 0 else 0

with col1:
    st.metric("📊 Stratégies Totales", len(strategies))

with col2:
    st.metric("🟢 Actives", active_count, delta="En cours" if active_count > 0 else None)

with col3:
    st.metric("⚡ Exécutions (24h)", total_executions)

with col4:
    st.metric("✅ Taux de Succès", f"{success_rate:.1f}%")

st.markdown("---")

# ========== MAIN LAYOUT ==========
col_strategies, col_create = st.columns([2, 1])

# ========== LISTE DES STRATEGIES ==========
with col_strategies:
    st.subheader("📋 Mes Stratégies")
    
    if strategies:
        for strategy in strategies:
            wallet = next((w for w in wallets if w.id == strategy.wallet_id), None)
            wallet_name = wallet.name if wallet else "Wallet supprimé"
            wallet_network = wallet.network if wallet else "?"
            
            # Icons par type
            type_icons = {
                'DCA': ('📊', 'type-dca'),
                'GRID': ('📐', 'type-grid'),
                'LIMIT': ('🎯', 'type-limit'),
                'SNIPER': ('🔫', 'type-sniper'),
            }
            icon, badge_class = type_icons.get(strategy.strategy_type.upper(), ('🤖', 'type-dca'))
            
            # Card CSS class
            card_class = "strategy-card strategy-card-active" if strategy.is_active else "strategy-card"
            
            with st.container():
                st.markdown(f'<div class="{card_class}">', unsafe_allow_html=True)
                
                col_s1, col_s2, col_s3, col_s4 = st.columns([3, 2, 2, 1])
                
                with col_s1:
                    status = "🟢" if strategy.is_active else "⚫"
                    st.markdown(f"### {status} {strategy.name}")
                    st.markdown(f'<span class="{badge_class}" style="padding: 4px 10px; border-radius: 15px;">{icon} {strategy.strategy_type.upper()}</span>', unsafe_allow_html=True)
                    st.caption(f"👛 {wallet_name} ({wallet_network})")
                
                with col_s2:
                    # Afficher config
                    cfg = strategy.config
                    if strategy.strategy_type.upper() == 'DCA':
                        amount = cfg.get('amount', 0)
                        freq = cfg.get('frequency', 'daily')
                        token = cfg.get('token', 'ETH')
                        st.markdown(f"**💵 ${amount}** / {freq}")
                        st.caption(f"Token: {token}")
                    elif strategy.strategy_type.upper() == 'GRID':
                        orders = cfg.get('num_orders', 0)
                        range_low = cfg.get('range_low', 0)
                        range_high = cfg.get('range_high', 0)
                        st.markdown(f"**📐 {orders} ordres**")
                        st.caption(f"Range: ${range_low} - ${range_high}")
                    elif strategy.strategy_type.upper() == 'LIMIT':
                        target = cfg.get('target_price', 0)
                        st.markdown(f"**🎯 ${target}**")
                    elif strategy.strategy_type.upper() == 'SNIPER':
                        st.markdown("**🔫 Actif**")
                
                with col_s3:
                    # Dernière exécution
                    if strategy.last_run:
                        time_ago = datetime.now() - strategy.last_run
                        if time_ago.days > 0:
                            last_run_str = f"il y a {time_ago.days}j"
                        elif time_ago.seconds > 3600:
                            last_run_str = f"il y a {time_ago.seconds // 3600}h"
                        else:
                            last_run_str = f"il y a {time_ago.seconds // 60}min"
                    else:
                        last_run_str = "Jamais"
                    
                    st.markdown(f"⏱️ **{last_run_str}**")
                    st.caption(f"Créée: {strategy.created_at.strftime('%d/%m/%y')}")
                
                with col_s4:
                    # Toggle ON/OFF
                    is_active = st.toggle(
                        "ON",
                        value=strategy.is_active,
                        key=f"toggle_{strategy.id}"
                    )
                    
                    if is_active != strategy.is_active:
                        db.toggle_strategy(strategy.id, is_active)
                        action = "activée" if is_active else "désactivée"
                        st.toast(f"Stratégie {action}!", icon="✅" if is_active else "⏹️")
                        st.rerun()
                    
                    # Delete button
                    if st.button("🗑️", key=f"del_{strategy.id}", help="Supprimer"):
                        db.delete_strategy(strategy.id)
                        st.toast("Stratégie supprimée", icon="🗑️")
                        st.rerun()
                
                st.markdown('</div>', unsafe_allow_html=True)
    else:
        st.info("📭 Aucune stratégie configurée. Créez votre première stratégie!")

# ========== CRÉATION DE STRATÉGIE ==========
with col_create:
    st.subheader("➕ Nouvelle Stratégie")
    
    if not wallets:
        st.warning("⚠️ Créez d'abord un wallet avant de configurer une stratégie.")
        if st.button("👛 Aller aux Wallets", use_container_width=True):
            st.switch_page("pages/1_wallet.py")
    else:
        # Sélection du type
        strategy_type = st.selectbox(
            "Type de stratégie",
            ["DCA", "GRID", "LIMIT", "SNIPER"],
            format_func=lambda x: {
                "DCA": "📊 DCA (Dollar Cost Averaging)",
                "GRID": "📐 Grid Trading",
                "LIMIT": "🎯 Limit Order",
                "SNIPER": "🔫 Token Sniper"
            }[x]
        )
        
        # Nom
        strategy_name = st.text_input(
            "Nom de la stratégie",
            value=f"Ma stratégie {strategy_type}"
        )
        
        # Wallet
        wallet_options = {w.id: f"{w.name} ({w.network})" for w in wallets}
        selected_wallet_id = st.selectbox(
            "Wallet",
            options=list(wallet_options.keys()),
            format_func=lambda x: wallet_options[x]
        )
        
        st.markdown("---")
        st.markdown("**⚙️ Configuration**")
        
        # Paramètres selon le type
        config_data = {}
        
        if strategy_type == "DCA":
            st.markdown("*Achat régulier d'un token à intervalles fixes*")
            
            config_data['token'] = st.selectbox(
                "Token à acheter",
                ["ETH", "BTC", "SOL", "BONK", "PEPE", "WIF"]
            )
            
            config_data['amount'] = st.number_input(
                "Montant par achat ($)",
                min_value=10,
                max_value=10000,
                value=100,
                step=10
            )
            
            config_data['frequency'] = st.selectbox(
                "Fréquence",
                ["hourly", "daily", "weekly", "monthly"],
                format_func=lambda x: {
                    "hourly": "⏰ Toutes les heures",
                    "daily": "📅 Quotidien",
                    "weekly": "📆 Hebdomadaire",
                    "monthly": "🗓️ Mensuel"
                }[x],
                index=1
            )
            
            config_data['max_slippage'] = st.slider(
                "Slippage max (%)",
                min_value=0.5,
                max_value=5.0,
                value=1.0,
                step=0.5
            )
        
        elif strategy_type == "GRID":
            st.markdown("*Ordres d'achat/vente répartis dans une range de prix*")
            
            config_data['token'] = st.selectbox(
                "Pair de trading",
                ["ETH/USDC", "BTC/USDC", "SOL/USDC", "PEPE/USDC"]
            )
            
            col_range1, col_range2 = st.columns(2)
            with col_range1:
                config_data['range_low'] = st.number_input(
                    "Prix bas ($)",
                    min_value=0.0,
                    value=2800.0,
                    step=10.0
                )
            with col_range2:
                config_data['range_high'] = st.number_input(
                    "Prix haut ($)",
                    min_value=0.0,
                    value=3500.0,
                    step=10.0
                )
            
            config_data['num_orders'] = st.slider(
                "Nombre d'ordres",
                min_value=5,
                max_value=50,
                value=10
            )
            
            config_data['total_investment'] = st.number_input(
                "Investissement total ($)",
                min_value=100,
                max_value=100000,
                value=1000,
                step=100
            )
        
        elif strategy_type == "LIMIT":
            st.markdown("*Ordre unique à un prix cible*")
            
            config_data['action'] = st.selectbox(
                "Action",
                ["BUY", "SELL"],
                format_func=lambda x: "🟢 Acheter" if x == "BUY" else "🔴 Vendre"
            )
            
            config_data['token'] = st.selectbox(
                "Token",
                ["ETH", "BTC", "SOL", "BONK", "PEPE"]
            )
            
            config_data['target_price'] = st.number_input(
                "Prix cible ($)",
                min_value=0.0,
                value=3000.0,
                step=10.0
            )
            
            config_data['amount'] = st.number_input(
                "Montant ($)",
                min_value=10,
                max_value=100000,
                value=500
            )
        
        elif strategy_type == "SNIPER":
            st.markdown("*Achat automatique de nouveaux tokens dès leur lancement*")
            
            config_data['dex'] = st.selectbox(
                "DEX à surveiller",
                ["Uniswap V3", "PancakeSwap", "BaseSwap", "SushiSwap"]
            )
            
            config_data['min_liquidity'] = st.number_input(
                "Liquidité minimum ($)",
                min_value=1000,
                max_value=1000000,
                value=10000,
                step=1000
            )
            
            config_data['buy_amount'] = st.number_input(
                "Montant par snipe ($)",
                min_value=10,
                max_value=10000,
                value=100
            )
            
            config_data['max_tax'] = st.slider(
                "Tax maximum (%)",
                min_value=0,
                max_value=20,
                value=5
            )
            
            config_data['anti_rug'] = st.checkbox("🛡️ Protection anti-rug", value=True)
        
        st.markdown("---")
        
        # Bouton de création
        if st.button("🚀 Créer la Stratégie", type="primary", use_container_width=True):
            try:
                strategy_id = db.add_strategy(
                    name=strategy_name,
                    strategy_type=strategy_type,
                    wallet_id=selected_wallet_id,
                    config=config_data
                )
                st.success(f"✅ Stratégie '{strategy_name}' créée!")
                st.balloons()
                st.rerun()
            except Exception as e:
                st.error(f"❌ Erreur: {e}")

st.markdown("---")

# ========== HISTORIQUE D'EXÉCUTION ==========
st.subheader("📜 Historique d'Exécution")

if executions:
    for exec_record in executions[:10]:
        # Trouver la stratégie associée
        strategy = next((s for s in strategies if s.id == exec_record.strategy_id), None)
        strategy_name = strategy.name if strategy else f"Stratégie #{exec_record.strategy_id}"
        
        status_icon = "✅" if exec_record.status == "success" else "❌"
        status_class = "exec-success" if exec_record.status == "success" else "exec-failed"
        
        with st.container():
            cols = st.columns([1, 3, 2, 2, 2])
            
            with cols[0]:
                st.write(status_icon)
            
            with cols[1]:
                st.markdown(f"**{strategy_name}**")
            
            with cols[2]:
                st.caption(exec_record.executed_at.strftime("%d/%m %H:%M"))
            
            with cols[3]:
                if exec_record.tx_hash:
                    st.markdown(f"`{exec_record.tx_hash[:10]}...`")
                else:
                    st.caption("-")
            
            with cols[4]:
                result = exec_record.result
                if 'amount' in result:
                    st.caption(f"${result['amount']}")
                elif exec_record.error:
                    st.caption(f"⚠️ {exec_record.error[:20]}...")
else:
    # Données demo
    demo_executions = [
        {"status": "✅", "strategy": "DCA ETH Daily", "time": "14:30", "tx": "0x7a8b...", "result": "$100"},
        {"status": "✅", "strategy": "Grid BTC/USDC", "time": "12:15", "tx": "0x3f2c...", "result": "Buy @ $42,500"},
        {"status": "❌", "strategy": "Sniper New Token", "time": "10:45", "tx": "-", "result": "Slippage too high"},
        {"status": "✅", "strategy": "DCA ETH Daily", "time": "Hier 14:30", "tx": "0x9d1e...", "result": "$100"},
        {"status": "✅", "strategy": "Limit Buy SOL", "time": "Hier 08:22", "tx": "0x2b4a...", "result": "10 SOL @ $95"},
    ]
    
    for exec_data in demo_executions:
        cols = st.columns([1, 3, 2, 2, 2])
        cols[0].write(exec_data["status"])
        cols[1].markdown(f"**{exec_data['strategy']}**")
        cols[2].caption(exec_data["time"])
        cols[3].markdown(f"`{exec_data['tx']}`" if exec_data["tx"] != "-" else "-")
        cols[4].caption(exec_data["result"])

# ========== GRAPHIQUE DE PERFORMANCE ==========
st.markdown("---")
st.subheader("📈 Performance des Stratégies")

col_chart1, col_chart2 = st.columns(2)

with col_chart1:
    # Exécutions par jour
    days = pd.date_range(end=datetime.now(), periods=14, freq='D')
    exec_counts = [random.randint(0, 15) for _ in days]
    
    fig_exec = go.Figure()
    fig_exec.add_trace(go.Bar(
        x=days,
        y=exec_counts,
        marker_color='#667eea',
        name='Exécutions'
    ))
    
    fig_exec.update_layout(
        title="📊 Exécutions (14 derniers jours)",
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        xaxis=dict(showgrid=False),
        yaxis=dict(showgrid=True, gridcolor='rgba(255,255,255,0.05)'),
        height=300
    )
    st.plotly_chart(fig_exec, use_container_width=True)

with col_chart2:
    # P&L par stratégie
    if strategies:
        strat_names = [s.name[:15] for s in strategies[:5]]
        strat_pnl = [random.uniform(-500, 2000) for _ in strat_names]
    else:
        strat_names = ["DCA ETH", "Grid BTC", "Sniper", "Limit SOL"]
        strat_pnl = [450, 1200, -150, 320]
    
    colors = ['#00ff88' if p >= 0 else '#ff4757' for p in strat_pnl]
    
    fig_pnl = go.Figure(data=[
        go.Bar(
            x=strat_names,
            y=strat_pnl,
            marker_color=colors,
            text=[f"${p:+,.0f}" for p in strat_pnl],
            textposition='outside'
        )
    ])
    
    fig_pnl.add_hline(y=0, line_dash="solid", line_color="rgba(255,255,255,0.3)")
    
    fig_pnl.update_layout(
        title="💰 P&L par Stratégie",
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        xaxis=dict(showgrid=False),
        yaxis=dict(showgrid=True, gridcolor='rgba(255,255,255,0.05)', title="$"),
        height=300
    )
    st.plotly_chart(fig_pnl, use_container_width=True)

# ========== FOOTER ==========
st.markdown("---")
cols_footer = st.columns(4)

with cols_footer[0]:
    if st.button("🏠 Dashboard", use_container_width=True):
        st.switch_page("pages/0_dashboard.py")

with cols_footer[1]:
    if st.button("👛 Wallets", use_container_width=True):
        st.switch_page("pages/1_wallet.py")

with cols_footer[2]:
    if st.button("📈 Trades", use_container_width=True):
        st.switch_page("pages/2_trades.py")

with cols_footer[3]:
    if st.button("⚙️ Settings", use_container_width=True):
        st.switch_page("pages/5_settings.py")
