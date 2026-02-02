"""
Crypto SmallCap Trader - Home / Landing Page
Frontend Streamlit pour le monitoring et contrôle du bot de trading
"""

import streamlit as st
from datetime import datetime
import sys
import os

# Add utils to path
sys.path.insert(0, os.path.dirname(__file__))

from utils.database import get_db
from utils.config import SUPPORTED_NETWORKS

# Configuration de la page
st.set_page_config(
    page_title="🚀 SmallCap Trader",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Styles CSS personnalisés
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 1rem;
    }
    .status-active {
        color: #00ff88;
        font-weight: bold;
    }
    .status-inactive {
        color: #ff4444;
        font-weight: bold;
    }
</style>
""", unsafe_allow_html=True)

# Database
db = get_db()

# Sidebar
with st.sidebar:
    st.image("https://img.icons8.com/fluency/96/rocket.png", width=80)
    st.title("SmallCap Trader")
    st.markdown("---")
    
    # Quick links
    st.page_link("pages/1_wallet.py", label="👛 Wallets", icon="👛")
    st.page_link("pages/9_positions.py", label="📊 Positions", icon="📊")
    st.page_link("pages/2_trades.py", label="📈 Trades", icon="📈")
    st.page_link("pages/9_logs_ia.py", label="🤖 Logs IA", icon="🤖")
    
    st.markdown("---")
    st.caption("v0.2.0 | " + datetime.now().strftime("%d/%m/%Y %H:%M"))

# Header principal
st.markdown('<p class="main-header">🚀 Crypto SmallCap Trader</p>', unsafe_allow_html=True)

# Fetch real wallet data
wallets = db.get_wallets()
active_wallet = db.get_active_wallet()

# Try to get real balances
total_value = 0
if active_wallet:
    try:
        from utils.balance import get_all_balances, get_prices
        balances = get_all_balances(active_wallet.address, active_wallet.network)
        if balances:
            symbols = [b.symbol for b in balances]
            prices = get_prices(symbols)
            for b in balances:
                total_value += b.balance * prices.get(b.symbol, 0)
    except Exception:
        pass

# Métriques principales
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric(
        label="💰 Valeur Portfolio",
        value=f"${total_value:,.2f}",
        delta=None
    )

with col2:
    st.metric(
        label="👛 Wallets",
        value=str(len(wallets)),
        delta="actifs" if wallets else None
    )

with col3:
    st.metric(
        label="🔄 Trades Actifs",
        value="0",
        delta="En attente"
    )

with col4:
    st.metric(
        label="🎯 Win Rate",
        value="--",
        delta="Pas encore de trades"
    )

st.markdown("---")

# Status Section
col_left, col_right = st.columns([2, 1])

with col_left:
    st.subheader("📊 Status")
    
    if active_wallet:
        network_icon = SUPPORTED_NETWORKS.get(active_wallet.network, {}).get('icon', '🔗')
        st.success(f"✅ Wallet actif: **{active_wallet.name}** ({network_icon} {active_wallet.network.upper()})")
        st.code(active_wallet.address, language=None)
        
        if total_value > 0:
            st.info(f"💰 Balance totale: **${total_value:,.2f}**")
        else:
            st.warning("⚠️ Wallet vide - Dépose des tokens pour commencer")
    else:
        st.warning("⚠️ Aucun wallet configuré")
        st.caption("Va dans 👛 Wallets pour créer ou importer un wallet")
    
    # Bot status
    st.markdown("---")
    st.subheader("🤖 Trading Bot")
    st.info("⏸️ Le bot de trading n'est pas encore actif. Configure tes stratégies dans l'onglet Stratégies.")

with col_right:
    st.subheader("🚀 Démarrage Rapide")
    
    steps = [
        ("👛 Créer un wallet", len(wallets) > 0),
        ("💰 Déposer des fonds", total_value > 0),
        ("📊 Configurer stratégie", False),
        ("🤖 Lancer le bot", False),
    ]
    
    for step, done in steps:
        if done:
            st.markdown(f"✅ ~~{step}~~")
        else:
            st.markdown(f"⬜ {step}")

st.markdown("---")

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

# Footer
st.markdown("---")
st.caption("SmallCap Trader v0.1.0 - Trading bot basé sur le sentiment social 📱")
