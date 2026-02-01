"""
Social Signals Module - Crypto sentiment and trending data
Uses reliable APIs: CoinMarketCap, CoinGecko, Alternative.me, Google Trends
"""

import requests
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
import time
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

CMC_API_KEY = os.getenv('CMC_API_KEY')
CMC_BASE_URL = 'https://pro-api.coinmarketcap.com/v1'
CRYPTOPANIC_API_KEY = os.getenv('CRYPTOPANIC_API_KEY')

# Rate limiting
LAST_REQUESTS = {}
MIN_INTERVAL = 1.0  # seconds between requests per endpoint


# ==================== GOOGLE TRENDS ====================

def get_google_trends(symbols: List[str], timeframe: str = 'now 7-d') -> Dict[str, int]:
    """
    Get Google Trends interest for crypto symbols.
    Returns dict of {symbol: interest_score (0-100)}
    No API key needed!
    """
    try:
        from pytrends.request import TrendReq
        
        # Clean symbols
        keywords = [s.lower() for s in symbols[:5]]  # Max 5 keywords
        
        pytrends = TrendReq(hl='en-US', tz=0, timeout=(10, 25))
        pytrends.build_payload(keywords, cat=0, timeframe=timeframe)
        
        data = pytrends.interest_over_time()
        
        if data.empty:
            return {}
        
        # Get latest value for each
        result = {}
        for kw in keywords:
            if kw in data.columns:
                result[kw.upper()] = int(data[kw].iloc[-1])
        
        return result
        
    except Exception as e:
        print(f"Google Trends error: {e}")
        return {}


def get_trend_score(symbol: str) -> Optional[int]:
    """Get Google Trends score for a single token (0-100)"""
    trends = get_google_trends([symbol])
    return trends.get(symbol.upper())


# ==================== CRYPTOPANIC (optional) ====================

def get_cryptopanic_sentiment(symbol: str = None) -> Dict[str, Any]:
    """
    Get news sentiment from CryptoPanic.
    Requires free API key from https://cryptopanic.com/developers/api/
    """
    if not CRYPTOPANIC_API_KEY:
        return {'error': 'No CryptoPanic API key configured'}
    
    try:
        params = {
            'auth_token': CRYPTOPANIC_API_KEY,
            'public': 'true',
            'filter': 'hot'
        }
        if symbol:
            params['currencies'] = symbol.upper()
        
        resp = requests.get(
            'https://cryptopanic.com/api/v1/posts/',
            params=params,
            timeout=10
        )
        resp.raise_for_status()
        data = resp.json()
        
        posts = data.get('results', [])
        if not posts:
            return {'sentiment': 0, 'posts': 0}
        
        # Calculate sentiment from votes
        bullish = sum(1 for p in posts if p.get('votes', {}).get('positive', 0) > p.get('votes', {}).get('negative', 0))
        bearish = sum(1 for p in posts if p.get('votes', {}).get('negative', 0) > p.get('votes', {}).get('positive', 0))
        
        total = bullish + bearish
        sentiment = (bullish - bearish) / total if total > 0 else 0
        
        return {
            'sentiment': sentiment,  # -1 to 1
            'posts': len(posts),
            'bullish': bullish,
            'bearish': bearish
        }
        
    except Exception as e:
        return {'error': str(e)}


def rate_limit(endpoint: str):
    """Respect rate limits"""
    now = time.time()
    last = LAST_REQUESTS.get(endpoint, 0)
    if now - last < MIN_INTERVAL:
        time.sleep(MIN_INTERVAL - (now - last))
    LAST_REQUESTS[endpoint] = time.time()


@dataclass
class TrendingToken:
    """Trending token data"""
    name: str
    symbol: str
    market_cap_rank: Optional[int]
    thumb: Optional[str]  # thumbnail URL
    score: int  # trending position
    price_btc: Optional[float] = None


@dataclass
class MarketSentiment:
    """Market sentiment data"""
    value: int  # 0-100
    classification: str  # "Extreme Fear", "Fear", "Neutral", "Greed", "Extreme Greed"
    timestamp: datetime
    

