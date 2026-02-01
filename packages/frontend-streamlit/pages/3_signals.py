"""
📡 Signaux Sociaux - Sentiment et Trending
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

st.set_page_config(
    page_title="📡 Signals | SmallCap Trader",
    page_icon="📡",
    layout="wide"
)

st.title("📡 Signaux & Sentiment")
st.caption("Analyse du sentiment de marché et tokens trending")

# Import module
try:
    from utils.social_signals import (
        get_source_status,
        get_fear_greed_index,
        get_fear_greed_history,
        get_trending_tokens,
        get_token_social_stats,
        get_global_market_data,
        get_tokens_by_market_cap
    )
    from utils.config import load_config
    MODULE_AVAILABLE = True
    config = load_config()
except ImportError as e:
    MODULE_AVAILABLE = False
    config = None
    st.error(f"Module non disponible: {e}")

if MODULE_AVAILABLE:
    # ========== SOURCE STATUS ==========
    st.markdown("---")
    st.subheader("🔌 Sources de Données")
    
    status = get_source_status()
    cols = st.columns(4)
    
    for i, (key, source) in enumerate(status.items()):
        with cols[i % 4]:
            icon = "🟢" if source['connected'] else "❌"
            st.markdown(f"**{source['icon']} {source['name']}**")
            st.caption(f"{icon} {source['description']}")
    
    st.markdown("---")
    
    # ========== FEAR & GREED INDEX ==========
    col_fg, col_market = st.columns([1, 1])
    
    with col_fg:
        st.subheader("😱 Fear & Greed Index")
        
        fg = get_fear_greed_index()
        
        if fg:
            # Color based on value
            if fg.value <= 25:
                color = "#ff4444"
                emoji = "😱"
            elif fg.value <= 45:
                color = "#ff8844"
                emoji = "😰"
            elif fg.value <= 55:
                color = "#ffff44"
                emoji = "😐"
            elif fg.value <= 75:
                color = "#88ff44"
                emoji = "😊"
            else:
                color = "#44ff44"
                emoji = "🤑"
            
            # Big number display
            st.markdown(f"""
            <div style="text-align: center; padding: 20px; background: linear-gradient(135deg, {color}22 0%, {color}11 100%); border-radius: 15px; border: 2px solid {color};">
                <div style="font-size: 4rem; font-weight: bold; color: {color};">{fg.value}</div>
                <div style="font-size: 1.5rem;">{emoji} {fg.classification}</div>
            </div>
            """, unsafe_allow_html=True)
            
            st.caption(f"Mis à jour: {fg.timestamp.strftime('%d/%m/%Y')}")
            
            # History chart
            st.markdown("**Historique 30 jours**")
            history = get_fear_greed_history(30)
            
            if history:
                df_history = pd.DataFrame([
                    {'Date': h.timestamp, 'Value': h.value, 'Label': h.classification}
                    for h in reversed(history)
                ])
                
                fig = go.Figure()
                fig.add_trace(go.Scatter(
                    x=df_history['Date'],
                    y=df_history['Value'],
                    fill='tozeroy',
                    line=dict(color='#667eea'),
                    fillcolor='rgba(102, 126, 234, 0.2)'
                ))
                
                # Zone colors
                fig.add_hrect(y0=0, y1=25, fillcolor="red", opacity=0.1, line_width=0)
                fig.add_hrect(y0=75, y1=100, fillcolor="green", opacity=0.1, line_width=0)
                fig.add_hline(y=50, line_dash="dash", line_color="gray")
                
                fig.update_layout(
                    height=200,
                    margin=dict(l=0, r=0, t=0, b=0),
                    plot_bgcolor='rgba(0,0,0,0)',
                    paper_bgcolor='rgba(0,0,0,0)',
                    yaxis=dict(range=[0, 100], showgrid=False),
                    xaxis=dict(showgrid=False),
                    showlegend=False
                )
                st.plotly_chart(fig, use_container_width=True)
        else:
            st.warning("⚠️ Impossible de charger le Fear & Greed Index")
    
    with col_market:
        st.subheader("🌍 Marché Global")
        
        global_data = get_global_market_data()
        
        if global_data:
            col1, col2 = st.columns(2)
            
            with col1:
                mcap = global_data.get('total_market_cap', 0)
                mcap_change = global_data.get('market_cap_change_24h', 0)
                st.metric(
                    "Market Cap Total",
                    f"${mcap/1e12:.2f}T",
                    f"{mcap_change:+.2f}%"
                )
                
                btc_dom = global_data.get('btc_dominance', 0)
                st.metric("BTC Dominance", f"{btc_dom:.1f}%")
            
            with col2:
                volume = global_data.get('total_volume_24h', 0)
                st.metric("Volume 24h", f"${volume/1e9:.1f}B")
                
                eth_dom = global_data.get('eth_dominance', 0)
                st.metric("ETH Dominance", f"{eth_dom:.1f}%")
            
            # Dominance pie chart
            fig_dom = px.pie(
                values=[btc_dom, eth_dom, 100 - btc_dom - eth_dom],
                names=['BTC', 'ETH', 'Altcoins'],
                color_discrete_sequence=['#f7931a', '#627eea', '#667eea'],
                hole=0.5
            )
            fig_dom.update_layout(
                height=200,
                margin=dict(l=0, r=0, t=0, b=0),
                showlegend=True,
                legend=dict(orientation="h", y=-0.1)
            )
            st.plotly_chart(fig_dom, use_container_width=True)
        else:
            st.warning("⚠️ Impossible de charger les données de marché")
    
    st.markdown("---")
    
    # ========== TRENDING TOKENS WITH DELTAS ==========
    st.subheader("🔥 Trending sur CoinGecko")
    
    # Import trending tracker
    try:
        from utils.trending_tracker import (
            get_trending_with_deltas, 
            format_delta, 
            format_delta_color,
            get_snapshot_count
        )
        TRACKER_AVAILABLE = True
    except ImportError:
        TRACKER_AVAILABLE = False
    
    if TRACKER_AVAILABLE:
        with st.spinner("Chargement du trending..."):
            trending_deltas = get_trending_with_deltas()
        
        # Show snapshot info
        snapshot_counts = get_snapshot_count()
        st.caption(f"📊 Snapshots: {snapshot_counts['24h']} (24h) | {snapshot_counts['7d']} (7j) | {snapshot_counts['total']} total")
        
        if trending_deltas:
            st.success(f"✅ {len(trending_deltas)} tokens trending chargés")
            
            # Simple table display
            for t in trending_deltas[:15]:
                delta_24h_str = format_delta(t.delta_24h, t.is_new_24h)
                delta_7d_str = format_delta(t.delta_7d, t.is_new_7d)
                delta_30d_str = format_delta(t.delta_30d, t.is_new_30d)
                
                # Color for 24h delta
                if t.is_new_24h or (t.delta_24h and t.delta_24h > 0):
                    color = "🟢"
                elif t.delta_24h and t.delta_24h < 0:
                    color = "🔴"
                else:
                    color = "⚪"
                
                cols = st.columns([1, 2, 3, 2, 2, 2, 2])
                cols[0].markdown(f"**#{t.current_rank}**")
                cols[1].markdown(f"**{t.symbol}**")
                cols[2].caption(t.name[:18])
                cols[3].caption(f"Rank #{t.market_cap_rank or 'N/A'}")
                cols[4].markdown(f"{color} {delta_24h_str}")
                cols[5].caption(delta_7d_str)
                cols[6].caption(delta_30d_str)
            
            # Legend
            st.markdown("---")
            st.caption("**Légende:** ↑3 = gagné 3 places | ↓2 = perdu 2 places | 🆕 NEW = nouveau | — = pas de données historiques")
        else:
            st.warning("⚠️ Impossible de charger les tokens trending")
    else:
        # Fallback to simple trending display
        trending = get_trending_tokens()
        
        if trending:
            cols = st.columns(5)
            
            for i, token in enumerate(trending[:10]):
                with cols[i % 5]:
                    rank_emoji = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"][i]
                    
                    st.markdown(f"""
                    <div style="padding: 10px; background: linear-gradient(135deg, #2d2d44 0%, #1e1e2e 100%); border-radius: 10px; text-align: center; margin-bottom: 10px;">
                        <div style="font-size: 1.5rem;">{rank_emoji}</div>
                        <div style="font-weight: bold;">{token.symbol}</div>
                        <div style="font-size: 0.8rem; color: #888;">{token.name[:15]}</div>
                        <div style="font-size: 0.7rem; color: #666;">Rank #{token.market_cap_rank or 'N/A'}</div>
                    </div>
                    """, unsafe_allow_html=True)
        else:
            st.info("📭 Impossible de charger les tokens trending")
    
    st.markdown("---")
    
    # ========== TOKENS BY MARKET CAP ==========
    if config and (config.trading.min_market_cap > 0 or config.trading.max_market_cap > 0):
        st.subheader("🎯 Tokens dans votre fourchette")
        
        min_cap = config.trading.min_market_cap
        max_cap = config.trading.max_market_cap
        
        cap_label = ""
        if min_cap > 0 and max_cap > 0:
            cap_label = f"${min_cap/1e6:.1f}M - ${max_cap/1e6:.1f}M"
        elif min_cap > 0:
            cap_label = f"> ${min_cap/1e6:.1f}M"
        elif max_cap > 0:
            cap_label = f"< ${max_cap/1e6:.1f}M"
        
        st.info(f"📊 Filtre Market Cap: **{cap_label}** (configurable dans Settings)")
        
        with st.spinner("Chargement des tokens..."):
            filtered_tokens = get_tokens_by_market_cap(min_cap, max_cap, limit=50)
        
        if filtered_tokens:
            st.caption(f"**{len(filtered_tokens)} tokens** correspondent à votre filtre")
            
            # Display as table
            import pandas as pd
            df = pd.DataFrame([
                {
                    'Rank': t.get('market_cap_rank', '-'),
                    'Token': f"{t['symbol']}",
                    'Nom': t['name'][:20],
                    'Market Cap': f"${t['market_cap']/1e6:.2f}M" if t.get('market_cap') else 'N/A',
                    'Prix': f"${t['price']:.4f}" if t.get('price') else 'N/A',
                    '24h': f"{t['price_change_24h']:+.2f}%" if t.get('price_change_24h') else 'N/A'
                }
                for t in filtered_tokens[:20]
            ])
            
            st.dataframe(
                df,
                column_config={
                    "Rank": st.column_config.NumberColumn("🏆"),
                    "Token": st.column_config.TextColumn("🪙 Token"),
                    "Nom": st.column_config.TextColumn("📝 Nom"),
                    "Market Cap": st.column_config.TextColumn("💰 MCap"),
                    "Prix": st.column_config.TextColumn("💵 Prix"),
                    "24h": st.column_config.TextColumn("📈 24h"),
                },
                hide_index=True,
                use_container_width=True
            )
        else:
            st.warning("⚠️ Aucun token ne correspond à votre filtre de market cap")
        
        st.markdown("---")
    
    # ========== TOKEN LOOKUP ==========
    st.subheader("🔍 Recherche Token")
    
    col_search, col_result = st.columns([1, 2])
    
    with col_search:
        token_id = st.text_input(
            "CoinGecko ID",
            value="bitcoin",
            help="Ex: bitcoin, ethereum, pepe, solana..."
        ).lower().strip()
        
        if st.button("🔍 Rechercher", type="primary"):
            with st.spinner("Chargement..."):
                stats = get_token_social_stats(token_id)
                st.session_state['token_stats'] = stats
    
    with col_result:
        if 'token_stats' in st.session_state and st.session_state['token_stats']:
            stats = st.session_state['token_stats']
            
            st.markdown(f"### {stats['name']} ({stats['symbol']})")
            
            # Metrics
            col1, col2, col3 = st.columns(3)
            
            with col1:
                if stats.get('twitter_followers'):
                    st.metric("🐦 Twitter", f"{stats['twitter_followers']:,}")
                if stats.get('telegram_members'):
                    st.metric("📱 Telegram", f"{stats['telegram_members']:,}")
            
            with col2:
                if stats.get('reddit_subscribers'):
                    st.metric("📖 Reddit", f"{stats['reddit_subscribers']:,}")
                if stats.get('reddit_active_48h'):
                    st.metric("📊 Reddit Active", f"{stats['reddit_active_48h']:,}")
            
            with col3:
                if stats.get('price_change_24h'):
                    st.metric("📈 Prix 24h", f"{stats['price_change_24h']:+.2f}%")
                if stats.get('price_change_7d'):
                    st.metric("📈 Prix 7d", f"{stats['price_change_7d']:+.2f}%")
            
            # Sentiment
            if stats.get('sentiment_up') is not None:
                up = stats['sentiment_up'] or 0
                down = stats['sentiment_down'] or 0
                st.markdown(f"**Sentiment CoinGecko:** 👍 {up:.0f}% | 👎 {down:.0f}%")
                st.progress(up / 100 if up else 0)
        
        elif 'token_stats' in st.session_state:
            st.warning("Token non trouvé. Vérifiez l'ID CoinGecko.")

    # ========== INFO ==========
    st.markdown("---")
    with st.expander("ℹ️ À propos des sources"):
        st.markdown("""
        **Sources actives :**
        - 😱 **Fear & Greed Index** - Sentiment global du marché crypto (Alternative.me)
        - 🦎 **CoinGecko Trending** - Top 10 tokens les plus recherchés
        - 📊 **CoinGecko Social Stats** - Twitter, Telegram, Reddit followers par token
        
        **Sources non disponibles :**
        - 🐦 **Twitter/X** - Nécessite API payante ($100+/mois depuis 2023)
        - 📖 **Reddit** - Bloqué depuis ce serveur (anti-bot)
        
        **Prochaines étapes possibles :**
        - Intégrer LunarCrush (API de sentiment social)
        - Ajouter un bot Telegram pour scraper les groupes crypto
        """)

# Navigation
st.markdown("---")
cols = st.columns(4)

with cols[0]:
    if st.button("🏠 Dashboard", use_container_width=True):
        st.switch_page("pages/0_dashboard.py")

with cols[1]:
    if st.button("👛 Wallets", use_container_width=True):
        st.switch_page("pages/1_wallet.py")

with cols[2]:
    if st.button("🎯 Stratégies", use_container_width=True):
        st.switch_page("pages/4_strategies.py")

with cols[3]:
    if st.button("🐋 Whales", use_container_width=True):
        st.switch_page("pages/7_whales.py")
