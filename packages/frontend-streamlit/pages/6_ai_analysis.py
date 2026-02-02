"""
🤖 AI Analysis - Analyse automatique des tokens
Récupère les signaux, analyse et recommande BUY/SELL/HOLD
"""

import streamlit as st
import pandas as pd
from datetime import datetime
import sys
import os
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
ai_path = os.path.join(os.path.dirname(__file__), '..', '..', 'ai-decision', 'python')
sys.path.insert(0, ai_path)

st.set_page_config(
    page_title="🤖 AI Analysis | SmallCap Trader",
    page_icon="🤖",
    layout="wide"
)

# Imports
try:
    from utils.social_signals import (
        get_fear_greed_index,
        get_trending_tokens,
        get_tokens_by_market_cap,
        get_google_trends,
        get_cryptopanic_sentiment
    )
    from utils.config import load_config
    from analyzer import analyze_token, TradingAction
    MODULES_OK = True
except ImportError as e:
    MODULES_OK = False
    st.error(f"❌ Module error: {e}")
    st.stop()

import requests

def fetch_token_details(coingecko_id: str) -> dict:
    """Fetch detailed token data from CoinGecko"""
    try:
        resp = requests.get(
            f'https://api.coingecko.com/api/v3/coins/{coingecko_id}',
            params={'localization': 'false', 'tickers': 'false', 'community_data': 'true'},
            timeout=10
        )
        if resp.status_code != 200:
            return None
        data = resp.json()
        
        market = data.get('market_data', {})
        sentiment_up = data.get('sentiment_votes_up_percentage', 50)
        
        return {
            'id': coingecko_id,
            'name': data.get('name'),
            'symbol': data.get('symbol', '').upper(),
            'price': market.get('current_price', {}).get('usd'),
            'price_change_24h': market.get('price_change_percentage_24h'),
            'price_change_7d': market.get('price_change_percentage_7d'),
            'volume_24h': market.get('total_volume', {}).get('usd'),
            'market_cap': market.get('market_cap', {}).get('usd'),
            'sentiment_score': (sentiment_up - 50) / 50 if sentiment_up else 0,
        }
    except:
        return None


def analyze_token_auto(token_data: dict, fg_value: int = 50, trends_data: dict = None, cryptopanic_data: dict = None) -> dict:
    """Run AI analysis on a token with fetched data + Google Trends + CryptoPanic"""
    if not token_data:
        return None
    
    symbol = token_data.get('symbol', '').upper()
    
    # Fear & Greed modifier (-0.5 to +0.5)
    fg_modifier = (fg_value - 50) / 100
    
    # Google Trends modifier (-0.5 to +0.5)
    trends_modifier = 0
    if trends_data and symbol in trends_data:
        trends_score = trends_data[symbol]
        trends_modifier = (trends_score - 50) / 100
    
    # CryptoPanic sentiment modifier (-0.5 to +0.5)
    cp_modifier = 0
    if cryptopanic_data and 'sentiment' in cryptopanic_data:
        cp_modifier = cryptopanic_data['sentiment'] * 0.5  # Already -1 to 1, scale to -0.5 to 0.5
    
    # Blend token sentiment with global signals
    token_sentiment = token_data.get('sentiment_score', 0)
    # 40% token sentiment, 25% Fear&Greed, 20% Google Trends, 15% CryptoPanic
    final_sentiment = (token_sentiment * 0.4) + (fg_modifier * 0.25) + (trends_modifier * 0.2) + (cp_modifier * 0.15)
    
    # Prepare data for analyzer
    sentiment_data = {
        'score': final_sentiment,
        'sample_count': 50
    }
    
    price_data = None
    p24 = token_data.get('price_change_24h')
    p7d = token_data.get('price_change_7d')
    if p24 is not None or p7d is not None:
        price_data = {
            'change_24h': p24 or 0,
            'change_7d': p7d or 0
        }
    
    # Volume data - estimate change based on market cap ratio
    volume_data = None
    vol = token_data.get('volume_24h')
    mcap = token_data.get('market_cap')
    if vol and mcap and mcap > 0:
        vol_ratio = (vol / mcap) * 100  # Volume as % of mcap
        # High volume ratio = bullish signal
        volume_change = (vol_ratio - 5) * 10  # Normalize around 5% baseline
        volume_data = {'change_24h': min(max(volume_change, -100), 500)}
    
    try:
        result = analyze_token(
            symbol=token_data.get('symbol', '?'),
            network='multi',
            sentiment_data=sentiment_data,
            volume_data=volume_data,
            price_data=price_data
        )
        
        return {
            'symbol': token_data.get('symbol'),
            'name': token_data.get('name'),
            'price': token_data.get('price'),
            'price_change_24h': p24,
            'market_cap': token_data.get('market_cap'),
            'action': result.action.value,
            'score': result.score.total_score,
            'confidence': result.confidence,
            'reason': result.prediction.reason
        }
    except Exception as e:
        return None


