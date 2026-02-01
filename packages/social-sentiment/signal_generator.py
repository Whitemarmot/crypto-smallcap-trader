"""
Signal generator for crypto trading based on social sentiment.
Combines multiple signals to detect hype before pump.
"""
import asyncio
from datetime import datetime, timedelta
from typing import Optional
from collections import defaultdict
from dataclasses import dataclass
import logging
import json

import numpy as np

from models import (
    SocialSignal, SignalType, SocialPost, Platform,
    MentionVolume, ViralIndicator, InfluencerActivity, HypeAlert
)
from sentiment_analyzer import CryptoSentimentAnalyzer, TokenSentimentAggregator
from twitter_scraper import TwitterAggregator
from telegram_monitor import TelegramAggregator

logger = logging.getLogger(__name__)


@dataclass
class SignalConfig:
    """Configuration for signal generation."""
    # Volume thresholds
    min_mentions_1h: int = 10
    volume_spike_multiplier: float = 3.0
    
    # Sentiment thresholds
    bullish_threshold: float = 0.3
    bearish_threshold: float = -0.3
    
    # Viral detection
    viral_velocity_threshold: float = 2.0
    viral_acceleration_threshold: float = 0.5
    
    # Influencer impact
    influencer_weight: float = 2.0
    min_influencer_followers: int = 100_000
    
    # Signal confidence
    min_confidence: float = 0.5
    
    # Manipulation detection
    manipulation_author_ratio: float = 0.3  # If >30% same authors, suspicious
    manipulation_timing_window: int = 5  # minutes - coordinated timing
    
    # Time windows
    short_window_minutes: int = 60
    medium_window_minutes: int = 360
    long_window_minutes: int = 1440


