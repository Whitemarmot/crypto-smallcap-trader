"""
Telegram channel monitor for crypto sentiment analysis.
Uses Telethon for real-time message monitoring.
"""
import asyncio
import re
from datetime import datetime, timedelta
from typing import Optional, Callable, Awaitable
from collections import defaultdict
import logging

from telethon import TelegramClient, events
from telethon.tl.types import Channel, Message, User
from telethon.errors import FloodWaitError, ChannelPrivateError

from models import SocialPost, Platform, MentionVolume

logger = logging.getLogger(__name__)


# Popular crypto Telegram channels/groups
CRYPTO_CHANNELS = {
    # News & Signals
    "cryptosignalalert": "Crypto Signal Alert",
    "whale_alert_io": "Whale Alert",
    "defillama_news": "DefiLlama News",
    "CryptoPanicNews": "CryptoPanic",
    "CoinMarketCapAnnouncements": "CMC Announcements",
    
    # Trading groups
    "cryptopumpgroup": "Crypto Pump Group",
    "altcoindaily": "Altcoin Daily",
    "cryptomoonshots": "Crypto Moonshots",
    
    # Influencer channels
    "CoinsiderChannel": "Coinsider",
    "cryptobanter": "Crypto Banter",
    
    # DEX/Chain specific
    "solanafloor": "Solana Floor",
    "BaseNewTokens": "Base New Tokens",
}

# Known influencer Telegram accounts (user IDs or usernames)
TELEGRAM_INFLUENCERS = set([
    "loomdart",
    "cryptokaleo", 
    "pentosh1",
])

# Token detection patterns
TICKER_PATTERN = re.compile(r'\$([A-Z]{2,10})\b')
CONTRACT_PATTERN = re.compile(r'0x[a-fA-F0-9]{40}')
SOLANA_PATTERN = re.compile(r'[1-9A-HJ-NP-Za-km-z]{32,44}')


