"""
Social Signal Analyzer for Crypto SmallCap Trader
Analyzes social media for crypto mentions, sentiment, and hype detection.

Sources:
- Reddit (public JSON API, no auth required)
- Future: Twitter/X, Telegram (require API keys)
"""

import re
import time
import requests
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
from collections import Counter
from dataclasses import dataclass
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ============ CRYPTO SENTIMENT LEXICON ============

BULLISH_WORDS = {
    'moon': 4, 'mooning': 5, 'bullish': 4, 'pump': 3, 'pumping': 4,
    'gem': 3, 'diamond': 3, 'hodl': 2, 'lfg': 3, 'wagmi': 3,
    'alpha': 3, 'undervalued': 3, 'breakout': 3, 'accumulate': 2,
    'bullrun': 4, 'lambo': 2, 'rocket': 3, 'massive': 2,
    'explode': 3, 'exploding': 4, 'launch': 2, 'airdrop': 2,
    'whale': 1, 'buy': 2, 'buying': 2, 'gains': 3, 'profit': 2,
    'green': 2, 'rally': 3, 'surge': 3, 'soaring': 4, 'rising': 2,
    'uptrend': 3, 'golden': 2, 'opportunity': 2, 'potential': 2,
    '100x': 5, '10x': 4, '1000x': 5, 'early': 2
}

BEARISH_WORDS = {
    'dump': -4, 'dumping': -5, 'rug': -5, 'rugpull': -5, 'scam': -5,
    'ponzi': -5, 'bearish': -4, 'crash': -4, 'crashing': -5,
    'dead': -3, 'rekt': -4, 'ngmi': -3, 'sell': -2, 'selling': -2,
    'exit': -2, 'bleeding': -3, 'bleed': -3, 'overvalued': -3,
    'bubble': -3, 'correction': -2, 'bagholders': -3, 'honeypot': -5,
    'fake': -4, 'fraud': -5, 'avoid': -3, 'red': -2, 'warning': -3,
    'danger': -4, 'downtrend': -3, 'falling': -2, 'loss': -2
}

# Bullish patterns (regex)
BULLISH_PATTERNS = [
    r'\b(easy|ez)\s*(100|1000|10)x\b',
    r'going\s+to\s+(the\s+)?moon',
    r'next\s+(100|1000)x',
    r"don'?t\s+miss",
    r'early\s+(on|entry|bird)',
    r'buy\s+(the\s+)?dip',
    r'load(ing)?\s+up',
    r'huge\s+(potential|gains)',
    r'about\s+to\s+(explode|pump|moon)',
    r'sleeping\s+giant',
    r'hidden\s+gem',
    r'still\s+(early|undervalued)',
]

# Bearish patterns (regex)
BEARISH_PATTERNS = [
    r'get\s+out(\s+now)?',
    r'stay\s+away',
    r'obvious\s+(scam|rug)',
    r"don'?t\s+buy",
    r'about\s+to\s+(dump|crash|rug)',
    r'team\s+(dumping|selling)',
    r'dev\s+(abandoned|rugged)',
    r'no\s+liquidity',
    r'red\s+flag',
    r'ponzi\s+scheme',
]

# Known token tickers/symbols
KNOWN_TOKENS = {
    'BTC', 'ETH', 'SOL', 'BNB', 'XRP', 'ADA', 'DOGE', 'SHIB', 'AVAX',
    'DOT', 'MATIC', 'LINK', 'UNI', 'ATOM', 'LTC', 'BCH', 'NEAR', 'APT',
    'ARB', 'OP', 'SUI', 'SEI', 'TIA', 'INJ', 'FTM', 'MANA', 'SAND',
    'APE', 'PEPE', 'FLOKI', 'BONK', 'WIF', 'BOME', 'SLERF', 'BRETT',
    'MEW', 'POPCAT', 'TURBO', 'WOJAK', 'LADYS', 'GALA', 'AXS', 'IMX',
    'RENDER', 'FET', 'AGIX', 'OCEAN', 'GRT', 'FIL', 'AR', 'THETA',
    'HNT', 'ROSE', 'ALGO', 'VET', 'HBAR', 'ICP', 'EGLD', 'XTZ', 'EOS',
    'AAVE', 'MKR', 'SNX', 'COMP', 'CRV', 'LDO', 'RPL', 'GMX', 'PENDLE'
}

