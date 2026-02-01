"""
Crypto SmallCap Trader - Vue Wallet
Gestion du portefeuille et des tokens
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import random

st.set_page_config(
    page_title="💼 Wallet | SmallCap Trader",
    page_icon="💼",
    layout="wide"
)

st.title("💼 Wallet & Portfolio")
st.markdown("Gérez votre portefeuille Solana et vos positions")

# Wallet Overview
st.markdown("---")
col1, col2, col3 = st.columns(3)

with col1:
    st.metric(
        label="💰 Balance Total",
        value="$12,458.32",
        delta="+$1,234.56 (10.9%)"
    )
    
with col2:
    st.metric(
        label="🔒 Solana (SOL)",
        value="45.32 SOL",
        delta="≈ $4,532.00"
    )
    
with col3:
    st.metric(
        label="💵 USDC",
        value="$1,250.00",
        delta="Stable"
    )

st.markdown("---")

# Wallet Address & Actions
st.subheader("🔑 Wallet Principal")
wallet_col1, wallet_col2 = st.columns([3, 1])

with wallet_col1:
    wallet_address = "7xKX...9nYz"
    st.code(f"Adresse: {wallet_address}", language=None)
    
with wallet_col2:
    if st.button("📋 Copier", use_container_width=True):
        st.toast("Adresse copiée!", icon="✅")

# Token Holdings
st.markdown("---")
st.subheader("🪙 Holdings")

holdings_data = {
    'Token': ['SOL', 'BONK', 'WIF', 'PYTH', 'JUP', 'USDC'],
    'Balance': ['45.32', '12,500,000', '234.5', '890', '125', '1,250'],
    'Prix': ['$100.02', '$0.0000234', '$2.68', '$0.42', '$0.89', '$1.00'],
    'Valeur ($)': ['$4,532.90', '$292.50', '$628.46', '$373.80', '$111.25', '$1,250.00'],
    'Allocation (%)': [35.2, 4.5, 9.7, 5.8, 1.7, 19.4],
    '24h Change': ['+2.4%', '+12.5%', '-3.2%', '+5.1%', '+1.8%', '0%'],
}

df_holdings = pd.DataFrame(holdings_data)

# Style pour les changements positifs/négatifs
def color_change(val):
    if '+' in str(val):
        return 'color: #00ff88'
    elif '-' in str(val):
        return 'color: #ff4444'
    return ''

st.dataframe(
    df_holdings,
    column_config={
        "Token": st.column_config.TextColumn("🪙 Token", width="small"),
        "Balance": st.column_config.TextColumn("📊 Balance"),
        "Prix": st.column_config.TextColumn("💵 Prix"),
        "Valeur ($)": st.column_config.TextColumn("💰 Valeur"),
        "Allocation (%)": st.column_config.ProgressColumn(
            "📈 Allocation",
            format="%.1f%%",
            min_value=0,
            max_value=100,
        ),
        "24h Change": st.column_config.TextColumn("🔄 24h"),
    },
    hide_index=True,
    use_container_width=True
)

# Graphique d'allocation
st.markdown("---")
col_chart1, col_chart2 = st.columns(2)

with col_chart1:
    st.subheader("📊 Allocation du Portfolio")
    fig_alloc = px.pie(
        df_holdings,
        values='Allocation (%)',
        names='Token',
        color_discrete_sequence=px.colors.sequential.Viridis
    )
    fig_alloc.update_layout(
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        height=400
    )
    st.plotly_chart(fig_alloc, use_container_width=True)

with col_chart2:
    st.subheader("📈 Performance par Token (7j)")
    
    performance_data = {
        'Token': ['SOL', 'BONK', 'WIF', 'PYTH', 'JUP'],
        'Performance (%)': [8.5, 45.2, -12.3, 22.1, 5.6]
    }
    df_perf = pd.DataFrame(performance_data)
    
    colors = ['#00ff88' if x > 0 else '#ff4444' for x in df_perf['Performance (%)']]
    
    fig_perf = go.Figure(data=[
        go.Bar(
            x=df_perf['Token'],
            y=df_perf['Performance (%)'],
            marker_color=colors
        )
    ])
    fig_perf.update_layout(
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        yaxis_title="Performance (%)",
        height=400
    )
    st.plotly_chart(fig_perf, use_container_width=True)

# Actions de wallet
st.markdown("---")
st.subheader("⚡ Actions")

action_cols = st.columns(4)

with action_cols[0]:
    with st.expander("📥 Déposer"):
        deposit_amount = st.number_input("Montant SOL", min_value=0.0, value=1.0, step=0.1)
        if st.button("Confirmer Dépôt", type="primary", use_container_width=True):
            st.success(f"Dépôt de {deposit_amount} SOL initié!")

with action_cols[1]:
    with st.expander("📤 Retirer"):
        withdraw_amount = st.number_input("Montant à retirer", min_value=0.0, value=0.5, step=0.1)
        withdraw_address = st.text_input("Adresse destination")
        if st.button("Confirmer Retrait", type="primary", use_container_width=True):
            if withdraw_address:
                st.success(f"Retrait de {withdraw_amount} SOL vers {withdraw_address[:8]}...")
            else:
                st.error("Veuillez entrer une adresse")

with action_cols[2]:
    with st.expander("🔄 Swap"):
        from_token = st.selectbox("De", ["SOL", "USDC", "BONK", "WIF"])
        to_token = st.selectbox("Vers", ["USDC", "SOL", "BONK", "WIF"])
        swap_amount = st.number_input("Montant", min_value=0.0, value=1.0, step=0.1)
        if st.button("Swap", type="primary", use_container_width=True):
            st.success(f"Swap {swap_amount} {from_token} → {to_token}")

with action_cols[3]:
    with st.expander("📊 Rebalance"):
        st.write("Réajuster l'allocation selon la stratégie")
        target_alloc = st.slider("SOL target (%)", 20, 60, 40)
        if st.button("Auto-Rebalance", type="primary", use_container_width=True):
            st.info("Rebalancing en cours...")

# Historique des transactions récentes
st.markdown("---")
st.subheader("📜 Transactions Récentes")

tx_data = {
    'Date': ['2024-01-15 14:32', '2024-01-15 12:15', '2024-01-14 18:45', '2024-01-14 10:22', '2024-01-13 22:10'],
    'Type': ['🟢 Achat', '🔴 Vente', '🔄 Swap', '🟢 Achat', '📤 Retrait'],
    'Token': ['BONK', 'WIF', 'SOL → USDC', 'PYTH', 'SOL'],
    'Montant': ['$250.00', '$180.50', '2 SOL → $198.50', '$150.00', '1.5 SOL'],
    'Status': ['✅ Confirmé', '✅ Confirmé', '✅ Confirmé', '✅ Confirmé', '✅ Confirmé'],
    'TX Hash': ['5xY7...kL9m', '8aB2...nP4q', '3cD5...rT7w', '9eF1...uV2x', '2gH4...yZ6a']
}

df_tx = pd.DataFrame(tx_data)
st.dataframe(df_tx, hide_index=True, use_container_width=True)
