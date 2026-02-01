"""
Twitter/X scraper for crypto sentiment analysis.
Uses snscrape and Nitter instances (no official API needed).
"""
import asyncio
import aiohttp
import re
import random
from datetime import datetime, timedelta
from typing import Optional, AsyncGenerator
from bs4 import BeautifulSoup
import logging

from models import SocialPost, Platform, MentionVolume

logger = logging.getLogger(__name__)


# Nitter instances (public, may change)
NITTER_INSTANCES = [
    "https://nitter.privacydev.net",
    "https://nitter.poast.org",
    "https://nitter.projectsegfau.lt",
    "https://nitter.1d4.us",
    "https://nitter.kavin.rocks",
]

# Known crypto influencers (follower counts approximate)
CRYPTO_INFLUENCERS = {
    "elonmusk": 150_000_000,
    "VitalikButerin": 5_000_000,
    "caborhino": 2_500_000,
    "CryptoCapo_": 800_000,
    "loomdart": 700_000,
    "Pentosh1": 650_000,
    "CryptoCred": 400_000,
    "AltcoinGordon": 350_000,
    "CryptoKaleo": 600_000,
    "inversebrah": 500_000,
    "blknoiz06": 450_000,
    "GCRClassic": 400_000,
    "CryptoWizardd": 350_000,
    "ColdBloodShill": 300_000,
    "Trader_XO": 280_000,
}

# Crypto-specific patterns to detect tokens
TICKER_PATTERN = re.compile(r'\$([A-Z]{2,10})\b')
CASHTAG_PATTERN = re.compile(r'(?:^|\s)\$([A-Za-z]{2,10})(?:\s|$|[.,!?])')


class NitterScraper:
    """Scrape Twitter via Nitter instances."""
    
    def __init__(self, instances: list[str] = None):
        self.instances = instances or NITTER_INSTANCES
        self.current_instance_idx = 0
        self.session: Optional[aiohttp.ClientSession] = None
        self.request_count = 0
        self.rate_limit_delay = 2.0  # seconds between requests
        
    async def __aenter__(self):
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30),
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
        )
        return self
    
    async def __aexit__(self, *args):
        if self.session:
            await self.session.close()
    
    def _get_instance(self) -> str:
        """Get current Nitter instance with rotation."""
        return self.instances[self.current_instance_idx]
    
    def _rotate_instance(self):
        """Rotate to next Nitter instance."""
        self.current_instance_idx = (self.current_instance_idx + 1) % len(self.instances)
        logger.info(f"Rotated to Nitter instance: {self._get_instance()}")
    
    async def _fetch_page(self, url: str, retries: int = 3) -> Optional[str]:
        """Fetch page with retry logic and instance rotation."""
        for attempt in range(retries):
            try:
                # Rate limiting
                await asyncio.sleep(self.rate_limit_delay + random.uniform(0, 1))
                self.request_count += 1
                
                async with self.session.get(url) as response:
                    if response.status == 200:
                        return await response.text()
                    elif response.status == 429:  # Rate limited
                        logger.warning(f"Rate limited on {self._get_instance()}")
                        self._rotate_instance()
                        await asyncio.sleep(5)
                    else:
                        logger.warning(f"HTTP {response.status} for {url}")
                        
            except Exception as e:
                logger.error(f"Error fetching {url}: {e}")
                self._rotate_instance()
                
        return None
    
    def _parse_tweet(self, tweet_elem, base_url: str) -> Optional[SocialPost]:
        """Parse a tweet element from Nitter HTML."""
        try:
            # Extract content
            content_elem = tweet_elem.select_one('.tweet-content')
            if not content_elem:
                return None
            content = content_elem.get_text(strip=True)
            
            # Extract author
            author_elem = tweet_elem.select_one('.username')
            author = author_elem.get_text(strip=True).lstrip('@') if author_elem else "unknown"
            
            # Extract timestamp
            time_elem = tweet_elem.select_one('.tweet-date a')
            if time_elem and time_elem.get('title'):
                try:
                    timestamp = datetime.strptime(
                        time_elem['title'], 
                        "%b %d, %Y · %I:%M %p %Z"
                    )
                except ValueError:
                    timestamp = datetime.utcnow()
            else:
                timestamp = datetime.utcnow()
            
            # Extract stats
            stats = tweet_elem.select('.tweet-stat')
            likes = retweets = replies = 0
            for stat in stats:
                text = stat.get_text(strip=True).lower()
                value = self._parse_stat_value(stat)
                if 'like' in text or 'fav' in text:
                    likes = value
                elif 'retweet' in text or 'rt' in text:
                    retweets = value
                elif 'repl' in text or 'comment' in text:
                    replies = value
            
            # Extract URL
            link_elem = tweet_elem.select_one('.tweet-link')
            url = None
            if link_elem and link_elem.get('href'):
                url = f"https://twitter.com{link_elem['href'].replace('/nitter', '')}"
            
            # Check if influencer
            author_lower = author.lower()
            is_influencer = author_lower in [k.lower() for k in CRYPTO_INFLUENCERS.keys()]
            follower_count = CRYPTO_INFLUENCERS.get(author, 0)
            
            return SocialPost(
                platform=Platform.TWITTER,
                content=content,
                author=author,
                timestamp=timestamp,
                url=url,
                likes=likes,
                retweets=retweets,
                replies=replies,
                is_influencer=is_influencer,
                follower_count=follower_count
            )
            
        except Exception as e:
            logger.error(f"Error parsing tweet: {e}")
            return None
    
    def _parse_stat_value(self, elem) -> int:
        """Parse stat value (handles K, M suffixes)."""
        try:
            text = elem.get_text(strip=True)
            # Extract number
            match = re.search(r'([\d,.]+)([KkMm])?', text)
            if not match:
                return 0
            
            value = float(match.group(1).replace(',', ''))
            suffix = match.group(2)
            
            if suffix and suffix.upper() == 'K':
                value *= 1000
            elif suffix and suffix.upper() == 'M':
                value *= 1_000_000
            
            return int(value)
        except:
            return 0
    
    async def search_token(
        self,
        token: str,
        max_results: int = 100,
        since_hours: int = 24
    ) -> AsyncGenerator[SocialPost, None]:
        """Search for tweets mentioning a crypto token."""
        since_date = datetime.utcnow() - timedelta(hours=since_hours)
        
        # Build search queries
        queries = [
            f"${token}",  # Cashtag
            f"#{token}",  # Hashtag
            f"{token} crypto",
            f"{token} moon",
            f"{token} pump",
        ]
        
        seen_ids = set()
        
        for query in queries:
            base_url = self._get_instance()
            search_url = f"{base_url}/search?f=tweets&q={query}"
            
            html = await self._fetch_page(search_url)
            if not html:
                continue
            
            soup = BeautifulSoup(html, 'html.parser')
            tweets = soup.select('.timeline-item')
            
            for tweet_elem in tweets:
                post = self._parse_tweet(tweet_elem, base_url)
                if post and post.post_id not in seen_ids:
                    if post.timestamp >= since_date:
                        seen_ids.add(post.post_id)
                        yield post
                        
                        if len(seen_ids) >= max_results:
                            return
    
    async def get_user_tweets(
        self,
        username: str,
        max_results: int = 20
    ) -> AsyncGenerator[SocialPost, None]:
        """Get recent tweets from a specific user."""
        base_url = self._get_instance()
        user_url = f"{base_url}/{username}"
        
        html = await self._fetch_page(user_url)
        if not html:
            return
        
        soup = BeautifulSoup(html, 'html.parser')
        tweets = soup.select('.timeline-item')
        
        count = 0
        for tweet_elem in tweets:
            if count >= max_results:
                break
            
            post = self._parse_tweet(tweet_elem, base_url)
            if post:
                yield post
                count += 1
    
    async def monitor_influencers(
        self,
        tokens: list[str]
    ) -> AsyncGenerator[SocialPost, None]:
        """Monitor influencer accounts for token mentions."""
        tokens_lower = [t.lower() for t in tokens]
        
        for influencer in CRYPTO_INFLUENCERS.keys():
            async for post in self.get_user_tweets(influencer, max_results=10):
                # Check if post mentions any of our tokens
                content_lower = post.content.lower()
                for token in tokens_lower:
                    if token in content_lower or f"${token}" in content_lower:
                        yield post
                        break