# Reddit crypto subreddits
CRYPTO_SUBREDDITS = [
    'CryptoMoonShots',
    'altcoin', 
    'SatoshiStreetBets',
    'CryptoMarkets',
    'smallcapcoins',
    'CryptoCurrency',
    'defi',
    'memecoin',
    'solana',
    'ethtrader',
]


@dataclass
class SocialPost:
    """Represents a social media post"""
    id: str
    source: str
    author: str
    title: str
    content: str
    url: str
    score: int  # upvotes/likes
    comments: int
    created_at: datetime
    subreddit: Optional[str] = None


@dataclass
class TokenMention:
    """Token mention with context"""
    token: str
    count: int
    avg_sentiment: float
    posts: List[SocialPost]


class SentimentAnalyzer:
    """Analyzes sentiment of crypto-related text"""
    
    @staticmethod
    def analyze(text: str) -> Tuple[float, str]:
        """
        Analyze sentiment of text.
        Returns (score, label) where score is -1 to 1 and label is 'bullish'/'bearish'/'neutral'
        """
        if not text:
            return 0.0, 'neutral'
        
        text_lower = text.lower()
        words = re.findall(r'\b\w+\b', text_lower)
        
        score = 0
        word_count = 0
        
        # Word-based scoring
        for word in words:
            if word in BULLISH_WORDS:
                score += BULLISH_WORDS[word]
                word_count += 1
            elif word in BEARISH_WORDS:
                score += BEARISH_WORDS[word]
                word_count += 1
        
        # Pattern matching (bonus)
        for pattern in BULLISH_PATTERNS:
            if re.search(pattern, text_lower):
                score += 2
                word_count += 1
        
        for pattern in BEARISH_PATTERNS:
            if re.search(pattern, text_lower):
                score -= 2
                word_count += 1
        
        # Normalize to -1 to 1 range
        if word_count > 0:
            normalized = max(-1, min(1, score / (word_count * 3)))
        else:
            normalized = 0.0
        
        # Determine label
        if normalized > 0.2:
            label = 'bullish'
        elif normalized < -0.2:
            label = 'bearish'
        else:
            label = 'neutral'
        
        return round(normalized, 3), label


class TokenExtractor:
    """Extracts crypto token mentions from text"""
    
    # Pattern for potential tickers: $XXX or XXX (3-5 uppercase letters)
    TICKER_PATTERN = re.compile(r'\$([A-Z]{2,6})\b|\b([A-Z]{3,5})\b')
    
    @classmethod
    def extract(cls, text: str) -> List[str]:
        """Extract token symbols from text"""
        if not text:
            return []
        
        tokens = set()
        
        # Find all potential tickers
        matches = cls.TICKER_PATTERN.findall(text.upper())
        for match in matches:
            ticker = match[0] or match[1]  # $XXX or XXX
            if ticker and len(ticker) >= 2:
                # Filter out common English words that look like tickers
                if ticker not in {'THE', 'AND', 'FOR', 'NOT', 'YOU', 'ALL', 'CAN', 
                                  'HER', 'WAS', 'ONE', 'OUR', 'OUT', 'DAY', 'GET',
                                  'HAS', 'HIM', 'HIS', 'HOW', 'ITS', 'LET', 'MAY',
                                  'NEW', 'NOW', 'OLD', 'SEE', 'TWO', 'WAY', 'WHO',
                                  'BOY', 'DID', 'ANY', 'JUST', 'COIN', 'HOLD', 'PUMP',
                                  'MOON', 'BULL', 'BEAR', 'SELL', 'FROM', 'WILL',
                                  'THIS', 'THAT', 'WITH', 'HAVE', 'BEEN', 'THEY'}:
                    # Prioritize known tokens
                    if ticker in KNOWN_TOKENS:
                        tokens.add(ticker)
                    elif ticker.startswith('$'):
                        tokens.add(ticker[1:])
        
        # Also check for explicit $token mentions in original case
        dollar_mentions = re.findall(r'\$([A-Za-z]{2,10})\b', text)
        for mention in dollar_mentions:
            ticker = mention.upper()
            if ticker not in {'THE', 'AND', 'FOR', 'NOT', 'YOU'}:
                tokens.add(ticker)
        
        return list(tokens)


