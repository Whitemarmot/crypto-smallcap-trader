"""
🤖 AI Trading Agent - Vrai agent IA autonome
Utilise Claude pour analyser et décider
"""

import os
import json
import requests
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()

# Anthropic API
ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY')
ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"


@dataclass
class AIDecision:
    """Decision from the AI agent"""
    symbol: str
    action: str  # BUY, SELL, HOLD
    confidence: float  # 0-100
    reasoning: str
    price: float
    target_price: Optional[float] = None
    stop_loss: Optional[float] = None
    data_used: Dict[str, Any] = None


def fetch_token_data(symbol: str) -> Dict[str, Any]:
    """Fetch all available data for a token"""
    data = {
        'symbol': symbol,
        'timestamp': datetime.now().isoformat(),
        'price': None,
        'price_change_24h': None,
        'price_change_7d': None,
        'volume_24h': None,
        'market_cap': None,
        'fear_greed': None,
        'trending_rank': None,
        'google_trends': None,
        'news': [],
        'sentiment': None
    }
    
    # 1. Get price data from CoinGecko
    try:
        # Map symbol to CoinGecko ID
        symbol_map = {
            'BTC': 'bitcoin', 'ETH': 'ethereum', 'SOL': 'solana',
            'PEPE': 'pepe', 'DOGE': 'dogecoin', 'SHIB': 'shiba-inu',
            'XRP': 'ripple', 'ADA': 'cardano', 'AVAX': 'avalanche-2',
            'LINK': 'chainlink', 'DOT': 'polkadot', 'MATIC': 'matic-network',
            'ARB': 'arbitrum', 'OP': 'optimism', 'BONK': 'bonk'
        }
        cg_id = symbol_map.get(symbol.upper(), symbol.lower())
        
        resp = requests.get(
            f'https://api.coingecko.com/api/v3/coins/{cg_id}',
            params={'localization': 'false', 'tickers': 'false', 'community_data': 'true'},
            timeout=10
        )
        if resp.status_code == 200:
            cg_data = resp.json()
            market = cg_data.get('market_data', {})
            data['price'] = market.get('current_price', {}).get('usd')
            data['price_change_24h'] = market.get('price_change_percentage_24h')
            data['price_change_7d'] = market.get('price_change_percentage_7d')
            data['volume_24h'] = market.get('total_volume', {}).get('usd')
            data['market_cap'] = market.get('market_cap', {}).get('usd')
            data['sentiment'] = cg_data.get('sentiment_votes_up_percentage')
    except Exception as e:
        print(f"CoinGecko error: {e}")
    
    # 2. Get Fear & Greed Index
    try:
        resp = requests.get('https://api.alternative.me/fng/', timeout=10)
        if resp.status_code == 200:
            fg_data = resp.json().get('data', [{}])[0]
            data['fear_greed'] = {
                'value': int(fg_data.get('value', 50)),
                'classification': fg_data.get('value_classification', 'Neutral')
            }
    except Exception as e:
        print(f"Fear & Greed error: {e}")
    
    # 3. Check if trending on CoinGecko
    try:
        resp = requests.get('https://api.coingecko.com/api/v3/search/trending', timeout=10)
        if resp.status_code == 200:
            trending = resp.json().get('coins', [])
            for i, coin in enumerate(trending):
                if coin.get('item', {}).get('symbol', '').upper() == symbol.upper():
                    data['trending_rank'] = i + 1
                    break
    except Exception as e:
        print(f"Trending error: {e}")
    
    # 4. Get Google Trends (if available)
    try:
        from pytrends.request import TrendReq
        pytrends = TrendReq(hl='en-US', tz=0, timeout=(5, 10))
        pytrends.build_payload([symbol.lower()], timeframe='now 7-d')
        trends = pytrends.interest_over_time()
        if not trends.empty:
            data['google_trends'] = int(trends[symbol.lower()].iloc[-1])
    except Exception as e:
        print(f"Google Trends error: {e}")
    
    # 5. Get news from CryptoPanic (if available)
    try:
        from utils.social_signals import get_cryptopanic_posts
        posts = get_cryptopanic_posts(symbol)
        if posts:
            data['news'] = [{'title': p.get('title', '')[:100], 'votes': p.get('votes', {})} for p in posts[:5]]
    except Exception as e:
        print(f"CryptoPanic error: {e}")
    
    return data


