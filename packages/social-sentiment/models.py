"""
Data models for social sentiment analysis.
"""
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional
import hashlib


class SignalType(Enum):
    """Trading signal types."""
    STRONG_BUY = "STRONG_BUY"
    BUY = "BUY"
    NEUTRAL = "NEUTRAL"
    SELL = "SELL"
    STRONG_SELL = "STRONG_SELL"


class Platform(Enum):
    """Social media platforms."""
    TWITTER = "twitter"
    TELEGRAM = "telegram"
    DISCORD = "discord"
    REDDIT = "reddit"


@dataclass
class SocialPost:
    """Represents a social media post."""
    platform: Platform
    content: str
    author: str
    timestamp: datetime
    url: Optional[str] = None
    likes: int = 0
    retweets: int = 0
    replies: int = 0
    views: int = 0
    is_influencer: bool = False
    follower_count: int = 0
    
    @property
    def post_id(self) -> str:
        """Generate unique ID for the post."""
        unique_str = f"{self.platform.value}:{self.author}:{self.timestamp.isoformat()}:{self.content[:50]}"
        return hashlib.md5(unique_str.encode()).hexdigest()
    
    @property
    def engagement_score(self) -> float:
        """Calculate engagement score."""
        # Weighted engagement
        score = (
            self.likes * 1.0 +
            self.retweets * 2.0 +
            self.replies * 1.5 +
            self.views * 0.01
        )
        # Bonus for influencers
        if self.is_influencer:
            score *= 1.5
        return score


@dataclass
class SentimentScore:
    """Sentiment analysis result for a piece of content."""
    text: str
    score: float  # -1.0 (bearish) to 1.0 (bullish)
    confidence: float  # 0.0 to 1.0
    tokens_detected: list[str] = field(default_factory=list)
    model_used: str = "finbert"
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    @property
    def label(self) -> str:
        """Human-readable sentiment label."""
        if self.score > 0.5:
            return "Very Bullish"
        elif self.score > 0.2:
            return "Bullish"
        elif self.score > -0.2:
            return "Neutral"
        elif self.score > -0.5:
            return "Bearish"
        else:
            return "Very Bearish"
    
    def to_dict(self) -> dict:
        return {
            "text": self.text[:100],
            "score": self.score,
            "confidence": self.confidence,
            "label": self.label,
            "tokens": self.tokens_detected,
            "model": self.model_used,
            "timestamp": self.timestamp.isoformat()
        }


@dataclass
class MentionVolume:
    """Tracks mention volume for a token over time."""
    token: str
    platform: Platform
    count: int
    window_minutes: int
    start_time: datetime
    end_time: datetime
    unique_authors: int = 0
    influencer_mentions: int = 0
    
    @property
    def mentions_per_minute(self) -> float:
        """Average mentions per minute."""
        return self.count / max(self.window_minutes, 1)
    
    @property
    def velocity(self) -> float:
        """Velocity score (weighted by unique authors and influencers)."""
        base_velocity = self.mentions_per_minute
        author_multiplier = min(self.unique_authors / max(self.count, 1) * 2, 1.5)
        influencer_multiplier = 1 + (self.influencer_mentions * 0.2)
        return base_velocity * author_multiplier * influencer_multiplier
    
    def to_dict(self) -> dict:
        return {
            "token": self.token,
            "platform": self.platform.value,
            "count": self.count,
            "window_minutes": self.window_minutes,
            "mentions_per_minute": self.mentions_per_minute,
            "velocity": self.velocity,
            "unique_authors": self.unique_authors,
            "influencer_mentions": self.influencer_mentions,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat()
        }


