"""
🎯 Stratégies de Trading Automatisées
Configuration et gestion des stratégies DCA, Limit Orders, Stop Loss.

⚠️ TOUTES LES STRATÉGIES SONT EN MODE DRY RUN PAR DÉFAUT
   Les vrais trades nécessitent une confirmation explicite.
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import sys
import os
import uuid

# Add utils to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from utils.database import get_db, StrategyRecord
from utils.config import load_config, SUPPORTED_NETWORKS

# Import trading utilities
try:
    from utils.trading import (
        NETWORKS, sync_get_quote, sync_simulate_swap,
        get_tokens_for_network, create_dca_strategy,
        create_limit_order, create_stop_loss,
        calculate_dca_projection, get_price_for_stop_loss
    )
    TRADING_AVAILABLE = True
except ImportError as e:
    TRADING_AVAILABLE = False
    TRADING_ERROR = str(e)

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
    .type-limit { background: linear-gradient(135deg, #ffecd2 0%, #fcb69f 100%); color: #333; }
    .type-stoploss { background: linear-gradient(135deg, #ff4757 0%, #c0392b 100%); }
    
    .status-on { color: #00ff88; }
    .status-off { color: #636e72; }
    
    .dry-run-badge {
        background: linear-gradient(135deg, #f39c12 0%, #e67e22 100%);
        color: white;
        padding: 3px 8px;
        border-radius: 10px;
        font-size: 0.7rem;
        font-weight: bold;
    }
    
    .warning-box {
        background: rgba(241, 196, 15, 0.1);
        border: 1px solid #f1c40f;
        border-radius: 10px;
        padding: 1rem;
        margin: 1rem 0;
    }
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
st.caption("Configurez et gérez vos stratégies automatisées (DCA, Limit Orders, Stop Loss)")

# Warning banner
st.markdown("""
<div class="warning-box">
    ⚠️ <strong>MODE DRY RUN PAR DÉFAUT</strong> - Les stratégies simulent les trades sans exécution réelle.
    Activez le mode "Live Trading" uniquement après avoir vérifié votre configuration.