# ==================== PAGE ====================

st.title("🤖 AI Analysis")
st.caption("Analyse automatique des tokens basée sur les signaux sociaux et de marché")

# Disclaimer
st.markdown("""
<div style="background: linear-gradient(90deg, #ff6b6b22 0%, #ffa50022 100%); 
            padding: 10px 15px; border-radius: 8px; margin-bottom: 15px; border-left: 4px solid #ff6b6b;">
    ⚠️ <strong>EXPERIMENTAL</strong> - Système basé sur des règles, pas du ML. Ne constitue pas un conseil financier.
</div>
""", unsafe_allow_html=True)

# Fear & Greed at top
fg = get_fear_greed_index()
fg_value = fg.value if fg else 50

if fg:
    fg_color = "#ff4444" if fg.value <= 25 else "#ff8844" if fg.value <= 45 else "#ffff44" if fg.value <= 55 else "#88ff44" if fg.value <= 75 else "#44ff44"
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown(f"""
        <div style="background: {fg_color}22; padding: 15px; border-radius: 10px; text-align: center; border: 2px solid {fg_color};">
            <div style="font-size: 2.5rem; font-weight: bold; color: {fg_color};">{fg.value}</div>
            <div>😱 Fear & Greed: <strong>{fg.classification}</strong></div>
        </div>
        """, unsafe_allow_html=True)

st.markdown("---")

# Source selection
config = load_config()
source = st.radio(
    "📊 Source des tokens",
    ["🔥 Trending CoinGecko", "🎯 Filtre Market Cap"],
    horizontal=True
)

# Run analysis button
if st.button("🚀 Lancer l'analyse automatique", type="primary", use_container_width=True):
    
    # Get tokens based on source
    tokens_to_analyze = []
    
    with st.spinner("Récupération des tokens..."):
        if "Trending" in source:
            trending = get_trending_tokens()
            if trending:
                tokens_to_analyze = [
                    {'id': t.name.lower().replace(' ', '-'), 'symbol': t.symbol, 'name': t.name}
                    for t in trending[:15]
                ]
                st.info(f"📊 {len(tokens_to_analyze)} tokens trending à analyser")
        else:
            min_cap = config.trading.min_market_cap
            max_cap = config.trading.max_market_cap
            filtered = get_tokens_by_market_cap(min_cap, max_cap, limit=20)
            if filtered:
                tokens_to_analyze = [
                    {'id': t.get('id', t['symbol'].lower()), 'symbol': t['symbol'], 'name': t['name']}
                    for t in filtered
                ]
                cap_label = f"${min_cap/1e6:.0f}M - ${max_cap/1e6:.0f}M" if max_cap else f"> ${min_cap/1e6:.0f}M"
                st.info(f"📊 {len(tokens_to_analyze)} tokens ({cap_label}) à analyser")
    
    if not tokens_to_analyze:
        st.warning("⚠️ Aucun token trouvé. Vérifie tes filtres dans Settings.")
    else:
        # Fetch Google Trends for all symbols at once (max 5)
        symbols = [t['symbol'] for t in tokens_to_analyze[:5]]
        
        with st.spinner("📈 Récupération Google Trends..."):
            trends_data = get_google_trends(symbols)
            if trends_data:
                st.caption(f"📈 Google Trends: {', '.join([f'{k}={v}' for k,v in trends_data.items()])}")
        
        # Fetch CryptoPanic global sentiment
        with st.spinner("📰 Récupération CryptoPanic..."):
            cryptopanic_data = get_cryptopanic_sentiment()
            if cryptopanic_data and cryptopanic_data.get('posts', 0) > 0:
                st.caption(f"📰 CryptoPanic: {cryptopanic_data['posts']} news | Sentiment: {cryptopanic_data['sentiment']:+.2f}")
        
        # Analyze each token
        results = []
        progress = st.progress(0, text="Analyse en cours...")
        
        for i, token in enumerate(tokens_to_analyze):
            progress.progress((i + 1) / len(tokens_to_analyze), text=f"Analyse de {token['symbol']}...")
            
            # Fetch detailed data
            details = fetch_token_details(token['id'])
            if not details:
                # Try with symbol as fallback
                details = fetch_token_details(token['symbol'].lower())
            
            if details:
                result = analyze_token_auto(details, fg_value, trends_data, cryptopanic_data)
                if result:
                    results.append(result)
            
            # Rate limiting
            time.sleep(0.3)
        
        progress.empty()
        
        if results:
            st.session_state['ai_results'] = results
            st.success(f"✅ {len(results)} tokens analysés!")
        else:
            st.error("❌ Impossible d'analyser les tokens")