class SnscrapeWrapper:
    """
    Wrapper for snscrape library (requires snscrape installed).
    Fallback when Nitter instances are unavailable.
    """
    
    def __init__(self):
        self._snscrape_available = self._check_snscrape()
    
    def _check_snscrape(self) -> bool:
        """Check if snscrape is available."""
        try:
            import snscrape.modules.twitter as sntwitter
            return True
        except ImportError:
            logger.warning("snscrape not installed. Using Nitter only.")
            return False
    
    async def search_token(
        self,
        token: str,
        max_results: int = 100,
        since_hours: int = 24
    ) -> AsyncGenerator[SocialPost, None]:
        """Search using snscrape."""
        if not self._snscrape_available:
            return
        
        import snscrape.modules.twitter as sntwitter
        
        since_date = datetime.utcnow() - timedelta(hours=since_hours)
        query = f"${token} OR #{token} since:{since_date.strftime('%Y-%m-%d')}"
        
        count = 0
        # Run in executor to avoid blocking
        loop = asyncio.get_event_loop()
        
        def _scrape():
            results = []
            scraper = sntwitter.TwitterSearchScraper(query)
            for tweet in scraper.get_items():
                if count >= max_results:
                    break
                results.append(tweet)
            return results
        
        tweets = await loop.run_in_executor(None, _scrape)
        
        for tweet in tweets:
            author = tweet.user.username
            is_influencer = author.lower() in [k.lower() for k in CRYPTO_INFLUENCERS.keys()]
            
            yield SocialPost(
                platform=Platform.TWITTER,
                content=tweet.rawContent,
                author=author,
                timestamp=tweet.date,
                url=tweet.url,
                likes=tweet.likeCount or 0,
                retweets=tweet.retweetCount or 0,
                replies=tweet.replyCount or 0,
                views=tweet.viewCount or 0,
                is_influencer=is_influencer,
                follower_count=tweet.user.followersCount or 0
            )