class RedditScraper:
    """Scrapes Reddit for crypto discussions using public JSON API"""
    
    BASE_URL = 'https://www.reddit.com'
    USER_AGENT = 'CryptoSmallCapTrader/1.0 (Educational/Research)'
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': self.USER_AGENT,
            'Accept': 'application/json',
        })
        self.last_request = 0
        self.min_interval = 2.0  # Reddit rate limit: ~1 req/2sec
        self._available = None
    
    def _rate_limit(self):
        """Respect Reddit's rate limits"""
        elapsed = time.time() - self.last_request
        if elapsed < self.min_interval:
            time.sleep(self.min_interval - elapsed)
        self.last_request = time.time()
    
    def is_available(self) -> bool:
        """Check if Reddit API is accessible"""
        if self._available is not None:
            return self._available
        
        try:
            self._rate_limit()
            response = self.session.get(
                f'{self.BASE_URL}/r/cryptocurrency.json',
                params={'limit': 1},
                timeout=10
            )
            self._available = response.status_code == 200
        except Exception as e:
            logger.warning(f"Reddit check failed: {e}")
            self._available = False
        
        return self._available
    
    def fetch_subreddit(self, subreddit: str, sort: str = 'hot', 
                        limit: int = 25) -> List[SocialPost]:
        """Fetch posts from a subreddit"""
        if not self.is_available():
            return []
        
        self._rate_limit()
        
        try:
            response = self.session.get(
                f'{self.BASE_URL}/r/{subreddit}/{sort}.json',
                params={'limit': limit},
                timeout=15
            )
            
            if response.status_code != 200:
                logger.warning(f"Reddit returned {response.status_code} for r/{subreddit}")
                return []
            
            data = response.json()
            posts = []
            
            for child in data.get('data', {}).get('children', []):
                post_data = child.get('data', {})
                
                posts.append(SocialPost(
                    id=post_data.get('id', ''),
                    source='reddit',
                    author=post_data.get('author', '[deleted]'),
                    title=post_data.get('title', ''),
                    content=post_data.get('selftext', ''),
                    url=f"https://reddit.com{post_data.get('permalink', '')}",
                    score=post_data.get('score', 0),
                    comments=post_data.get('num_comments', 0),
                    created_at=datetime.fromtimestamp(post_data.get('created_utc', 0)),
                    subreddit=subreddit
                ))
            
            return posts
            
        except Exception as e:
            logger.error(f"Error fetching r/{subreddit}: {e}")
            return []
    
    def fetch_crypto_posts(self, limit_per_sub: int = 15) -> List[SocialPost]:
        """Fetch posts from multiple crypto subreddits"""
        all_posts = []
        
        for subreddit in CRYPTO_SUBREDDITS:
            posts = self.fetch_subreddit(subreddit, limit=limit_per_sub)
            all_posts.extend(posts)
            
            if not posts:
                logger.info(f"No posts from r/{subreddit}, continuing...")
        
        return all_posts


class SocialAnalyzer:
    """Main class for analyzing social signals"""
    
    def __init__(self, db=None):
        self.reddit = RedditScraper()
        self.sentiment = SentimentAnalyzer()
        self.extractor = TokenExtractor()
        self.db = db
        self._last_fetch = None
        self._cached_posts: List[SocialPost] = []
        self._cache_duration = 300  # 5 minutes
    
    def get_status(self) -> Dict[str, Any]:
        """Get status of all social sources"""
        return {
            'reddit': {
                'connected': self.reddit.is_available(),
                'name': 'Reddit',
                'icon': '📖',
                'description': 'Crypto subreddits (public API)'
            },
            'twitter': {
                'connected': False,
                'name': 'Twitter/X',
                'icon': '🐦',
                'description': 'Requires API key configuration'
            },
            'telegram': {
                'connected': False,
                'name': 'Telegram',
                'icon': '📱',
                'description': 'Requires bot configuration'
            },
            'discord': {
                'connected': False,
                'name': 'Discord',
                'icon': '💬',
                'description': 'Requires bot configuration'
            }
        }
    
    def _should_refresh_cache(self) -> bool:
        """Check if we should refresh the cache"""
        if not self._last_fetch:
            return True
        return (datetime.now() - self._last_fetch).seconds > self._cache_duration
    
    def fetch_posts(self, force: bool = False) -> List[SocialPost]:
        """Fetch posts from all available sources"""
        if not force and not self._should_refresh_cache():
            return self._cached_posts
        
        posts = []
        
        # Reddit
        if self.reddit.is_available():
            reddit_posts = self.reddit.fetch_crypto_posts()
            posts.extend(reddit_posts)
            logger.info(f"Fetched {len(reddit_posts)} posts from Reddit")
        
        self._cached_posts = posts
        self._last_fetch = datetime.now()
        
        return posts
    
    def analyze_posts(self, posts: List[SocialPost]) -> Dict[str, TokenMention]:
        """Analyze posts and extract token mentions with sentiment"""
        token_data: Dict[str, Dict] = {}
        
        for post in posts:
            full_text = f"{post.title} {post.content}"
            tokens = self.extractor.extract(full_text)
            sentiment_score, _ = self.sentiment.analyze(full_text)
            
            for token in tokens:
                if token not in token_data:
                    token_data[token] = {
                        'count': 0,
                        'sentiment_sum': 0,
                        'posts': []
                    }
                
                token_data[token]['count'] += 1
                token_data[token]['sentiment_sum'] += sentiment_score
                token_data[token]['posts'].append(post)
        
        # Convert to TokenMention objects
        result = {}
        for token, data in token_data.items():
            avg_sentiment = data['sentiment_sum'] / data['count'] if data['count'] > 0 else 0
            result[token] = TokenMention(
                token=token,
                count=data['count'],
                avg_sentiment=round(avg_sentiment, 3),
                posts=data['posts'][:5]  # Keep top 5 posts
            )
        
        return result
    
    def calculate_hype_score(self, mention: TokenMention) -> float:
        """
        Calculate hype score based on:
        - Number of mentions
        - Engagement (upvotes, comments)
        - Sentiment strength
        """
        # Base score from mentions (log scale)
        import math
        mention_score = math.log(mention.count + 1, 2) * 10
        
        # Engagement score
        total_engagement = sum(p.score + p.comments for p in mention.posts)
        engagement_score = math.log(total_engagement + 1, 2) * 5
        
        # Sentiment modifier (absolute value - high sentiment either way = hype)
        sentiment_modifier = abs(mention.avg_sentiment) * 20
        
        # Combine and normalize to 0-100
        raw_score = mention_score + engagement_score + sentiment_modifier
        normalized = min(100, max(0, raw_score))
        
        return round(normalized, 1)