@dataclass
class ViralIndicator:
    """Detects viral propagation patterns."""
    token: str
    current_velocity: float
    baseline_velocity: float
    acceleration: float  # Rate of change
    is_viral: bool
    viral_score: float  # 0.0 to 1.0
    detected_at: datetime = field(default_factory=datetime.utcnow)
    
    @classmethod
    def calculate(
        cls,
        token: str,
        current_volume: MentionVolume,
        historical_volumes: list['MentionVolume'],
        viral_threshold: float = 3.0
    ) -> 'ViralIndicator':
        """Calculate viral indicator from volume data."""
        current_velocity = current_volume.velocity
        
        # Calculate baseline from historical data
        if historical_volumes:
            baseline_velocity = sum(v.velocity for v in historical_volumes) / len(historical_volumes)
        else:
            baseline_velocity = current_velocity * 0.5  # Assume half as baseline
        
        # Calculate acceleration (velocity change)
        if len(historical_volumes) >= 2:
            recent_velocity = historical_volumes[-1].velocity
            acceleration = (current_velocity - recent_velocity) / recent_velocity if recent_velocity > 0 else 0
        else:
            acceleration = 0
        
        # Determine if viral
        velocity_ratio = current_velocity / max(baseline_velocity, 0.001)
        is_viral = velocity_ratio >= viral_threshold
        
        # Viral score (normalized)
        viral_score = min(velocity_ratio / (viral_threshold * 2), 1.0)
        
        return cls(
            token=token,
            current_velocity=current_velocity,
            baseline_velocity=baseline_velocity,
            acceleration=acceleration,
            is_viral=is_viral,
            viral_score=viral_score
        )


@dataclass
class InfluencerActivity:
    """Tracks crypto influencer activity for a token."""
    token: str
    influencer_name: str
    platform: Platform
    post: SocialPost
    historical_accuracy: float = 0.5  # Track record 0-1
    follower_reach: int = 0
    
    @property
    def impact_score(self) -> float:
        """Calculate potential market impact."""
        reach_score = min(self.follower_reach / 1_000_000, 1.0)  # Normalize to 1M
        accuracy_weight = 0.5 + (self.historical_accuracy * 0.5)
        engagement_weight = min(self.post.engagement_score / 10000, 1.0)
        return reach_score * accuracy_weight * engagement_weight


@dataclass
class SocialSignal:
    """Combined social signal for trading decision."""
    token: str
    signal_type: SignalType
    confidence: float
    timestamp: datetime
    
    # Component scores
    sentiment_score: float
    volume_score: float
    viral_score: float
    influencer_score: float
    
    # Supporting data
    total_mentions: int
    positive_mentions: int
    negative_mentions: int
    platforms_active: list[Platform]
    top_influencers: list[str]
    
    # Risk metrics
    manipulation_risk: float  # 0-1, higher = more likely coordinated
    reliability: float  # 0-1, based on data quality
    
    def to_dict(self) -> dict:
        return {
            "token": self.token,
            "signal": self.signal_type.value,
            "confidence": round(self.confidence, 3),
            "timestamp": self.timestamp.isoformat(),
            "scores": {
                "sentiment": round(self.sentiment_score, 3),
                "volume": round(self.volume_score, 3),
                "viral": round(self.viral_score, 3),
                "influencer": round(self.influencer_score, 3)
            },
            "mentions": {
                "total": self.total_mentions,
                "positive": self.positive_mentions,
                "negative": self.negative_mentions
            },
            "platforms": [p.value for p in self.platforms_active],
            "top_influencers": self.top_influencers[:5],
            "risk": {
                "manipulation": round(self.manipulation_risk, 3),
                "reliability": round(self.reliability, 3)
            }
        }
    
    @property
    def composite_score(self) -> float:
        """Calculate weighted composite score."""
        weights = {
            "sentiment": 0.25,
            "volume": 0.20,
            "viral": 0.30,
            "influencer": 0.25
        }
        score = (
            self.sentiment_score * weights["sentiment"] +
            self.volume_score * weights["volume"] +
            self.viral_score * weights["viral"] +
            self.influencer_score * weights["influencer"]
        )
        # Adjust for manipulation risk
        return score * (1 - self.manipulation_risk * 0.5)


@dataclass
class HypeAlert:
    """Alert for potential hype/pump detection."""
    token: str
    alert_level: str  # "low", "medium", "high", "critical"
    detected_at: datetime
    signals: list[SocialSignal]
    reasons: list[str]
    estimated_time_to_peak: Optional[int] = None  # minutes
    
    def to_dict(self) -> dict:
        return {
            "token": self.token,
            "alert_level": self.alert_level,
            "detected_at": self.detected_at.isoformat(),
            "reasons": self.reasons,
            "estimated_peak_minutes": self.estimated_time_to_peak,
            "signal_count": len(self.signals)
        }
