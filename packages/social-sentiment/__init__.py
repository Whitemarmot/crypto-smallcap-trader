"""
Social Sentiment Analysis Package for Crypto Trading

Detects hype and generates BUY/SELL signals based on:
- Twitter/X mentions via Nitter/snscrape
- Telegram channel monitoring
- Sentiment analysis (FinBERT)
- Viral propagation detection
- Influencer activity tracking

Usage:
    from social_sentiment import SocialSignalGenerator, SignalType

    generator = SocialSignalGenerator()
    signal = await generator.generate_signal("PEPE")
    
    if signal.signal_type == SignalType.STRONG_BUY:
        print(f"🚀 Strong buy signal for ${signal.token}")
"""

from models import (
    SocialPost,
    SentimentScore,
    MentionVolume,
    ViralIndicator,
    InfluencerActivity,
    SocialSignal,
    HypeAlert,
    SignalType,
    Platform,
)

from sentiment_analyzer import (
    CryptoSentimentAnalyzer,
    TokenSentimentAggregator,
)

from twitter_scraper import (
    TwitterAggregator,
    NitterScraper,
    extract_tokens_from_text,
)

from telegram_monitor import (
    TelegramMonitor,
    TelegramAggregator,
)

from signal_generator import (
    SocialSignalGenerator,
    SignalConfig,
)


__version__ = "0.1.0"
__all__ = [
    # Models
    "SocialPost",
    "SentimentScore", 
    "MentionVolume",
    "ViralIndicator",
    "InfluencerActivity",
    "SocialSignal",
    "HypeAlert",
    "SignalType",
    "Platform",
    # Analyzers
    "CryptoSentimentAnalyzer",
    "TokenSentimentAggregator",
    # Scrapers
    "TwitterAggregator",
    "NitterScraper",
    "TelegramMonitor",
    "TelegramAggregator",
    # Signal Generator
    "SocialSignalGenerator",
    "SignalConfig",
    # Utilities
    "extract_tokens_from_text",
]