# Display results
if 'ai_results' in st.session_state and st.session_state['ai_results']:
    results = st.session_state['ai_results']
    
    st.markdown("---")
    st.subheader("📋 Résultats de l'analyse")
    
    # Sort by score descending
    results_sorted = sorted(results, key=lambda x: x['score'], reverse=True)
    
    # Summary cards
    buys = [r for r in results_sorted if r['action'] == 'BUY']
    sells = [r for r in results_sorted if r['action'] == 'SELL']
    holds = [r for r in results_sorted if r['action'] == 'HOLD']
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown(f"""
        <div style="background: #00ff8822; padding: 15px; border-radius: 10px; text-align: center;">
            <div style="font-size: 2rem; color: #00ff88;">🟢 {len(buys)}</div>
            <div>BUY</div>
        </div>
        """, unsafe_allow_html=True)
    with col2:
        st.markdown(f"""
        <div style="background: #ffaa0022; padding: 15px; border-radius: 10px; text-align: center;">
            <div style="font-size: 2rem; color: #ffaa00;">🟡 {len(holds)}</div>
            <div>HOLD</div>
        </div>
        """, unsafe_allow_html=True)
    with col3:
        st.markdown(f"""
        <div style="background: #ff444422; padding: 15px; border-radius: 10px; text-align: center;">
            <div style="font-size: 2rem; color: #ff4444;">🔴 {len(sells)}</div>
            <div>SELL</div>
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown("---")
    
    # Detailed results
    for r in results_sorted:
        action_color = {"BUY": "#00ff88", "SELL": "#ff4444", "HOLD": "#ffaa00"}.get(r['action'], "#888")
        action_emoji = {"BUY": "🟢", "SELL": "🔴", "HOLD": "🟡"}.get(r['action'], "❓")
        
        with st.container():
            cols = st.columns([1, 2, 1, 1, 1, 3])
            
            with cols[0]:
                st.markdown(f"<div style='font-size: 1.5rem;'>{action_emoji}</div>", unsafe_allow_html=True)
            
            with cols[1]:
                st.markdown(f"**{r['symbol']}**")
                st.caption(r['name'][:20])
            
            with cols[2]:
                if r.get('price'):
                    st.markdown(f"${r['price']:.4f}")
                else:
                    st.markdown("--")
            
            with cols[3]:
                p24 = r.get('price_change_24h')
                if p24:
                    color = "green" if p24 > 0 else "red"
                    st.markdown(f":{color}[{p24:+.1f}%]")
                else:
                    st.markdown("--")
            
            with cols[4]:
                st.markdown(f"**{r['score']:.0f}**/100")
                st.caption(f"{r['confidence']*100:.0f}% conf.")
            
            with cols[5]:
                st.caption(r.get('reason', '')[:60])
        
        st.markdown("<hr style='margin: 5px 0; opacity: 0.2;'>", unsafe_allow_html=True)
    
    # Export
    st.markdown("---")
    df = pd.DataFrame(results_sorted)
    csv = df.to_csv(index=False)
    st.download_button(
        "📥 Exporter CSV",
        csv,
        "ai_analysis.csv",
        "text/csv"
    )

# Navigation
st.markdown("---")
cols = st.columns(4)
with cols[0]:
    if st.button("🏠 Dashboard", use_container_width=True):
        st.switch_page("pages/0_dashboard.py")
with cols[1]:
    if st.button("📡 Signals", use_container_width=True):
        st.switch_page("pages/3_signals.py")
with cols[2]:
    if st.button("🎯 Strategies", use_container_width=True):
        st.switch_page("pages/8_simulation.py")
with cols[3]:
    if st.button("⚙️ Settings", use_container_width=True):
        st.switch_page("pages/5_settings.py")