def ask_claude_decision(token_data: Dict[str, Any], profile: str = 'modere') -> AIDecision:
    """Ask Claude to analyze data and make a trading decision"""
    
    if not ANTHROPIC_API_KEY:
        # Fallback to rule-based if no API key
        return fallback_decision(token_data)
    
    # Build the prompt
    symbol = token_data.get('symbol', 'UNKNOWN')
    
    prompt = f"""Tu es un trader crypto expérimenté. Analyse ces données et donne une décision de trading.

## Données du token {symbol}:

**Prix & Marché:**
- Prix actuel: ${token_data.get('price', 'N/A')}
- Variation 24h: {token_data.get('price_change_24h', 'N/A')}%
- Variation 7j: {token_data.get('price_change_7d', 'N/A')}%
- Volume 24h: ${token_data.get('volume_24h', 'N/A'):,.0f}
- Market Cap: ${token_data.get('market_cap', 'N/A'):,.0f}

**Sentiment:**
- Fear & Greed Index: {token_data.get('fear_greed', {}).get('value', 'N/A')} ({token_data.get('fear_greed', {}).get('classification', 'N/A')})
- Sentiment CoinGecko: {token_data.get('sentiment', 'N/A')}% positif
- Google Trends (0-100): {token_data.get('google_trends', 'N/A')}
- Trending Rank: #{token_data.get('trending_rank', 'Non trending')}

**News récentes:**
{chr(10).join(['- ' + n.get('title', '') for n in token_data.get('news', [])[:3]]) or '- Aucune news récente'}

## Profil de trading: {profile.upper()}
{"- Conservateur: Peu de trades, haute conviction requise" if profile == 'conservateur' else ""}
{"- Modéré: Équilibré entre risque et opportunité" if profile == 'modere' else ""}
{"- Agressif: Plus de trades, tolérance au risque plus élevée" if profile == 'agressif' else ""}
{"- Degen: YOLO, cherche les gros gains" if profile == 'degen' else ""}

## Ta décision:
Réponds UNIQUEMENT avec un JSON valide (pas de texte avant ou après):
{{
    "action": "BUY" ou "SELL" ou "HOLD",
    "confidence": 0-100,
    "reasoning": "Explication courte de ta décision",
    "target_price": prix cible si BUY (ou null),
    "stop_loss": prix stop-loss si BUY (ou null)
}}
"""

    try:
        response = requests.post(
            ANTHROPIC_URL,
            headers={
                'Content-Type': 'application/json',
                'x-api-key': ANTHROPIC_API_KEY,
                'anthropic-version': '2023-06-01'
            },
            json={
                'model': 'claude-3-haiku-20240307',  # Fast & cheap for trading decisions
                'max_tokens': 500,
                'messages': [{'role': 'user', 'content': prompt}]
            },
            timeout=30
        )
        
        if response.status_code == 200:
            content = response.json().get('content', [{}])[0].get('text', '{}')
            # Parse JSON from response
            try:
                decision_data = json.loads(content)
            except json.JSONDecodeError:
                # Try to extract JSON from text
                import re
                json_match = re.search(r'\{.*\}', content, re.DOTALL)
                if json_match:
                    decision_data = json.loads(json_match.group())
                else:
                    return fallback_decision(token_data)
            
            return AIDecision(
                symbol=symbol,
                action=decision_data.get('action', 'HOLD'),
                confidence=float(decision_data.get('confidence', 50)),
                reasoning=decision_data.get('reasoning', 'No reasoning provided'),
                price=token_data.get('price', 0),
                target_price=decision_data.get('target_price'),
                stop_loss=decision_data.get('stop_loss'),
                data_used=token_data
            )
        else:
            print(f"Claude API error: {response.status_code} - {response.text}")
            return fallback_decision(token_data)
            
    except Exception as e:
        print(f"Claude request error: {e}")
        return fallback_decision(token_data)


def fallback_decision(token_data: Dict[str, Any]) -> AIDecision:
    """Fallback rule-based decision when Claude is unavailable"""
    symbol = token_data.get('symbol', 'UNKNOWN')
    price = token_data.get('price', 0)
    fg = token_data.get('fear_greed', {}).get('value', 50)
    p24h = token_data.get('price_change_24h', 0) or 0
    trending = token_data.get('trending_rank')
    
    score = 50
    reasons = []
    
    # Fear & Greed scoring
    if fg <= 25:
        score += 25
        reasons.append(f"Extreme Fear ({fg}) = opportunité d'achat")
    elif fg <= 40:
        score += 15
        reasons.append(f"Fear ({fg}) = bon point d'entrée")
    elif fg >= 75:
        score -= 25
        reasons.append(f"Extreme Greed ({fg}) = prudence")
    elif fg >= 60:
        score -= 15
        reasons.append(f"Greed ({fg}) = réduire exposition")
    
    # Price momentum
    if p24h > 10:
        score += 10
        reasons.append(f"Momentum positif (+{p24h:.1f}%)")
    elif p24h < -10:
        score -= 10
        reasons.append(f"Momentum négatif ({p24h:.1f}%)")
    
    # Trending bonus
    if trending and trending <= 5:
        score += 15
        reasons.append(f"Trending #{trending}")
    
    # Decide action
    if score >= 70:
        action = "BUY"
    elif score <= 35:
        action = "SELL"
    else:
        action = "HOLD"
    
    return AIDecision(
        symbol=symbol,
        action=action,
        confidence=min(abs(score - 50) * 2, 100),
        reasoning=" | ".join(reasons) if reasons else "Analyse basée sur les règles",
        price=price,
        data_used=token_data
    )


def analyze_token(symbol: str, profile: str = 'modere') -> AIDecision:
    """Main function: fetch data and get AI decision"""
    # 1. Fetch all data
    data = fetch_token_data(symbol)
    
    # 2. Get AI decision
    decision = ask_claude_decision(data, profile)
    
    return decision


def analyze_multiple_tokens(symbols: List[str], profile: str = 'modere') -> List[AIDecision]:
    """Analyze multiple tokens"""
    import time
    decisions = []
    
    for symbol in symbols:
        decision = analyze_token(symbol, profile)
        decisions.append(decision)
        time.sleep(0.5)  # Rate limiting
    
    return decisions