def get_fear_greed_index() -> Optional[MarketSentiment]:
    """
    Get crypto Fear & Greed Index from Alternative.me
    Free API, no key required
    """
    try:
        rate_limit('fear_greed')
        resp = requests.get(
            'https://api.alternative.me/fng/',
            params={'limit': 1},
            timeout=10
        )
        resp.raise_for_status()
        data = resp.json()
        
        if data.get('data'):
            item = data['data'][0]
            return MarketSentiment(
                value=int(item['value']),
                classification=item['value_classification'],
                timestamp=datetime.fromtimestamp(int(item['timestamp']))
            )
    except Exception as e:
        print(f"Fear & Greed API error: {e}")
    
    return None


def get_fear_greed_history(days: int = 30) -> List[MarketSentiment]:
    """Get historical Fear & Greed data"""
    try:
        rate_limit('fear_greed')
        resp = requests.get(
            'https://api.alternative.me/fng/',
            params={'limit': days},
            timeout=15
        )
        resp.raise_for_status()
        data = resp.json()
        
        history = []
        for item in data.get('data', []):
            history.append(MarketSentiment(
                value=int(item['value']),
                classification=item['value_classification'],
                timestamp=datetime.fromtimestamp(int(item['timestamp']))
            ))
        return history
    except Exception as e:
        print(f"Fear & Greed history error: {e}")
        return []


def get_trending_tokens() -> List[TrendingToken]:
    """
    Get trending tokens from CoinGecko
    Free API, no key required
    """
    try:
        rate_limit('coingecko_trending')
        resp = requests.get(
            'https://api.coingecko.com/api/v3/search/trending',
            timeout=15
        )
        resp.raise_for_status()
        data = resp.json()
        
        tokens = []
        for i, coin in enumerate(data.get('coins', [])):
            item = coin.get('item', {})
            tokens.append(TrendingToken(
                name=item.get('name', ''),
                symbol=item.get('symbol', '').upper(),
                market_cap_rank=item.get('market_cap_rank'),
                thumb=item.get('thumb'),
                score=i + 1,  # Position in trending
                price_btc=item.get('price_btc')
            ))
        return tokens
    except Exception as e:
        print(f"CoinGecko trending error: {e}")
        return []


def get_token_social_stats(token_id: str) -> Optional[Dict[str, Any]]:
    """
    Get social stats for a specific token from CoinGecko
    Returns twitter followers, telegram members, reddit subscribers, etc.
    """
    try:
        rate_limit('coingecko_coin')
        resp = requests.get(
            f'https://api.coingecko.com/api/v3/coins/{token_id}',
            params={
                'localization': 'false',
                'tickers': 'false',
                'market_data': 'true',
                'community_data': 'true',
                'developer_data': 'false'
            },
            timeout=15
        )
        resp.raise_for_status()
        data = resp.json()
        
        community = data.get('community_data', {})
        market = data.get('market_data', {})
        
        return {
            'name': data.get('name'),
            'symbol': data.get('symbol', '').upper(),
            'twitter_followers': community.get('twitter_followers'),
            'telegram_members': community.get('telegram_channel_user_count'),
            'reddit_subscribers': community.get('reddit_subscribers'),
            'reddit_active_48h': community.get('reddit_accounts_active_48h'),
            'sentiment_up': data.get('sentiment_votes_up_percentage'),
            'sentiment_down': data.get('sentiment_votes_down_percentage'),
            'price_change_24h': market.get('price_change_percentage_24h'),
            'price_change_7d': market.get('price_change_percentage_7d'),
            'volume_24h': market.get('total_volume', {}).get('usd'),
            'market_cap': market.get('market_cap', {}).get('usd'),
        }
    except Exception as e:
        print(f"CoinGecko coin data error: {e}")
        return None


def get_global_market_data() -> Optional[Dict[str, Any]]:
    """Get global crypto market data"""
    try:
        rate_limit('coingecko_global')
        resp = requests.get(
            'https://api.coingecko.com/api/v3/global',
            timeout=10
        )
        resp.raise_for_status()
        data = resp.json().get('data', {})
        
        return {
            'total_market_cap': data.get('total_market_cap', {}).get('usd'),
            'total_volume_24h': data.get('total_volume', {}).get('usd'),
            'btc_dominance': data.get('market_cap_percentage', {}).get('btc'),
            'eth_dominance': data.get('market_cap_percentage', {}).get('eth'),
            'market_cap_change_24h': data.get('market_cap_change_percentage_24h_usd'),
            'active_cryptocurrencies': data.get('active_cryptocurrencies'),
        }
    except Exception as e:
        print(f"CoinGecko global data error: {e}")
        return None