class TwitterAggregator:
    """
    Aggregate Twitter data from multiple sources.
    Combines Nitter scraping and snscrape.
    """
    
    def __init__(self):
        self.nitter = NitterScraper()
        self.snscrape = SnscrapeWrapper()
        self.cache: dict[str, list[SocialPost]] = {}
        self.cache_ttl = 300  # 5 minutes
        self.cache_timestamps: dict[str, datetime] = {}
    
    async def search_token(
        self,
        token: str,
        max_results: int = 100,
        since_hours: int = 24,
        use_cache: bool = True
    ) -> list[SocialPost]:
        """Search for token mentions across all sources."""
        cache_key = f"{token}:{since_hours}"
        
        # Check cache
        if use_cache and cache_key in self.cache:
            cache_time = self.cache_timestamps.get(cache_key)
            if cache_time and (datetime.utcnow() - cache_time).seconds < self.cache_ttl:
                return self.cache[cache_key][:max_results]
        
        posts = []
        seen_ids = set()
        
        # Try Nitter first
        async with self.nitter:
            async for post in self.nitter.search_token(token, max_results, since_hours):
                if post.post_id not in seen_ids:
                    seen_ids.add(post.post_id)
                    posts.append(post)
        
        # Supplement with snscrape if needed
        if len(posts) < max_results // 2:
            async for post in self.snscrape.search_token(
                token, 
                max_results - len(posts), 
                since_hours
            ):
                if post.post_id not in seen_ids:
                    seen_ids.add(post.post_id)
                    posts.append(post)
        
        # Sort by engagement
        posts.sort(key=lambda p: p.engagement_score, reverse=True)
        
        # Cache results
        self.cache[cache_key] = posts
        self.cache_timestamps[cache_key] = datetime.utcnow()
        
        return posts[:max_results]
    
    async def get_mention_volume(
        self,
        token: str,
        window_minutes: int = 60
    ) -> MentionVolume:
        """Calculate mention volume for a token."""
        posts = await self.search_token(
            token,
            max_results=500,
            since_hours=window_minutes / 60 + 1,
            use_cache=False
        )
        
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(minutes=window_minutes)
        
        # Filter to window
        window_posts = [
            p for p in posts 
            if p.timestamp >= start_time
        ]
        
        unique_authors = len(set(p.author for p in window_posts))
        influencer_mentions = sum(1 for p in window_posts if p.is_influencer)
        
        return MentionVolume(
            token=token,
            platform=Platform.TWITTER,
            count=len(window_posts),
            window_minutes=window_minutes,
            start_time=start_time,
            end_time=end_time,
            unique_authors=unique_authors,
            influencer_mentions=influencer_mentions
        )
    
    async def detect_trending(
        self,
        tokens: list[str],
        threshold_multiplier: float = 2.0
    ) -> list[tuple[str, float]]:
        """Detect trending tokens based on velocity increase."""
        results = []
        
        for token in tokens:
            # Get current and historical volumes
            current = await self.get_mention_volume(token, window_minutes=60)
            historical = await self.get_mention_volume(token, window_minutes=360)
            
            # Calculate velocity ratio
            current_velocity = current.velocity
            baseline_velocity = historical.velocity / 6  # Normalize to hourly
            
            if baseline_velocity > 0:
                ratio = current_velocity / baseline_velocity
                if ratio >= threshold_multiplier:
                    results.append((token, ratio))
        
        # Sort by ratio descending
        results.sort(key=lambda x: x[1], reverse=True)
        return results


# Utility functions
def extract_tokens_from_text(text: str) -> list[str]:
    """Extract potential crypto tokens from text."""
    tokens = set()
    
    # Cashtags
    for match in CASHTAG_PATTERN.finditer(text):
        tokens.add(match.group(1).upper())
    
    # Tickers
    for match in TICKER_PATTERN.finditer(text):
        tokens.add(match.group(1).upper())
    
    # Filter out common false positives
    false_positives = {'USD', 'EUR', 'GBP', 'THE', 'AND', 'FOR', 'NOT', 'ALL'}
    tokens = {t for t in tokens if t not in false_positives and len(t) >= 2}
    
    return list(tokens)


async def main():
    """Example usage."""
    aggregator = TwitterAggregator()
    
    # Search for a token
    print("Searching for $PEPE mentions...")
    posts = await aggregator.search_token("PEPE", max_results=20)
    
    for post in posts[:5]:
        print(f"\n[@{post.author}] {post.content[:100]}...")
        print(f"  Engagement: {post.engagement_score:.0f} | Influencer: {post.is_influencer}")
    
    # Get volume
    print("\n\nCalculating mention volume...")
    volume = await aggregator.get_mention_volume("PEPE", window_minutes=60)
    print(f"Volume: {volume.count} mentions in {volume.window_minutes}min")
    print(f"Velocity: {volume.velocity:.2f}")


if __name__ == "__main__":
    asyncio.run(main())