class TelegramMonitor:
    """
    Real-time Telegram channel monitor for crypto signals.
    Requires Telegram API credentials (api_id, api_hash).
    """
    
    def __init__(
        self,
        api_id: int,
        api_hash: str,
        session_name: str = "crypto_monitor"
    ):
        self.api_id = api_id
        self.api_hash = api_hash
        self.session_name = session_name
        self.client: Optional[TelegramClient] = None
        
        # Message storage
        self.messages: list[SocialPost] = []
        self.message_buffer_size = 10000
        
        # Volume tracking
        self.token_mentions: dict[str, list[datetime]] = defaultdict(list)
        self.channel_stats: dict[str, dict] = defaultdict(lambda: {"messages": 0, "members": 0})
        
        # Callbacks
        self.on_message: Optional[Callable[[SocialPost], Awaitable[None]]] = None
        self.on_token_mention: Optional[Callable[[str, SocialPost], Awaitable[None]]] = None
        self.on_influencer_post: Optional[Callable[[SocialPost], Awaitable[None]]] = None
        
        # Tracking tokens
        self.watched_tokens: set[str] = set()
        
    async def start(self, phone: str = None):
        """Start the Telegram client."""
        self.client = TelegramClient(
            self.session_name,
            self.api_id,
            self.api_hash
        )
        
        await self.client.start(phone=phone)
        logger.info("Telegram client started")
        
        # Register event handlers
        self.client.add_event_handler(
            self._handle_new_message,
            events.NewMessage()
        )
        
        return self
    
    async def stop(self):
        """Stop the Telegram client."""
        if self.client:
            await self.client.disconnect()
            logger.info("Telegram client stopped")
    
    async def __aenter__(self):
        await self.start()
        return self
    
    async def __aexit__(self, *args):
        await self.stop()
    
    def watch_token(self, token: str):
        """Add a token to the watch list."""
        self.watched_tokens.add(token.upper())
    
    def unwatch_token(self, token: str):
        """Remove a token from the watch list."""
        self.watched_tokens.discard(token.upper())
    
    async def join_channels(self, channel_usernames: list[str] = None):
        """Join crypto channels for monitoring."""
        channels = channel_usernames or list(CRYPTO_CHANNELS.keys())
        joined = []
        
        for username in channels:
            try:
                entity = await self.client.get_entity(username)
                if isinstance(entity, Channel):
                    # Already a member or public channel
                    self.channel_stats[username]["members"] = getattr(
                        entity, 'participants_count', 0
                    )
                    joined.append(username)
                    logger.info(f"Monitoring channel: @{username}")
            except ChannelPrivateError:
                logger.warning(f"Cannot access private channel: @{username}")
            except FloodWaitError as e:
                logger.warning(f"Flood wait: {e.seconds}s")
                await asyncio.sleep(e.seconds)
            except Exception as e:
                logger.error(f"Error joining @{username}: {e}")
        
        return joined
    
    async def _handle_new_message(self, event: events.NewMessage.Event):
        """Handle incoming messages from monitored channels."""
        message: Message = event.message
        
        # Skip empty messages
        if not message.text:
            return
        
        # Get sender info
        try:
            sender = await event.get_sender()
            chat = await event.get_chat()
        except Exception as e:
            logger.debug(f"Could not get sender/chat: {e}")
            return
        
        # Determine author name
        if isinstance(sender, User):
            author = sender.username or f"user_{sender.id}"
            is_influencer = author.lower() in TELEGRAM_INFLUENCERS
        else:
            author = getattr(chat, 'username', None) or f"channel_{chat.id}"
            is_influencer = False
        
        # Create post object
        post = SocialPost(
            platform=Platform.TELEGRAM,
            content=message.text,
            author=author,
            timestamp=message.date.replace(tzinfo=None),
            url=f"https://t.me/{author}/{message.id}" if author else None,
            views=message.views or 0,
            is_influencer=is_influencer
        )
        
        # Store message
        self._store_message(post)
        
        # Update channel stats
        chat_username = getattr(chat, 'username', str(chat.id))
        self.channel_stats[chat_username]["messages"] += 1
        
        # Trigger callbacks
        if self.on_message:
            asyncio.create_task(self.on_message(post))
        
        if is_influencer and self.on_influencer_post:
            asyncio.create_task(self.on_influencer_post(post))
        
        # Extract and track token mentions
        tokens = self._extract_tokens(message.text)
        for token in tokens:
            self.token_mentions[token].append(datetime.utcnow())
            
            if token in self.watched_tokens and self.on_token_mention:
                asyncio.create_task(self.on_token_mention(token, post))
    
    def _store_message(self, post: SocialPost):
        """Store message with buffer management."""
        self.messages.append(post)
        
        # Trim buffer if needed
        if len(self.messages) > self.message_buffer_size:
            self.messages = self.messages[-self.message_buffer_size // 2:]
    
    def _extract_tokens(self, text: str) -> list[str]:
        """Extract crypto token symbols from text."""
        tokens = set()
        
        # Cashtags ($TOKEN)
        for match in TICKER_PATTERN.finditer(text.upper()):
            token = match.group(1)
            if len(token) >= 2 and token not in {'USD', 'EUR', 'GBP'}:
                tokens.add(token)
        
        return list(tokens)
    
    def _extract_contracts(self, text: str) -> list[tuple[str, str]]:
        """Extract contract addresses from text."""
        contracts = []
        
        # Ethereum/EVM addresses
        for match in CONTRACT_PATTERN.finditer(text):
            contracts.append(("evm", match.group(0)))
        
        # Solana addresses
        for match in SOLANA_PATTERN.finditer(text):
            addr = match.group(0)
            # Basic validation - Solana addresses don't have 0/O/I/l
            if not any(c in addr for c in '0OIl'):
                contracts.append(("solana", addr))
        
        return contracts
    
    async def get_channel_messages(
        self,
        channel: str,
        limit: int = 100,
        since_hours: int = 24
    ) -> list[SocialPost]:
        """Fetch historical messages from a channel."""
        posts = []
        since = datetime.utcnow() - timedelta(hours=since_hours)
        
        try:
            entity = await self.client.get_entity(channel)
            
            async for message in self.client.iter_messages(
                entity, 
                limit=limit,
                offset_date=datetime.utcnow()
            ):
                if not message.text:
                    continue
                
                if message.date.replace(tzinfo=None) < since:
                    break
                
                post = SocialPost(
                    platform=Platform.TELEGRAM,
                    content=message.text,
                    author=channel,
                    timestamp=message.date.replace(tzinfo=None),
                    url=f"https://t.me/{channel}/{message.id}",
                    views=message.views or 0
                )
                posts.append(post)
                
        except Exception as e:
            logger.error(f"Error fetching from @{channel}: {e}")
        
        return posts
    
    async def search_token_mentions(
        self,
        token: str,
        channels: list[str] = None,
        since_hours: int = 24,
        limit_per_channel: int = 100
    ) -> list[SocialPost]:
        """Search for token mentions across channels."""
        channels = channels or list(CRYPTO_CHANNELS.keys())
        all_posts = []
        token_upper = token.upper()
        
        for channel in channels:
            posts = await self.get_channel_messages(
                channel,
                limit=limit_per_channel,
                since_hours=since_hours
            )
            
            # Filter for token mentions
            for post in posts:
                if f"${token_upper}" in post.content.upper() or \
                   f"#{token_upper}" in post.content.upper() or \
                   token_upper in post.content.upper().split():
                    all_posts.append(post)
            
            # Small delay between channels
            await asyncio.sleep(0.5)
        
        # Sort by timestamp
        all_posts.sort(key=lambda p: p.timestamp, reverse=True)
        return all_posts
    
    def get_mention_volume(
        self,
        token: str,
        window_minutes: int = 60
    ) -> MentionVolume:
        """Get mention volume for a token from stored data."""
        token_upper = token.upper()
        now = datetime.utcnow()
        window_start = now - timedelta(minutes=window_minutes)
        
        # Count mentions in window
        mentions = self.token_mentions.get(token_upper, [])
        recent_mentions = [m for m in mentions if m >= window_start]
        
        # Count from stored messages
        relevant_posts = [
            p for p in self.messages
            if p.timestamp >= window_start and 
            (f"${token_upper}" in p.content.upper() or token_upper in p.content.upper())
        ]
        
        unique_authors = len(set(p.author for p in relevant_posts))
        influencer_mentions = sum(1 for p in relevant_posts if p.is_influencer)
        
        return MentionVolume(
            token=token_upper,
            platform=Platform.TELEGRAM,
            count=max(len(recent_mentions), len(relevant_posts)),
            window_minutes=window_minutes,
            start_time=window_start,
            end_time=now,
            unique_authors=unique_authors,
            influencer_mentions=influencer_mentions
        )
    
    def get_trending_tokens(
        self,
        window_minutes: int = 60,
        min_mentions: int = 5
    ) -> list[tuple[str, int]]:
        """Get currently trending tokens based on mention count."""
        now = datetime.utcnow()
        window_start = now - timedelta(minutes=window_minutes)
        
        # Count mentions per token
        token_counts = defaultdict(int)
        
        for token, timestamps in self.token_mentions.items():
            count = sum(1 for ts in timestamps if ts >= window_start)
            if count >= min_mentions:
                token_counts[token] = count
        
        # Sort by count
        sorted_tokens = sorted(
            token_counts.items(),
            key=lambda x: x[1],
            reverse=True
        )
        
        return sorted_tokens[:20]
    
    async def run_forever(self):
        """Run the monitor indefinitely."""
        logger.info("Starting Telegram monitor...")
        await self.client.run_until_disconnected()


class TelegramAggregator:
    """
    Aggregator for Telegram data without real-time monitoring.
    Uses public channel scraping.
    """
    
    def __init__(self, api_id: int = None, api_hash: str = None):
        self.api_id = api_id
        self.api_hash = api_hash
        self._monitor: Optional[TelegramMonitor] = None
    
    async def _get_monitor(self) -> Optional[TelegramMonitor]:
        """Get or create monitor instance."""
        if not self.api_id or not self.api_hash:
            logger.warning("Telegram API credentials not configured")
            return None
        
        if not self._monitor:
            self._monitor = TelegramMonitor(self.api_id, self.api_hash)
            await self._monitor.start()
        
        return self._monitor
    
    async def search_token(
        self,
        token: str,
        max_results: int = 100,
        since_hours: int = 24
    ) -> list[SocialPost]:
        """Search for token mentions."""
        monitor = await self._get_monitor()
        if not monitor:
            return []
        
        posts = await monitor.search_token_mentions(
            token,
            since_hours=since_hours,
            limit_per_channel=max_results // len(CRYPTO_CHANNELS)
        )
        
        return posts[:max_results]
    
    async def get_mention_volume(
        self,
        token: str,
        window_minutes: int = 60
    ) -> MentionVolume:
        """Get mention volume for a token."""
        monitor = await self._get_monitor()
        if not monitor:
            return MentionVolume(
                token=token.upper(),
                platform=Platform.TELEGRAM,
                count=0,
                window_minutes=window_minutes,
                start_time=datetime.utcnow() - timedelta(minutes=window_minutes),
                end_time=datetime.utcnow()
            )
        
        # Fetch recent data first
        await monitor.search_token_mentions(token, since_hours=window_minutes / 60 + 1)
        
        return monitor.get_mention_volume(token, window_minutes)
    
    async def close(self):
        """Close the monitor."""
        if self._monitor:
            await self._monitor.stop()


# Example callback functions
async def on_new_message(post: SocialPost):
    """Example callback for new messages."""
    print(f"[{post.timestamp}] @{post.author}: {post.content[:100]}...")


async def on_token_alert(token: str, post: SocialPost):
    """Example callback for token mentions."""
    print(f"🚨 {token} mentioned by @{post.author}")
    print(f"   {post.content[:150]}...")


async def main():
    """Example usage - requires API credentials."""
    import os
    
    api_id = os.getenv("TELEGRAM_API_ID")
    api_hash = os.getenv("TELEGRAM_API_HASH")
    
    if not api_id or not api_hash:
        print("Set TELEGRAM_API_ID and TELEGRAM_API_HASH environment variables")
        print("Get them from https://my.telegram.org/apps")
        return
    
    monitor = TelegramMonitor(int(api_id), api_hash)
    
    async with monitor:
        # Set callbacks
        monitor.on_message = on_new_message
        monitor.on_token_mention = on_token_alert
        
        # Watch specific tokens
        monitor.watch_token("PEPE")
        monitor.watch_token("WIF")
        monitor.watch_token("BONK")
        
        # Join channels
        await monitor.join_channels()
        
        print("Monitoring Telegram channels... Press Ctrl+C to stop")
        
        # Run for 5 minutes as demo
        try:
            await asyncio.sleep(300)
        except KeyboardInterrupt:
            pass
        
        # Show trending tokens
        trending = monitor.get_trending_tokens(window_minutes=5)
        print("\nTrending tokens:")
        for token, count in trending:
            print(f"  ${token}: {count} mentions")


if __name__ == "__main__":
    asyncio.run(main())