</div>
""", unsafe_allow_html=True)

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

# ========== CHECK TRADING ENGINE ==========
if not TRADING_AVAILABLE:
    st.error(f"⚠️ Trading Engine non disponible: {TRADING_ERROR}")
    st.info("Installez les dépendances: `pip install httpx web3 eth-account`")

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
                'LIMIT': ('🎯', 'type-limit'),
                'STOP_LOSS': ('🛑', 'type-stoploss'),
            }
            icon, badge_class = type_icons.get(strategy.strategy_type.upper(), ('🤖', 'type-dca'))
            
            # Card CSS class
            card_class = "strategy-card strategy-card-active" if strategy.is_active else "strategy-card"
            
            with st.container():
                st.markdown(f'<div class="{card_class}">', unsafe_allow_html=True)
                
                col_s1, col_s2, col_s3, col_s4 = st.columns([3, 2, 2, 1])
                
                with col_s1:
                    status = "🟢" if strategy.is_active else "⚫"
                    dry_run = strategy.config.get('dry_run', True)
                    dry_badge = '<span class="dry-run-badge">DRY RUN</span>' if dry_run else ''
                    st.markdown(f"### {status} {strategy.name} {dry_badge}", unsafe_allow_html=True)
                    st.markdown(f'<span class="{badge_class}" style="padding: 4px 10px; border-radius: 15px;">{icon} {strategy.strategy_type.upper()}</span>', unsafe_allow_html=True)
                    st.caption(f"👛 {wallet_name} ({wallet_network})")
                
                with col_s2:
                    cfg = strategy.config
                    if strategy.strategy_type.upper() == 'DCA':
                        amount = cfg.get('amount_per_buy', cfg.get('amount', 0))
                        freq = cfg.get('frequency_hours', 24)
                        token_out = cfg.get('token_out', cfg.get('token', 'ETH'))
                        token_in = cfg.get('token_in', 'USDC')
                        st.markdown(f"**💵 ${amount}** every {freq}h")
                        st.caption(f"{token_in} → {token_out}")
                        
                        # Show stats
                        exec_count = cfg.get('executions_count', 0)
                        total_spent = cfg.get('total_spent', 0)
                        if exec_count > 0:
                            st.caption(f"📈 {exec_count} buys | ${total_spent} spent")
                    
                    elif strategy.strategy_type.upper() == 'LIMIT':
                        target = cfg.get('target_price', 0)
                        side = cfg.get('side', 'buy').upper()
                        amount = cfg.get('amount', 0)
                        st.markdown(f"**🎯 {side} @ ${target}**")
                        st.caption(f"Amount: ${amount}")
                    
                    elif strategy.strategy_type.upper() == 'STOP_LOSS':
                        trigger = cfg.get('trigger_percent', 10)
                        ref_price = cfg.get('reference_price', 0)
                        trailing = "📈 Trailing" if cfg.get('trailing', False) else "📍 Fixed"
                        st.markdown(f"**🛑 -{trigger}%**")
                        st.caption(f"{trailing} | Ref: ${ref_price}")
                
                with col_s3:
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
                    
                    # Next run for DCA
                    if strategy.strategy_type.upper() == 'DCA' and strategy.is_active:
                        freq = strategy.config.get('frequency_hours', 24)
                        if strategy.last_run:
                            next_run = strategy.last_run + timedelta(hours=freq)
                            if next_run > datetime.now():
                                delta = next_run - datetime.now()
                                hours_left = delta.seconds // 3600
                                st.caption(f"⏳ Prochain: {hours_left}h")
                
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
            ["DCA", "LIMIT", "STOP_LOSS"],
            format_func=lambda x: {
                "DCA": "📊 DCA (Dollar Cost Averaging)",
                "LIMIT": "🎯 Limit Order",
                "STOP_LOSS": "🛑 Stop Loss"
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
        
        # Get selected wallet info
        selected_wallet = next((w for w in wallets if w.id == selected_wallet_id), None)
        network = selected_wallet.network if selected_wallet else "ethereum"
        
        # Get tokens for network
        if TRADING_AVAILABLE:
            tokens = get_tokens_for_network(network)
            token_symbols = [t['symbol'] for t in tokens]
        else:
            token_symbols = ["ETH", "USDC", "USDT", "DAI"]
        
        st.markdown("---")
        st.markdown("**⚙️ Configuration**")
        
        config_data = {}
        
        # ========== DCA CONFIG ==========
        if strategy_type == "DCA":
            st.markdown("*Achat régulier d'un token à intervalles fixes*")
            
            col_tokens = st.columns(2)
            with col_tokens[0]:
                config_data['token_in'] = st.selectbox(
                    "Token source (paiement)",
                    ["USDC", "USDT", "DAI"] + ([t for t in token_symbols if t not in ["USDC", "USDT", "DAI"]]),
                    key="dca_token_in"
                )
            with col_tokens[1]:
                config_data['token_out'] = st.selectbox(
                    "Token à acheter",
                    [t for t in token_symbols if t != config_data['token_in']],
                    key="dca_token_out"
                )
            
            config_data['amount_per_buy'] = st.number_input(
                f"Montant par achat ({config_data['token_in']})",
                min_value=10.0,
                max_value=10000.0,
                value=100.0,
                step=10.0
            )
            
            frequency_options = {
                1: "⏰ Toutes les heures",
                4: "🕓 Toutes les 4 heures",
                12: "🌓 2x par jour",
                24: "📅 Quotidien",
                168: "📆 Hebdomadaire",
                720: "🗓️ Mensuel"
            }
            config_data['frequency_hours'] = st.selectbox(
                "Fréquence",
                options=list(frequency_options.keys()),
                format_func=lambda x: frequency_options[x],
                index=3  # Daily by default
            )
            
            # Optional limits
            with st.expander("🔧 Limites optionnelles"):
                total_budget = st.number_input(
                    "Budget total max ($)",
                    min_value=0.0,
                    max_value=100000.0,
                    value=0.0,
                    help="0 = illimité"
                )
                config_data['total_budget'] = total_budget if total_budget > 0 else None
                
                max_exec = st.number_input(
                    "Nombre max d'achats",
                    min_value=0,
                    max_value=1000,
                    value=0,
                    help="0 = illimité"
                )
                config_data['max_executions'] = max_exec if max_exec > 0 else None
            
            config_data['max_slippage'] = st.slider(
                "Slippage max (%)",
                min_value=0.5,
                max_value=5.0,
                value=1.0,
                step=0.5
            )
            
            # DCA Projection
            if TRADING_AVAILABLE:
                st.markdown("---")
                st.markdown("**📈 Projection (30 jours)**")
                
                # Get current price for projection
                current_price = 0
                try:
                    quote = sync_get_quote(config_data['token_in'], config_data['token_out'], 1.0, network)
                    if quote and quote.get('success'):
                        current_price = quote['price']
                except:
                    pass
                
                if current_price > 0:
                    projection = calculate_dca_projection(
                        amount_per_buy=config_data['amount_per_buy'],
                        frequency_hours=config_data['frequency_hours'],
                        duration_days=30,
                        estimated_price=current_price
                    )
                    
                    col_proj1, col_proj2 = st.columns(2)
                    with col_proj1:
                        st.metric("Achats prévus", projection['num_buys'])
                        st.metric("Total investi", f"${projection['total_invested']:.0f}")
                    with col_proj2:
                        st.metric(f"{config_data['token_out']} acquis", f"{projection['tokens_acquired']:.4f}")
                        st.metric("Prix actuel", f"${current_price:.2f}")
        
        # ========== LIMIT ORDER CONFIG ==========
        elif strategy_type == "LIMIT":
            st.markdown("*Exécute un ordre quand le prix atteint une cible*")
            
            config_data['side'] = st.selectbox(
                "Action",
                ["buy", "sell"],
                format_func=lambda x: "🟢 Acheter quand prix ≤ cible" if x == "buy" else "🔴 Vendre quand prix ≥ cible"
            )
            
            col_tokens = st.columns(2)
            if config_data['side'] == 'buy':
                with col_tokens[0]:
                    config_data['token_in'] = st.selectbox(
                        "Payer avec",
                        ["USDC", "USDT", "DAI"],
                        key="limit_token_in"
                    )
                with col_tokens[1]:
                    config_data['token_out'] = st.selectbox(
                        "Acheter",
                        [t for t in token_symbols if t not in ["USDC", "USDT", "DAI"]],
                        key="limit_token_out"
                    )
            else:
                with col_tokens[0]:
                    config_data['token_in'] = st.selectbox(
                        "Vendre",
                        [t for t in token_symbols if t not in ["USDC", "USDT", "DAI"]],
                        key="limit_sell_token"
                    )
                with col_tokens[1]:
                    config_data['token_out'] = st.selectbox(
                        "Recevoir",
                        ["USDC", "USDT", "DAI"],
                        key="limit_receive_token"
                    )
            
            # Current price
            current_price = 0
            if TRADING_AVAILABLE:
                try:
                    quote = sync_get_quote(config_data['token_out'], config_data['token_in'], 1.0, network)
                    if quote and quote.get('success'):
                        current_price = quote['price']
                        st.info(f"💹 Prix actuel: 1 {config_data['token_out']} = ${current_price:.2f}")
                except:
                    pass
            
            config_data['target_price'] = st.number_input(
                f"Prix cible ($ par {config_data['token_out']})",
                min_value=0.0,
                value=current_price * 0.9 if config_data['side'] == 'buy' else current_price * 1.1,
                step=10.0
            )
            
            config_data['amount'] = st.number_input(
                f"Montant ({config_data['token_in']})",
                min_value=10.0,
                max_value=100000.0,
                value=500.0
            )
            
            config_data['max_slippage'] = st.slider(
                "Slippage max (%)",
                min_value=0.5,
                max_value=5.0,
                value=1.0,
                step=0.5
            )
        
        # ========== STOP LOSS CONFIG ==========
        elif strategy_type == "STOP_LOSS":
            st.markdown("*Vend automatiquement si le prix baisse trop*")
            
            col_tokens = st.columns(2)
            with col_tokens[0]:
                config_data['token_in'] = st.selectbox(
                    "Token à protéger",
                    [t for t in token_symbols if t not in ["USDC", "USDT", "DAI"]],
                    key="sl_token"
                )
            with col_tokens[1]:
                config_data['token_out'] = st.selectbox(
                    "Vendre vers",
                    ["USDC", "USDT", "DAI"],
                    key="sl_stable"
                )
            
            # Get current price
            current_price = 0
            if TRADING_AVAILABLE:
                try:
                    quote = sync_get_quote(config_data['token_in'], config_data['token_out'], 1.0, network)
                    if quote and quote.get('success'):
                        current_price = quote['price']
                        st.info(f"💹 Prix actuel: 1 {config_data['token_in']} = ${current_price:.2f}")
                except:
                    pass
            
            config_data['reference_price'] = st.number_input(
                "Prix de référence ($)",
                min_value=0.0,
                value=current_price if current_price > 0 else 3000.0,
                help="Le prix à partir duquel calculer la baisse"
            )
            
            config_data['trigger_percent'] = st.slider(
                "Déclencheur (% de baisse)",
                min_value=1.0,
                max_value=50.0,
                value=10.0,
                step=1.0,
                help="Vend si le prix baisse de ce pourcentage"
            )
            
            # Calculate stop price
            if config_data['reference_price'] > 0:
                stop_price = config_data['reference_price'] * (1 - config_data['trigger_percent'] / 100)
                st.caption(f"🛑 Prix de déclenchement: ${stop_price:.2f}")
            
            config_data['amount'] = st.number_input(
                f"Quantité à vendre ({config_data['token_in']})",
                min_value=0.0,
                value=1.0,
                step=0.1
            )
            
            config_data['trailing'] = st.checkbox(
                "📈 Trailing Stop Loss",
                value=False,
                help="Ajuste automatiquement le stop loss à la hausse quand le prix monte"
            )
            
            config_data['max_slippage'] = st.slider(
                "Slippage max (%)",
                min_value=0.5,
                max_value=5.0,
                value=2.0,  # Higher for stop loss
                step=0.5
            )
        
        st.markdown("---")
        
        # Dry run toggle (default ON)
        config_data['dry_run'] = st.checkbox(
            "🔒 Mode Dry Run (simulation)",
            value=True,
            help="Active par défaut. Désactivez uniquement pour exécuter de vrais trades."
        )
        
        if not config_data['dry_run']:
            st.warning("⚠️ ATTENTION: Le mode Live Trading exécutera de vraies transactions!")
        
        # Bouton de création
        if st.button("🚀 Créer la Stratégie", type="primary", use_container_width=True):
            try:
                # Generate unique ID
                strategy_id = f"{strategy_type.lower()}-{uuid.uuid4().hex[:8]}"
                config_data['id'] = strategy_id
                config_data['name'] = strategy_name
                config_data['wallet_id'] = selected_wallet_id
                config_data['network'] = network
                
                # Save to database
                db_id = db.add_strategy(
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

# ========== QUICK QUOTE TEST ==========
if TRADING_AVAILABLE:
    with st.expander("🧪 Tester une Quote (Prix actuel)"):
        col_q1, col_q2, col_q3, col_q4 = st.columns(4)
        
        with col_q1:
            test_network = st.selectbox(
                "Network",
                list(NETWORKS.keys()),
                format_func=lambda x: f"{NETWORKS[x]['icon']} {NETWORKS[x]['name']}"
            )
        
        test_tokens = get_tokens_for_network(test_network)
        test_symbols = [t['symbol'] for t in test_tokens]
        
        with col_q2:
            test_from = st.selectbox("De", test_symbols, index=0)
        
        with col_q3:
            test_to = st.selectbox("Vers", [t for t in test_symbols if t != test_from], index=0)
        
        with col_q4:
            test_amount = st.number_input("Montant", min_value=0.001, value=1.0, step=0.1)
        
        if st.button("📊 Obtenir Quote", key="test_quote"):
            with st.spinner("Récupération du prix..."):
                quote = sync_get_quote(test_from, test_to, test_amount, test_network)
                
                if quote and quote.get('success'):
                    col_r1, col_r2, col_r3 = st.columns(3)
                    with col_r1:
                        st.metric("Vous payez", f"{quote['src_amount']} {test_from}")
                    with col_r2:
                        st.metric("Vous recevez", f"{quote['dst_amount']:.6f} {test_to}")
                    with col_r3:
                        st.metric("Prix", f"1 {test_from} = {quote['price']:.6f} {test_to}")
                    
                    st.caption(f"Gas estimé: {quote['gas_estimate']} | Quote: {quote['quoted_at']}")
                else:
                    st.error(f"Erreur: {quote.get('error', 'Unknown error')}")

st.markdown("---")

# ========== HISTORIQUE D'EXÉCUTION ==========
st.subheader("📜 Historique d'Exécution")

if executions:
    for exec_record in executions[:10]:
        strategy = next((s for s in strategies if s.id == exec_record.strategy_id), None)
        strategy_name = strategy.name if strategy else f"Stratégie #{exec_record.strategy_id}"
        
        status_icon = "✅" if exec_record.status == "success" else "❌"
        is_dry = exec_record.result.get('is_dry_run', True)
        dry_badge = "🔒" if is_dry else "💰"
        
        with st.container():
            cols = st.columns([1, 3, 2, 2, 2])
            
            with cols[0]:
                st.write(f"{status_icon} {dry_badge}")
            
            with cols[1]:
                st.markdown(f"**{strategy_name}**")
            
            with cols[2]:
                st.caption(exec_record.executed_at.strftime("%d/%m %H:%M"))
            
            with cols[3]:
                if exec_record.tx_hash:
                    st.markdown(f"`{exec_record.tx_hash[:10]}...`")
                elif is_dry:
                    st.caption("Simulation")
                else:
                    st.caption("-")
            
            with cols[4]:
                result = exec_record.result
                if 'amount_in' in result:
                    st.caption(f"${result['amount_in']}")
                elif exec_record.error:
                    st.caption(f"⚠️ {exec_record.error[:20]}...")
else:
    st.info("""
    📭 **Pas encore d'exécutions**
    
    Les résultats apparaîtront ici une fois que vos stratégies seront activées.
    
    Pour commencer :
    1. Créez une stratégie ci-dessus
    2. Activez-la avec le toggle
    3. Le système vérifiera les conditions périodiquement
    """)

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
