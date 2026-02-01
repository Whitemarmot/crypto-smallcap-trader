"""
Crypto SmallCap Trader - Home / Landing Page
Frontend Streamlit pour le monitoring et contrôle du bot de trading
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
sys.path.insert(0, os.path.dirname(__file__))

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
    .metric-card {
        background: linear-gradient(135deg, #1e1e2e 0%, #2d2d44 100%);
        border-radius: 10px;
        padding: 1rem;
        border: 1px solid #404060;
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

# Sidebar
with st.sidebar:
    st.image("https://img.icons8.com/fluency/96/rocket.png", width=80)
    st.title("SmallCap Trader")
    st.markdown("---")
    
    # Status du bot
    bot_status = st.toggle("🤖 Bot Trading", value=True)
    if bot_status:
        st.success("✅ Bot actif")
    else:
        st.error("⛔ Bot inactif")
    
    st.markdown("---")
    
    # Paramètres rapides
    st.subheader("⚙️ Paramètres")
    risk_level = st.select_slider(
        "Niveau de risque",
        options=["Très faible", "Faible", "Modéré", "Élevé", "Agressif"],
        value="Modéré"
    )
    
    max_position = st.slider("Taille max position ($)", 100, 5000, 500, 100)
    
    st.markdown("---")
    st.caption("v0.1.0 | Dernière MAJ: " + datetime.now().strftime("%H:%M:%S"))

# Header principal
st.markdown('<p class="main-header">🚀 Crypto SmallCap Trader Dashboard</p>', unsafe_allow_html=True)

# Métriques principales (row 1)
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric(
        label="💰 Valeur Portfolio",
        value="$12,458.32",
        delta="+$847.21 (7.3%)",
        delta_color="normal"
    )

with col2:
    st.metric(
        label="📈 P&L Aujourd'hui",
        value="+$234.56",
        delta="+1.92%",
        delta_color="normal"
    )

with col3:
    st.metric(
        label="🔄 Trades Actifs",
        value="3",
        delta="2 en profit",
        delta_color="normal"
    )

with col4:
    st.metric(
        label="🎯 Win Rate (7j)",
        value="68.5%",
        delta="+2.1%",
        delta_color="normal"
    )

st.markdown("---")

# Graphiques (row 2)
col_left, col_right = st.columns([2, 1])

with col_left:
    st.subheader("📊 Performance du Portfolio")
    
    # Génération de données de démo
    dates = pd.date_range(start=datetime.now() - timedelta(days=30), end=datetime.now(), freq='D')
    base_value = 10000
    values = [base_value]
    for i in range(1, len(dates)):
        change = random.uniform(-0.03, 0.04)
        values.append(values[-1] * (1 + change))
    
    df_portfolio = pd.DataFrame({
        'Date': dates,
        'Valeur ($)': values
    })
    
    fig = px.area(
        df_portfolio, 
        x='Date', 
        y='Valeur ($)',
        color_discrete_sequence=['#667eea']
    )
    fig.update_layout(
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        xaxis=dict(showgrid=False),
        yaxis=dict(showgrid=True, gridcolor='rgba(255,255,255,0.1)'),
        height=350
    )
    st.plotly_chart(fig, use_container_width=True)

with col_right:
    st.subheader("🪙 Allocation")
    
    allocation_data = {
        'Token': ['SOL', 'BONK', 'WIF', 'PYTH', 'JUP', 'USDC'],
        'Allocation': [35, 20, 15, 12, 8, 10]
    }
    df_alloc = pd.DataFrame(allocation_data)
    
    fig_pie = px.pie(
        df_alloc,
        values='Allocation',
        names='Token',
        color_discrete_sequence=px.colors.sequential.Plasma
    )
    fig_pie.update_layout(
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        height=350,
        showlegend=True
    )
    st.plotly_chart(fig_pie, use_container_width=True)

# Positions actives et signaux récents (row 3)
col_positions, col_signals = st.columns(2)

with col_positions:
    st.subheader("📍 Positions Actives")
    
    positions_data = {
        'Token': ['BONK', 'WIF', 'PYTH'],
        'Entry': ['$0.0000234', '$2.45', '$0.42'],
        'Actuel': ['$0.0000256', '$2.68', '$0.39'],
        'P&L': ['+9.4%', '+9.3%', '-7.1%'],
        'Taille': ['$450', '$380', '$290']
    }
    df_positions = pd.DataFrame(positions_data)
    
    st.dataframe(
        df_positions,
        column_config={
            "Token": st.column_config.TextColumn("🪙 Token"),
            "Entry": st.column_config.TextColumn("📥 Entry"),
            "Actuel": st.column_config.TextColumn("💵 Prix"),
            "P&L": st.column_config.TextColumn("📊 P&L"),
            "Taille": st.column_config.TextColumn("💰 Taille"),
        },
        hide_index=True,
        use_container_width=True
    )

with col_signals:
    st.subheader("📡 Signaux Récents")
    
    signals = [
        {"time": "14:32", "type": "🟢 BUY", "token": "JUP", "source": "Twitter KOL", "strength": "Strong"},
        {"time": "13:15", "type": "🟡 HOLD", "token": "BONK", "source": "Sentiment", "strength": "Medium"},
        {"time": "12:48", "type": "🔴 SELL", "token": "MYRO", "source": "AI Model", "strength": "Strong"},
        {"time": "11:22", "type": "🟢 BUY", "token": "WEN", "source": "Volume Spike", "strength": "Medium"},
    ]
    
    for signal in signals:
        with st.container():
            cols = st.columns([1, 1, 2, 2, 1])
            cols[0].write(signal["time"])
            cols[1].write(signal["type"])
            cols[2].write(f"**{signal['token']}**")
            cols[3].write(signal["source"])
            cols[4].write(f"_{signal['strength']}_")

st.markdown("---")

# Footer avec actions rapides
st.subheader("⚡ Actions Rapides")
action_cols = st.columns(5)

with action_cols[0]:
    if st.button("🔄 Refresh Data", use_container_width=True):
        st.rerun()

with action_cols[1]:
    if st.button("📊 Export Report", use_container_width=True):
        st.toast("Report exporté!", icon="✅")

with action_cols[2]:
    if st.button("🛑 Pause Trading", use_container_width=True):
        st.warning("Trading pausé")

with action_cols[3]:
    if st.button("💰 Withdraw", use_container_width=True):
        st.info("Ouvrir modal de retrait...")

with action_cols[4]:
    if st.button("⚙️ Settings", use_container_width=True):
        st.switch_page("pages/5_settings.py")

# Footer with navigation
st.markdown("---")
st.markdown("### 📍 Navigation Rapide")
nav_cols = st.columns(6)

with nav_cols[0]:
    if st.button("🏠 Dashboard", use_container_width=True, type="primary"):
        st.switch_page("pages/0_dashboard.py")
        
with nav_cols[1]:
    if st.button("👛 Wallets", use_container_width=True):
        st.switch_page("pages/1_wallet.py")

with nav_cols[2]:
    if st.button("📈 Trades", use_container_width=True):
        st.switch_page("pages/2_trades.py")

with nav_cols[3]:
    if st.button("📡 Signaux", use_container_width=True):
        st.switch_page("pages/3_signals.py")

with nav_cols[4]:
    if st.button("🎯 Stratégies", use_container_width=True):
        st.switch_page("pages/4_strategies.py")

with nav_cols[5]:
    if st.button("⚙️ Paramètres", use_container_width=True):
        st.switch_page("pages/5_settings.py")