def calculate_sentiment_score(fear_greed: int, price_change_24h: float = 0) -> float:
    """
    Calculate normalized sentiment score (-1 to 1)
    Combines Fear & Greed Index with price momentum
    """
    # Fear & Greed: 0-100 -> -1 to 1
    fg_normalized = (fear_greed - 50) / 50  # -1 at 0, +1 at 100
    
    # Price change: cap at ±20% for normalization
    price_capped = max(-20, min(20, price_change_24h))
    price_normalized = price_capped / 20  # -1 to +1
    
    # Weighted average (70% fear/greed, 30% price)
    combined = fg_normalized * 0.7 + price_normalized * 0.3
    
    return round(combined, 3)


def filter_by_market_cap(tokens: List[Dict], min_cap: float = 0, max_cap: float = 0) -> List[Dict]:
    """
    Filter tokens by market cap range
    
    Args:
        tokens: List of token dicts with 'market_cap' key
        min_cap: Minimum market cap (0 = no minimum)
        max_cap: Maximum market cap (0 = no maximum)
    """
    if min_cap == 0 and max_cap == 0:
        return tokens  # No filter
    
    filtered = []
    for token in tokens:
        mcap = token.get('market_cap', 0)
        if mcap is None:
            continue
        
        # Check minimum
        if min_cap > 0 and mcap < min_cap:
            continue
        
        # Check maximum
        if max_cap > 0 and mcap > max_cap:
            continue
        
        filtered.append(token)
    
    return filtered


def get_tokens_by_market_cap_cmc(min_cap: float = 0, max_cap: float = 0, limit: int = 100) -> List[Dict]:
    """
    Get tokens within a market cap range from CoinMarketCap.
    Free tier doesn't support native filtering, but we paginate smartly.
    """
    if not CMC_API_KEY:
        return []
    
    # Estimate starting rank based on max_cap
    # Rough mapping: rank 1-50 = >$1B, 50-200 = $100M-$1B, 200-800 = $1M-$100M
    if max_cap > 0 and max_cap <= 100_000_000:  # Small caps < $100M
        start_rank = 200
    elif max_cap > 0 and max_cap <= 1_000_000_000:  # Mid caps < $1B
        start_rank = 50
    else:
        start_rank = 1
    
    tokens = []
    
    try:
        rate_limit('cmc_listings')
        
        resp = requests.get(
            f'{CMC_BASE_URL}/cryptocurrency/listings/latest',
            headers={
                'X-CMC_PRO_API_KEY': CMC_API_KEY,
                'Accept': 'application/json'
            },
            params={
                'start': start_rank,
                'limit': 200,  # CMC free tier max
                'sort': 'market_cap',
                'sort_dir': 'desc',
                'convert': 'USD'
            },
            timeout=15
        )
        resp.raise_for_status()
        data = resp.json()
        
        for coin in data.get('data', []):
            quote = coin.get('quote', {}).get('USD', {})
            mcap = quote.get('market_cap', 0)
            
            if mcap is None or mcap == 0:
                continue
            
            # Filter by market cap range
            if min_cap > 0 and mcap < min_cap:
                continue
            if max_cap > 0 and mcap > max_cap:
                continue
            
            tokens.append({
                'id': coin.get('slug'),
                'symbol': coin.get('symbol', '').upper(),
                'name': coin.get('name'),
                'market_cap': mcap,
                'market_cap_rank': coin.get('cmc_rank'),
                'price': quote.get('price'),
                'price_change_24h': quote.get('percent_change_24h'),
                'volume_24h': quote.get('volume_24h'),
                'image': None
            })
            
            if len(tokens) >= limit:
                break
        
        return tokens
        
    except Exception as e:
        print(f"CoinMarketCap error: {e}")
        return []