# ============ PUBLIC API FUNCTIONS ============

_analyzer: Optional[SocialAnalyzer] = None


def get_analyzer(db=None) -> SocialAnalyzer:
    """Get or create the singleton analyzer instance"""
    global _analyzer
    if _analyzer is None:
        _analyzer = SocialAnalyzer(db)
    return _analyzer


def get_trending_tokens(limit: int = 10, db=None) -> List[Dict[str, Any]]:
    """
    Get the most mentioned/trending tokens from social media.
    
    Returns list of dicts with:
    - token: symbol
    - mentions: number of mentions
    - sentiment: average sentiment (-1 to 1)
    - hype_score: calculated hype (0-100)
    - sample_posts: list of sample posts
    """
    analyzer = get_analyzer(db)
    
    # Check if any source is available
    status = analyzer.get_status()
    available_sources = [k for k, v in status.items() if v['connected']]
    
    if not available_sources:
        return []
    
    # Fetch and analyze
    posts = analyzer.fetch_posts()
    
    if not posts:
        return []
    
    mentions = analyzer.analyze_posts(posts)
    
    # Calculate hype scores and format results
    results = []
    for token, mention in mentions.items():
        hype_score = analyzer.calculate_hype_score(mention)
        
        results.append({
            'token': token,
            'mentions': mention.count,
            'sentiment': mention.avg_sentiment,
            'hype_score': hype_score,
            'sample_posts': [
                {
                    'title': p.title[:100],
                    'source': p.source,
                    'subreddit': p.subreddit,
                    'score': p.score,
                    'url': p.url
                }
                for p in mention.posts[:3]
            ]
        })
    
    # Sort by hype score and return top N
    results.sort(key=lambda x: x['hype_score'], reverse=True)
    
    # Save to DB if available
    if db:
        for r in results[:limit]:
            try:
                db.update_token_trend(
                    token=r['token'],
                    mentions_1h=r['mentions'],
                    mentions_24h=r['mentions'],  # Would need historical data for true 24h
                    avg_sentiment=r['sentiment'],
                    hype_score=r['hype_score']
                )
            except Exception as e:
                logger.error(f"Failed to save token trend: {e}")
    
    return results[:limit]