class SocialSignalGenerator:
    """
    Generates trading signals from social media data.
    Detects hype and potential pump patterns.
    """
    
    def __init__(
        self,
        config: SignalConfig = None,
        telegram_api_id: int = None,
        telegram_api_hash: str = None
    ):
        self.config = config or SignalConfig()
        
        # Initialize components
        self.sentiment_analyzer = CryptoSentimentAnalyzer()
        self.sentiment_aggregator = TokenSentimentAggregator(self.sentiment_analyzer)
        self.twitter = TwitterAggregator()
        self.telegram = TelegramAggregator(telegram_api_id, telegram_api_hash)
        
        # Historical data storage
        self.volume_history: dict[str, list[MentionVolume]] = defaultdict(list)
        self.signal_history: dict[str, list[SocialSignal]] = defaultdict(list)
        self.alerts: list[HypeAlert] = []
        
        # Track baselines
        self.baseline_volumes: dict[str, float] = {}
        
    async def collect_social_data(
        self,
        token: str,
        since_hours: int = 24
    ) -> list[SocialPost]:
        """Collect social media posts about a token."""
        all_posts = []
        
        # Collect from Twitter
        try:
            twitter_posts = await self.twitter.search_token(
                token,
                max_results=200,
                since_hours=since_hours
            )
            all_posts.extend(twitter_posts)
            logger.info(f"Collected {len(twitter_posts)} Twitter posts for ${token}")
        except Exception as e:
            logger.error(f"Twitter collection error: {e}")
        
        # Collect from Telegram
        try:
            telegram_posts = await self.telegram.search_token(
                token,
                max_results=200,
                since_hours=since_hours
            )
            all_posts.extend(telegram_posts)
            logger.info(f"Collected {len(telegram_posts)} Telegram posts for ${token}")
        except Exception as e:
            logger.error(f"Telegram collection error: {e}")
        
        # Sort by timestamp
        all_posts.sort(key=lambda p: p.timestamp, reverse=True)
        
        return all_posts
    
    async def calculate_volume_metrics(
        self,
        token: str,
        posts: list[SocialPost]
    ) -> dict:
        """Calculate volume-based metrics."""
        now = datetime.utcnow()
        
        # Short window (1h)
        short_cutoff = now - timedelta(minutes=self.config.short_window_minutes)
        short_posts = [p for p in posts if p.timestamp >= short_cutoff]
        
        # Medium window (6h)
        medium_cutoff = now - timedelta(minutes=self.config.medium_window_minutes)
        medium_posts = [p for p in posts if p.timestamp >= medium_cutoff]
        
        # Calculate volumes
        short_volume = MentionVolume(
            token=token,
            platform=Platform.TWITTER,  # Aggregate
            count=len(short_posts),
            window_minutes=self.config.short_window_minutes,
            start_time=short_cutoff,
            end_time=now,
            unique_authors=len(set(p.author for p in short_posts)),
            influencer_mentions=sum(1 for p in short_posts if p.is_influencer)
        )
        
        medium_volume = MentionVolume(
            token=token,
            platform=Platform.TWITTER,
            count=len(medium_posts),
            window_minutes=self.config.medium_window_minutes,
            start_time=medium_cutoff,
            end_time=now,
            unique_authors=len(set(p.author for p in medium_posts)),
            influencer_mentions=sum(1 for p in medium_posts if p.is_influencer)
        )
        
        # Store history
        self.volume_history[token].append(short_volume)
        if len(self.volume_history[token]) > 100:
            self.volume_history[token] = self.volume_history[token][-100:]
        
        # Calculate baseline
        if token not in self.baseline_volumes:
            self.baseline_volumes[token] = medium_volume.velocity / 6
        else:
            # Exponential moving average
            alpha = 0.1
            self.baseline_volumes[token] = (
                alpha * (medium_volume.velocity / 6) +
                (1 - alpha) * self.baseline_volumes[token]
            )
        
        # Volume score (0-1, normalized)
        baseline = self.baseline_volumes[token]
        if baseline > 0:
            volume_ratio = short_volume.velocity / baseline
            volume_score = min(volume_ratio / self.config.volume_spike_multiplier, 1.0)
        else:
            volume_score = 0.5 if short_volume.count > 0 else 0.0
        
        return {
            "short_volume": short_volume,
            "medium_volume": medium_volume,
            "baseline_velocity": baseline,
            "volume_score": volume_score,
            "is_spike": volume_ratio >= self.config.volume_spike_multiplier if baseline > 0 else False
        }
    
    async def calculate_viral_metrics(
        self,
        token: str,
        posts: list[SocialPost]
    ) -> ViralIndicator:
        """Detect viral propagation patterns."""
        history = self.volume_history.get(token, [])
        
        # Get current volume
        now = datetime.utcnow()
        short_cutoff = now - timedelta(minutes=self.config.short_window_minutes)
        short_posts = [p for p in posts if p.timestamp >= short_cutoff]
        
        current_volume = MentionVolume(
            token=token,
            platform=Platform.TWITTER,
            count=len(short_posts),
            window_minutes=self.config.short_window_minutes,
            start_time=short_cutoff,
            end_time=now,
            unique_authors=len(set(p.author for p in short_posts)),
            influencer_mentions=sum(1 for p in short_posts if p.is_influencer)
        )
        
        return ViralIndicator.calculate(
            token=token,
            current_volume=current_volume,
            historical_volumes=history[-10:],
            viral_threshold=self.config.viral_velocity_threshold
        )
    
    async def analyze_influencer_activity(
        self,
        token: str,
        posts: list[SocialPost]
    ) -> list[InfluencerActivity]:
        """Analyze influencer posts about the token."""
        influencer_posts = [p for p in posts if p.is_influencer]
        
        activities = []
        for post in influencer_posts:
            activity = InfluencerActivity(
                token=token,
                influencer_name=post.author,
                platform=post.platform,
                post=post,
                follower_reach=post.follower_count,
                historical_accuracy=0.5  # Default, would need historical tracking
            )
            activities.append(activity)
        
        return activities
    
    def detect_manipulation(
        self,
        posts: list[SocialPost]
    ) -> float:
        """
        Detect potential manipulation/coordinated activity.
        Returns risk score 0-1.
        """
        if not posts:
            return 0.0
        
        risk_factors = []
        
        # Factor 1: Author concentration
        author_counts = defaultdict(int)
        for post in posts:
            author_counts[post.author] += 1
        
        total_posts = len(posts)
        unique_authors = len(author_counts)
        
        if unique_authors > 0:
            # If few authors posting a lot
            max_posts_per_author = max(author_counts.values())
            concentration = max_posts_per_author / total_posts
            risk_factors.append(concentration)
        
        # Factor 2: Timing clustering (coordinated posting)
        if len(posts) >= 3:
            timestamps = sorted([p.timestamp for p in posts])
            intervals = [
                (timestamps[i + 1] - timestamps[i]).total_seconds()
                for i in range(len(timestamps) - 1)
            ]
            
            if intervals:
                # Low variance in intervals = coordinated
                mean_interval = np.mean(intervals)
                if mean_interval > 0:
                    cv = np.std(intervals) / mean_interval  # Coefficient of variation
                    timing_risk = max(0, 1 - cv)  # Lower CV = higher risk
                    risk_factors.append(timing_risk * 0.5)
        
        # Factor 3: Content similarity (would need text comparison)
        # Simplified: check for repeated content
        contents = [p.content[:50].lower() for p in posts]
        unique_contents = len(set(contents))
        if total_posts > 0:
            content_diversity = unique_contents / total_posts
            risk_factors.append(1 - content_diversity)
        
        # Factor 4: New account activity (if we had account age)
        # Placeholder
        
        # Combine factors
        if risk_factors:
            manipulation_risk = np.mean(risk_factors)
        else:
            manipulation_risk = 0.0
        
        return float(min(manipulation_risk, 1.0))
    
    async def generate_signal(
        self,
        token: str,
        posts: list[SocialPost] = None
    ) -> SocialSignal:
        """
        Generate a comprehensive trading signal for a token.
        """
        # Collect data if not provided
        if posts is None:
            posts = await self.collect_social_data(token)
        
        if not posts:
            # No data - neutral signal
            return SocialSignal(
                token=token,
                signal_type=SignalType.NEUTRAL,
                confidence=0.0,
                timestamp=datetime.utcnow(),
                sentiment_score=0.0,
                volume_score=0.0,
                viral_score=0.0,
                influencer_score=0.0,
                total_mentions=0,
                positive_mentions=0,
                negative_mentions=0,
                platforms_active=[],
                top_influencers=[],
                manipulation_risk=0.0,
                reliability=0.0
            )
        
        # Calculate all metrics
        volume_metrics = await self.calculate_volume_metrics(token, posts)
        viral_indicator = await self.calculate_viral_metrics(token, posts)
        influencer_activity = await self.analyze_influencer_activity(token, posts)
        
        # Sentiment analysis
        sentiment_result = await self.sentiment_aggregator.analyze_posts(token, posts)
        
        # Manipulation detection
        manipulation_risk = self.detect_manipulation(posts)
        
        # Calculate component scores (0-1)
        sentiment_score = (sentiment_result["average_sentiment"] + 1) / 2  # Normalize to 0-1
        volume_score = volume_metrics["volume_score"]
        viral_score = viral_indicator.viral_score
        
        # Influencer score
        if influencer_activity:
            influencer_score = min(
                sum(a.impact_score for a in influencer_activity) / 3,
                1.0
            )
        else:
            influencer_score = 0.0
        
        # Determine signal type
        composite = (
            sentiment_score * 0.25 +
            volume_score * 0.20 +
            viral_score * 0.30 +
            influencer_score * 0.25
        )
        
        # Adjust for manipulation
        adjusted_composite = composite * (1 - manipulation_risk * 0.5)
        
        if adjusted_composite >= 0.75:
            signal_type = SignalType.STRONG_BUY
        elif adjusted_composite >= 0.6:
            signal_type = SignalType.BUY
        elif adjusted_composite <= 0.25:
            signal_type = SignalType.STRONG_SELL
        elif adjusted_composite <= 0.4:
            signal_type = SignalType.SELL
        else:
            signal_type = SignalType.NEUTRAL
        
        # Calculate confidence
        data_points = len(posts)
        data_quality = min(data_points / 50, 1.0)  # More data = higher confidence
        platform_diversity = len(set(p.platform for p in posts)) / 2
        
        confidence = (
            data_quality * 0.4 +
            sentiment_result.get("confidence", 0.5) * 0.3 +
            platform_diversity * 0.3
        ) * (1 - manipulation_risk * 0.3)
        
        # Reliability score
        reliability = data_quality * (1 - manipulation_risk)
        
        # Count sentiment distribution
        positive = int(sentiment_result["positive_ratio"] * data_points)
        negative = int(sentiment_result["negative_ratio"] * data_points)
        
        # Get platforms and influencers
        platforms = list(set(p.platform for p in posts))
        top_influencers = [a.influencer_name for a in influencer_activity[:5]]
        
        signal = SocialSignal(
            token=token,
            signal_type=signal_type,
            confidence=float(confidence),
            timestamp=datetime.utcnow(),
            sentiment_score=float(sentiment_result["average_sentiment"]),
            volume_score=float(volume_score),
            viral_score=float(viral_score),
            influencer_score=float(influencer_score),
            total_mentions=data_points,
            positive_mentions=positive,
            negative_mentions=negative,
            platforms_active=platforms,
            top_influencers=top_influencers,
            manipulation_risk=float(manipulation_risk),
            reliability=float(reliability)
        )
        
        # Store in history
        self.signal_history[token].append(signal)
        if len(self.signal_history[token]) > 100:
            self.signal_history[token] = self.signal_history[token][-100:]
        
        return signal
    
    async def detect_hype(
        self,
        tokens: list[str],
        check_interval_minutes: int = 15
    ) -> list[HypeAlert]:
        """
        Detect hype patterns that may precede a pump.
        Returns alerts for tokens showing hype indicators.
        """
        alerts = []
        
        for token in tokens:
            try:
                signal = await self.generate_signal(token)
                
                # Check for hype indicators
                reasons = []
                alert_level = "low"
                
                # Volume spike
                if signal.volume_score >= 0.7:
                    reasons.append(f"Volume spike: {signal.volume_score:.1%} above baseline")
                    alert_level = "medium"
                
                # Viral activity
                if signal.viral_score >= 0.6:
                    reasons.append(f"Viral activity detected (score: {signal.viral_score:.2f})")
                    alert_level = "medium" if alert_level == "low" else "high"
                
                # Influencer activity
                if signal.influencer_score >= 0.5 and signal.top_influencers:
                    reasons.append(
                        f"Influencer mentions: {', '.join(signal.top_influencers[:3])}"
                    )
                    alert_level = "high" if alert_level != "low" else "medium"
                
                # Strong bullish sentiment
                if signal.sentiment_score >= 0.5:
                    reasons.append(f"Strong bullish sentiment: {signal.sentiment_score:+.2f}")
                
                # Combined hype indicators
                if signal.signal_type in [SignalType.STRONG_BUY, SignalType.BUY]:
                    if signal.viral_score >= 0.5 and signal.volume_score >= 0.5:
                        alert_level = "high"
                        
                        if signal.manipulation_risk < 0.3:
                            alert_level = "critical"
                            reasons.append("⚠️ Potential pump incoming - low manipulation risk")
                
                # Create alert if reasons found
                if reasons:
                    # Estimate time to peak (rough heuristic)
                    if alert_level == "critical":
                        time_to_peak = 30  # minutes
                    elif alert_level == "high":
                        time_to_peak = 60
                    else:
                        time_to_peak = None
                    
                    alert = HypeAlert(
                        token=token,
                        alert_level=alert_level,
                        detected_at=datetime.utcnow(),
                        signals=[signal],
                        reasons=reasons,
                        estimated_time_to_peak=time_to_peak
                    )
                    alerts.append(alert)
                    self.alerts.append(alert)
                    
                    logger.warning(
                        f"🚨 HYPE ALERT [{alert_level.upper()}] ${token}: {', '.join(reasons[:2])}"
                    )
                    
            except Exception as e:
                logger.error(f"Error detecting hype for {token}: {e}")
        
        # Sort by alert level
        level_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        alerts.sort(key=lambda a: level_order.get(a.alert_level, 4))
        
        return alerts
    
    async def run_monitoring(
        self,
        tokens: list[str],
        interval_seconds: int = 300,
        on_alert: callable = None
    ):
        """
        Continuously monitor tokens for hype signals.
        """
        logger.info(f"Starting hype monitoring for: {', '.join(tokens)}")
        
        while True:
            try:
                alerts = await self.detect_hype(tokens)
                
                for alert in alerts:
                    if on_alert:
                        await on_alert(alert)
                    else:
                        print(json.dumps(alert.to_dict(), indent=2))
                
                await asyncio.sleep(interval_seconds)
                
            except asyncio.CancelledError:
                logger.info("Monitoring stopped")
                break
            except Exception as e:
                logger.error(f"Monitoring error: {e}")
                await asyncio.sleep(60)
    
    def get_signal_summary(self, token: str) -> dict:
        """Get a summary of recent signals for a token."""
        signals = self.signal_history.get(token, [])
        
        if not signals:
            return {"token": token, "status": "no_data"}
        
        recent = signals[-10:]
        
        return {
            "token": token,
            "latest_signal": recent[-1].to_dict(),
            "signal_count": len(signals),
            "avg_sentiment": np.mean([s.sentiment_score for s in recent]),
            "avg_volume": np.mean([s.volume_score for s in recent]),
            "trend": self._calculate_trend(recent),
            "active_alerts": [
                a.to_dict() for a in self.alerts
                if a.token == token and 
                (datetime.utcnow() - a.detected_at).seconds < 3600
            ]
        }
    
    def _calculate_trend(self, signals: list[SocialSignal]) -> str:
        """Calculate signal trend."""
        if len(signals) < 3:
            return "insufficient_data"
        
        composites = [s.composite_score for s in signals]
        
        # Simple trend detection
        recent_avg = np.mean(composites[-3:])
        older_avg = np.mean(composites[:-3])
        
        change = recent_avg - older_avg
        
        if change > 0.1:
            return "bullish"
        elif change < -0.1:
            return "bearish"
        else:
            return "neutral"


