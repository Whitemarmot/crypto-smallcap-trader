"""
Crypto SmallCap Trader - Historique des Trades
Suivi et analyse des trades passés
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import random

st.set_page_config(
    page_title="📈 Trades | SmallCap Trader",
    page_icon="📈",
    layout="wide"
)

st.title("📈 Historique des Trades")
st.markdown("Analysez vos performances de trading")

# Filtres
st.markdown("---")
filter_cols = st.columns(4)

with filter_cols[0]:
    date_range = st.date_input(
        "📅 Période",
        value=(datetime.now() - timedelta(days=30), datetime.now()),
        key="date_filter"
    )
    
with filter_cols[1]:
    token_filter = st.multiselect(
        "🪙 Tokens",
        ["Tous", "SOL", "BONK", "WIF", "PYTH", "JUP", "MYRO", "WEN"],
        default=["Tous"]
    )

with filter_cols[2]:
    trade_type = st.selectbox(
        "📊 Type",
        ["Tous", "Buy", "Sell", "Win", "Loss"]
    )
    
with filter_cols[3]:
    sort_by = st.selectbox(
        "🔃 Trier par",
        ["Date (récent)", "Date (ancien)", "P&L (haut)", "P&L (bas)", "Taille"]
    )

# Stats rapides
st.markdown("---")
stat_cols = st.columns(5)

with stat_cols[0]:
    st.metric("📊 Total Trades", "156", "+12 ce mois")
    
with stat_cols[1]:
    st.metric("🎯 Win Rate", "68.5%", "+2.3%")
    
with stat_cols[2]:
    st.metric("💰 P&L Total", "+$2,847.32", "+18.7%")
    
with stat_cols[3]:
    st.metric("📈 Meilleur Trade", "+$456.78", "BONK")
    
with stat_cols[4]:
    st.metric("📉 Pire Trade", "-$123.45", "MYRO")

# Graphique de performance cumulative
st.markdown("---")
st.subheader("📊 Performance Cumulative")

# Génération de données de démo
dates = pd.date_range(start=datetime.now() - timedelta(days=90), end=datetime.now(), freq='D')
cumulative_pnl = [0]
for i in range(1, len(dates)):
    daily_change = random.uniform(-50, 80)
    cumulative_pnl.append(cumulative_pnl[-1] + daily_change)

df_cumulative = pd.DataFrame({
    'Date': dates,
    'P&L Cumulatif ($)': cumulative_pnl
})

fig_cumulative = go.Figure()
fig_cumulative.add_trace(go.Scatter(
    x=df_cumulative['Date'],
    y=df_cumulative['P&L Cumulatif ($)'],
    fill='tonexty',
    fillcolor='rgba(102, 126, 234, 0.3)',
    line=dict(color='#667eea', width=2),
    name='P&L Cumulatif'
))

fig_cumulative.add_hline(y=0, line_dash="dash", line_color="gray")
fig_cumulative.update_layout(
    plot_bgcolor='rgba(0,0,0,0)',
    paper_bgcolor='rgba(0,0,0,0)',
    xaxis=dict(showgrid=False),
    yaxis=dict(showgrid=True, gridcolor='rgba(255,255,255,0.1)', title="P&L ($)"),
    height=400
)
st.plotly_chart(fig_cumulative, use_container_width=True)

# Stats par token
st.markdown("---")
col_stats1, col_stats2 = st.columns(2)

with col_stats1:
    st.subheader("🪙 Performance par Token")
    
    token_perf = {
        'Token': ['BONK', 'WIF', 'SOL', 'PYTH', 'JUP', 'MYRO'],
        'Trades': [45, 32, 28, 22, 18, 11],
        'Win Rate': [72, 68, 75, 64, 61, 45],
        'P&L ($)': [892.50, 456.30, 678.20, 234.10, 156.80, -89.40]
    }
    df_token_perf = pd.DataFrame(token_perf)
    
    fig_token = px.bar(
        df_token_perf,
        x='Token',
        y='P&L ($)',
        color='P&L ($)',
        color_continuous_scale=['#ff4444', '#ffaa00', '#00ff88']
    )
    fig_token.update_layout(
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        height=350
    )
    st.plotly_chart(fig_token, use_container_width=True)

with col_stats2:
    st.subheader("📈 Distribution des Trades")
    
    trade_dist = {
        'Résultat': ['Gagnant', 'Perdant', 'Breakeven'],
        'Count': [107, 42, 7]
    }
    df_dist = pd.DataFrame(trade_dist)
    
    fig_dist = px.pie(
        df_dist,
        values='Count',
        names='Résultat',
        color='Résultat',
        color_discrete_map={'Gagnant': '#00ff88', 'Perdant': '#ff4444', 'Breakeven': '#888888'}
    )
    fig_dist.update_layout(
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        height=350
    )
    st.plotly_chart(fig_dist, use_container_width=True)

# Tableau des trades
st.markdown("---")
st.subheader("📋 Historique Détaillé")

# Générer des trades de démo
trades_data = []
tokens = ['BONK', 'WIF', 'PYTH', 'JUP', 'MYRO', 'WEN', 'SOL']
for i in range(20):
    trade_date = datetime.now() - timedelta(days=random.randint(0, 30), hours=random.randint(0, 23))
    token = random.choice(tokens)
    entry = round(random.uniform(0.1, 5), 4)
    exit_price = entry * (1 + random.uniform(-0.15, 0.25))
    size = random.randint(100, 1000)
    pnl_pct = ((exit_price - entry) / entry) * 100
    pnl_usd = size * (pnl_pct / 100)
    
    trades_data.append({
        'Date': trade_date.strftime('%Y-%m-%d %H:%M'),
        'Token': token,
        'Type': '🟢 Long' if random.random() > 0.3 else '🔴 Short',
        'Entry': f"${entry:.4f}",
        'Exit': f"${exit_price:.4f}",
        'Taille ($)': f"${size}",
        'P&L (%)': f"{pnl_pct:+.2f}%",
        'P&L ($)': f"${pnl_usd:+.2f}",
        'Signal': random.choice(['AI Model', 'Twitter KOL', 'Volume', 'Sentiment']),
        'Durée': f"{random.randint(1, 48)}h"
    })

df_trades = pd.DataFrame(trades_data)

# Colorer le P&L
st.dataframe(
    df_trades,
    column_config={
        "Date": st.column_config.TextColumn("📅 Date", width="medium"),
        "Token": st.column_config.TextColumn("🪙 Token", width="small"),
        "Type": st.column_config.TextColumn("📊 Type", width="small"),
        "Entry": st.column_config.TextColumn("📥 Entry"),
        "Exit": st.column_config.TextColumn("📤 Exit"),
        "Taille ($)": st.column_config.TextColumn("💰 Taille"),
        "P&L (%)": st.column_config.TextColumn("📈 P&L %"),
        "P&L ($)": st.column_config.TextColumn("💵 P&L $"),
        "Signal": st.column_config.TextColumn("📡 Signal"),
        "Durée": st.column_config.TextColumn("⏱️ Durée", width="small"),
    },
    hide_index=True,
    use_container_width=True
)

# Export
st.markdown("---")
export_cols = st.columns(4)

with export_cols[0]:
    if st.button("📥 Export CSV", use_container_width=True):
        st.toast("Export CSV généré!", icon="✅")
        
with export_cols[1]:
    if st.button("📊 Export PDF Report", use_container_width=True):
        st.toast("Rapport PDF généré!", icon="✅")
        
with export_cols[2]:
    if st.button("📈 Analyse Avancée", use_container_width=True):
        st.info("Ouverture de l'analyse avancée...")
        
with export_cols[3]:
    if st.button("🔄 Rafraîchir", use_container_width=True):
        st.rerun()