def get_tokens_by_market_cap(min_cap: float = 0, max_cap: float = 0, limit: int = 100) -> List[Dict]:
    """
    Get tokens within a market cap range.
    Uses CoinMarketCap (faster, native filtering) with CoinGecko fallback.
    """
    # Try CMC first (has native market cap filtering)
    if CMC_API_KEY:
        tokens = get_tokens_by_market_cap_cmc(min_cap, max_cap, limit)
        if tokens:
            return tokens
    
    # Fallback to CoinGecko with pagination
    import time
    
    tokens = []
    page = 1
    max_pages = 5
    per_page = 250
    
    if max_cap > 0 and max_cap < 1e9:
        page = 3
    elif max_cap > 0 and max_cap < 10e9:
        page = 2
    
    try:
        while len(tokens) < limit and page <= max_pages:
            rate_limit('coingecko_markets')
            
            resp = requests.get(
                'https://api.coingecko.com/api/v3/coins/markets',
                params={
                    'vs_currency': 'usd',
                    'order': 'market_cap_desc',
                    'per_page': per_page,
                    'page': page,
                    'sparkline': 'false'
                },
                timeout=15
            )
            resp.raise_for_status()
            data = resp.json()
            
            if not data:
                break
            
            for coin in data:
                mcap = coin.get('market_cap', 0)
                if mcap is None:
                    continue
                if min_cap > 0 and mcap < min_cap:
                    continue
                if max_cap > 0 and mcap > max_cap:
                    continue
                
                tokens.append({
                    'id': coin.get('id'),
                    'symbol': coin.get('symbol', '').upper(),
                    'name': coin.get('name'),
                    'market_cap': mcap,
                    'market_cap_rank': coin.get('market_cap_rank'),
                    'price': coin.get('current_price'),
                    'price_change_24h': coin.get('price_change_percentage_24h'),
                    'volume_24h': coin.get('total_volume'),
                    'image': coin.get('image')
                })
                
                if len(tokens) >= limit:
                    break
            
            page += 1
            time.sleep(0.5)
        
        return tokens[:limit]
        
    except Exception as e:
        print(f"CoinGecko markets error: {e}")
        return tokens  # Return what we found so far


def get_signals_summary() -> Dict[str, Any]:
    """
    Get a summary of all social signals
    """
    summary = {
        'fear_greed': None,
        'trending': [],
        'global_market': None,
        'last_updated': datetime.now().isoformat()
    }
    
    # Fear & Greed
    fg = get_fear_greed_index()
    if fg:
        summary['fear_greed'] = {
            'value': fg.value,
            'classification': fg.classification,
            'sentiment_score': calculate_sentiment_score(fg.value)
        }
    
    # Trending
    trending = get_trending_tokens()
    summary['trending'] = [
        {
            'name': t.name,
            'symbol': t.symbol,
            'rank': t.market_cap_rank,
            'trending_position': t.score
        }
        for t in trending[:10]
    ]
    
    # Global market
    summary['global_market'] = get_global_market_data()
    
    return summary


# ============ Source Status ============

def get_source_status() -> Dict[str, Dict]:
    """Check which data sources are available"""
    status = {}
    
    # Fear & Greed Index
    try:
        fg = get_fear_greed_index()
        status['fear_greed'] = {
            'name': 'Fear & Greed Index',
            'icon': '😱',
            'connected': fg is not None,
            'description': 'Market sentiment (Alternative.me)'
        }
    except:
        status['fear_greed'] = {'name': 'Fear & Greed Index', 'icon': '😱', 'connected': False}
    
    # CoinGecko Trending
    try:
        trending = get_trending_tokens()
        status['coingecko'] = {
            'name': 'CoinGecko Trending',
            'icon': '🦎',
            'connected': len(trending) > 0,
            'description': f'{len(trending)} trending tokens'
        }
    except:
        status['coingecko'] = {'name': 'CoinGecko Trending', 'icon': '🦎', 'connected': False}
    
    # Twitter (not available without API)
    status['twitter'] = {
        'name': 'Twitter/X',
        'icon': '🐦',
        'connected': False,
        'description': 'Requires API key ($100/mo minimum)'
    }
    
    # Reddit (blocked from VPS)
    status['reddit'] = {
        'name': 'Reddit',
        'icon': '📖',
        'connected': False,
        'description': 'Blocked from this server'
    }
    
    return status