def get_sentiment(token_symbol: str, db=None) -> Dict[str, Any]:
    """
    Get sentiment analysis for a specific token.
    
    Returns dict with:
    - token: symbol
    - sentiment: score from -1 (bearish) to 1 (bullish)
    - label: 'bullish', 'bearish', or 'neutral'
    - mentions: recent mention count
    - confidence: how confident the analysis is (based on sample size)
    """
    analyzer = get_analyzer(db)
    
    # Check sources
    status = analyzer.get_status()
    available_sources = [k for k, v in status.items() if v['connected']]
    
    if not available_sources:
        return {
            'token': token_symbol.upper(),
            'sentiment': 0,
            'label': 'unknown',
            'mentions': 0,
            'confidence': 0,
            'error': 'No social sources available'
        }
    
    # Get posts and filter by token
    posts = analyzer.fetch_posts()
    token_upper = token_symbol.upper()
    
    relevant_posts = []
    total_sentiment = 0
    
    for post in posts:
        full_text = f"{post.title} {post.content}"
        tokens = analyzer.extractor.extract(full_text)
        
        if token_upper in tokens:
            sentiment, _ = analyzer.sentiment.analyze(full_text)
            relevant_posts.append(post)
            total_sentiment += sentiment
    
    if not relevant_posts:
        # Try DB fallback
        if db:
            db_data = db.get_token_sentiment(token_symbol)
            if db_data:
                return {
                    'token': token_upper,
                    'sentiment': db_data.get('avg_sentiment', 0),
                    'label': 'bullish' if db_data.get('avg_sentiment', 0) > 0.2 else 
                             'bearish' if db_data.get('avg_sentiment', 0) < -0.2 else 'neutral',
                    'mentions': db_data.get('mentions_24h', 0),
                    'confidence': 0.5,
                    'source': 'cached'
                }
        
        return {
            'token': token_upper,
            'sentiment': 0,
            'label': 'unknown',
            'mentions': 0,
            'confidence': 0,
            'error': f'No mentions found for {token_upper}'
        }
    
    avg_sentiment = total_sentiment / len(relevant_posts)
    
    # Confidence based on sample size
    confidence = min(1.0, len(relevant_posts) / 10)
    
    # Determine label
    if avg_sentiment > 0.2:
        label = 'bullish'
    elif avg_sentiment < -0.2:
        label = 'bearish'
    else:
        label = 'neutral'
    
    return {
        'token': token_upper,
        'sentiment': round(avg_sentiment, 3),
        'label': label,
        'mentions': len(relevant_posts),
        'confidence': round(confidence, 2),
        'sample_posts': [
            {'title': p.title[:80], 'url': p.url, 'score': p.score}
            for p in relevant_posts[:5]
        ]
    }


def get_recent_signals(limit: int = 20, db=None) -> List[Dict[str, Any]]:
    """
    Get recent high-quality signals (unusual activity, sentiment spikes, etc.)
    """
    analyzer = get_analyzer(db)
    
    status = analyzer.get_status()
    available_sources = [k for k, v in status.items() if v['connected']]
    
    if not available_sources:
        return []
    
    posts = analyzer.fetch_posts()
    
    if not posts:
        return []
    
    signals = []
    mentions = analyzer.analyze_posts(posts)
    
    for token, mention in mentions.items():
        hype_score = analyzer.calculate_hype_score(mention)
        
        # Only create signals for notable activity
        if hype_score >= 30 or mention.count >= 3:
            # Determine signal type
            if mention.avg_sentiment > 0.3:
                signal_type = 'buy'
                message = f"🟢 Bullish sentiment detected"
            elif mention.avg_sentiment < -0.3:
                signal_type = 'sell'
                message = f"🔴 Bearish sentiment detected"
            elif hype_score >= 50:
                signal_type = 'alert'
                message = f"🔥 High hype activity"
            else:
                signal_type = 'info'
                message = f"📊 Trending"
            
            signal = {
                'token': token,
                'type': signal_type,
                'message': message,
                'sentiment': mention.avg_sentiment,
                'hype_score': hype_score,
                'mentions': mention.count,
                'source': 'reddit',
                'created_at': datetime.now().isoformat()
            }
            signals.append(signal)
            
            # Save to DB
            if db:
                try:
                    db.add_signal(
                        token=token,
                        signal_type=signal_type,
                        source='reddit',
                        message=f"{message} ({mention.count} mentions, sentiment: {mention.avg_sentiment:.2f})",
                        sentiment_score=mention.avg_sentiment,
                        hype_score=hype_score
                    )
                except Exception as e:
                    logger.error(f"Failed to save signal: {e}")
    
    # Sort by hype score
    signals.sort(key=lambda x: x['hype_score'], reverse=True)
    
    return signals[:limit]


def get_source_status() -> Dict[str, Any]:
    """Get connection status for all social sources"""
    analyzer = get_analyzer()
    return analyzer.get_status()
