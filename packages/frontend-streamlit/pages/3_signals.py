"""
Crypto SmallCap Trader - Signaux Sociaux
Analyse des signaux Twitter, Telegram et autres sources
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import random

st.set_page_config(
    page_title="📡 Signals | SmallCap Trader",
    page_icon="📡",
    layout="wide"
)

st.title("📡 Signaux Sociaux")
st.markdown("Analyse en temps réel des signaux crypto sur les réseaux sociaux")

# Status des sources
st.markdown("---")
st.subheader("🔌 Sources Connectées")

source_cols = st.columns(4)

with source_cols[0]:
    st.metric("🐦 Twitter/X", "Active", "245 KOLs suivis")
    st.progress(100, text="Connecté")
    
with source_cols[1]:
    st.metric("📱 Telegram", "Active", "18 groupes")
    st.progress(100, text="Connecté")
    
with source_cols[2]:
    st.metric("💬 Discord", "Active", "12 serveurs")
    st.progress(100, text="Connecté")
    
with source_cols[3]:
    st.metric("📰 News", "Active", "5 sources")
    st.progress(100, text="Connecté")

# Filtres
st.markdown("---")
filter_cols = st.columns(5)

with filter_cols[0]:
    source_filter = st.multiselect(
        "📡 Source",
        ["Twitter", "Telegram", "Discord", "News"],
        default=["Twitter", "Telegram"]
    )
    
with filter_cols[1]:
    signal_type = st.selectbox(
        "🎯 Type de signal",
        ["Tous", "Buy", "Sell", "Alert", "News"]
    )
    
with filter_cols[2]:
    strength_filter = st.select_slider(
        "💪 Force min",
        options=["Faible", "Moyen", "Fort", "Très fort"],
        value="Moyen"
    )
    
with filter_cols[3]:
    time_filter = st.selectbox(
        "⏰ Période",
        ["1h", "6h", "24h", "7j", "30j"]
    )

with filter_cols[4]:
    auto_refresh = st.toggle("🔄 Auto-refresh", value=True)

# Signaux en temps réel
st.markdown("---")
st.subheader("🚨 Signaux Live")

# Générer des signaux de démo
signals = [
    {
        "time": "14:45:32",
        "source": "🐦 Twitter",
        "author": "@CryptoKOL_Alpha",
        "token": "BONK",
        "type": "🟢 BUY",
        "strength": 85,
        "message": "Major accumulation pattern forming on BONK. Smart money loading up. NFA 🚀",
        "followers": "245K",
        "engagement": "2.3K likes"
    },
    {
        "time": "14:32:18",
        "source": "📱 Telegram",
        "author": "Solana Whales",
        "token": "JUP",
        "type": "🟢 BUY",
        "strength": 78,
        "message": "Whale just bought 500K JUP. Transaction hash: 5xY7...",
        "followers": "85K",
        "engagement": "520 views"
    },
    {
        "time": "14:15:44",
        "source": "🐦 Twitter",
        "author": "@DeFi_Degen",
        "token": "WIF",
        "type": "🟡 HOLD",
        "strength": 62,
        "message": "WIF consolidating nicely. Waiting for breakout confirmation before adding.",
        "followers": "180K",
        "engagement": "1.1K likes"
    },
    {
        "time": "13:58:21",
        "source": "📰 News",
        "author": "CoinDesk",
        "token": "SOL",
        "type": "📰 NEWS",
        "strength": 70,
        "message": "Solana DeFi TVL reaches new ATH at $5.2B",
        "followers": "2.1M",
        "engagement": "Featured"
    },
    {
        "time": "13:42:55",
        "source": "💬 Discord",
        "author": "Memecoin Hunters",
        "token": "MYRO",
        "type": "🔴 SELL",
        "strength": 72,
        "message": "Dev wallet moved tokens. Taking profits here. -30% from entry still green.",
        "followers": "45K",
        "engagement": "89 reactions"
    },
    {
        "time": "13:28:10",
        "source": "🐦 Twitter",
        "author": "@SolanaLegend",
        "token": "PYTH",
        "type": "🟢 BUY",
        "strength": 88,
        "message": "PYTH about to announce major partnership. Sources confirm. This is huge. 🔥",
        "followers": "520K",
        "engagement": "5.8K likes"
    },
]

for signal in signals:
    with st.container():
        col1, col2, col3 = st.columns([1, 3, 1])
        
        with col1:
            st.write(f"**{signal['time']}**")
            st.write(signal['source'])
            st.caption(signal['author'])
            
        with col2:
            signal_header = f"{signal['type']} **{signal['token']}**"
            st.markdown(signal_header)
            st.write(signal['message'])
            st.caption(f"👥 {signal['followers']} | 💬 {signal['engagement']}")
            
        with col3:
            st.metric("Force", f"{signal['strength']}%")
            strength_color = "green" if signal['strength'] > 70 else "orange" if signal['strength'] > 50 else "red"
            st.progress(signal['strength'])
            
        st.markdown("---")

# Analyse de sentiment
st.subheader("📊 Analyse de Sentiment")

col_sent1, col_sent2 = st.columns(2)

with col_sent1:
    # Sentiment par token
    sentiment_data = {
        'Token': ['BONK', 'WIF', 'JUP', 'PYTH', 'SOL', 'MYRO'],
        'Bullish': [78, 62, 71, 85, 80, 35],
        'Bearish': [12, 28, 18, 8, 12, 45],
        'Neutral': [10, 10, 11, 7, 8, 20]
    }
    df_sentiment = pd.DataFrame(sentiment_data)
    
    fig_sent = go.Figure()
    fig_sent.add_trace(go.Bar(name='Bullish', x=df_sentiment['Token'], y=df_sentiment['Bullish'], marker_color='#00ff88'))
    fig_sent.add_trace(go.Bar(name='Bearish', x=df_sentiment['Token'], y=df_sentiment['Bearish'], marker_color='#ff4444'))
    fig_sent.add_trace(go.Bar(name='Neutral', x=df_sentiment['Token'], y=df_sentiment['Neutral'], marker_color='#888888'))
    
    fig_sent.update_layout(
        barmode='stack',
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        title="Sentiment par Token",
        yaxis_title="% des mentions",
        height=400
    )
    st.plotly_chart(fig_sent, use_container_width=True)

with col_sent2:
    # Volume de mentions
    hours = list(range(24))
    mention_volume = [random.randint(50, 200) for _ in hours]
    
    fig_volume = go.Figure()
    fig_volume.add_trace(go.Scatter(
        x=hours,
        y=mention_volume,
        fill='tozeroy',
        fillcolor='rgba(102, 126, 234, 0.3)',
        line=dict(color='#667eea', width=2),
        name='Mentions'
    ))
    
    fig_volume.update_layout(
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        title="Volume de Mentions (24h)",
        xaxis_title="Heure",
        yaxis_title="Nombre de mentions",
        height=400
    )
    st.plotly_chart(fig_volume, use_container_width=True)

# Top KOLs
st.markdown("---")
st.subheader("👑 Top KOLs Performance")

kol_data = {
    'KOL': ['@CryptoKOL_Alpha', '@SolanaLegend', '@DeFi_Degen', '@MemeLord', '@WhaleWatcher'],
    'Followers': ['520K', '245K', '180K', '320K', '95K'],
    'Signaux (30j)': [45, 38, 52, 28, 41],
    'Accuracy': [78, 72, 65, 82, 69],
    'Avg P&L': ['+24.5%', '+18.2%', '+12.8%', '+31.2%', '+15.6%'],
    'Score': [92, 85, 71, 88, 74]
}
df_kols = pd.DataFrame(kol_data)

st.dataframe(
    df_kols,
    column_config={
        "KOL": st.column_config.TextColumn("👤 KOL"),
        "Followers": st.column_config.TextColumn("👥 Followers"),
        "Signaux (30j)": st.column_config.NumberColumn("📡 Signaux"),
        "Accuracy": st.column_config.ProgressColumn(
            "🎯 Accuracy",
            format="%d%%",
            min_value=0,
            max_value=100,
        ),
        "Avg P&L": st.column_config.TextColumn("💰 Avg P&L"),
        "Score": st.column_config.ProgressColumn(
            "⭐ Score",
            format="%d",
            min_value=0,
            max_value=100,
        ),
    },
    hide_index=True,
    use_container_width=True
)

# Configuration des alertes
st.markdown("---")
st.subheader("🔔 Configuration des Alertes")

alert_cols = st.columns(3)

with alert_cols[0]:
    st.write("**Tokens à surveiller**")
    watched_tokens = st.multiselect(
        "Ajouter des tokens",
        ["BONK", "WIF", "PYTH", "JUP", "MYRO", "WEN", "POPCAT", "BOME"],
        default=["BONK", "WIF", "PYTH"],
        label_visibility="collapsed"
    )
    
with alert_cols[1]:
    st.write("**Seuil de force**")
    alert_threshold = st.slider(
        "Force minimum pour alerte",
        min_value=50,
        max_value=100,
        value=75,
        label_visibility="collapsed"
    )
    
with alert_cols[2]:
    st.write("**Notifications**")
    notify_telegram = st.checkbox("📱 Telegram", value=True)
    notify_discord = st.checkbox("💬 Discord", value=True)
    notify_email = st.checkbox("📧 Email", value=False)

if st.button("💾 Sauvegarder Configuration", type="primary"):
    st.success("Configuration sauvegardée!")
    st.toast("Alertes mises à jour", icon="✅")