async def main():
    """Example usage and demo."""
    print("=" * 60)
    print("SOCIAL SIGNAL GENERATOR - Hype Detection System")
    print("=" * 60)
    
    # Initialize generator
    generator = SocialSignalGenerator()
    
    # Demo tokens
    tokens = ["PEPE", "WIF", "BONK"]
    
    print(f"\nMonitoring tokens: {', '.join(tokens)}")
    print("-" * 60)
    
    for token in tokens:
        print(f"\n🔍 Analyzing ${token}...")
        
        # Generate signal
        signal = await generator.generate_signal(token)
        
        print(f"\n📊 Signal: {signal.signal_type.value}")
        print(f"   Confidence: {signal.confidence:.1%}")
        print(f"   Sentiment: {signal.sentiment_score:+.3f}")
        print(f"   Volume Score: {signal.volume_score:.3f}")
        print(f"   Viral Score: {signal.viral_score:.3f}")
        print(f"   Influencer Score: {signal.influencer_score:.3f}")
        print(f"   Total Mentions: {signal.total_mentions}")
        print(f"   Manipulation Risk: {signal.manipulation_risk:.1%}")
        
        if signal.top_influencers:
            print(f"   Top Influencers: {', '.join(signal.top_influencers[:3])}")
    
    # Detect hype
    print("\n" + "=" * 60)
    print("HYPE DETECTION")
    print("=" * 60)
    
    alerts = await generator.detect_hype(tokens)
    
    if alerts:
        for alert in alerts:
            print(f"\n🚨 [{alert.alert_level.upper()}] ${alert.token}")
            for reason in alert.reasons:
                print(f"   • {reason}")
            if alert.estimated_time_to_peak:
                print(f"   ⏱️ Est. time to peak: {alert.estimated_time_to_peak} min")
    else:
        print("\nNo significant hype detected.")


if __name__ == "__main__":
    asyncio.run(main())
