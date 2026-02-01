"""
Token Scoring System
Combines sentiment, volume, and price signals into a unified score (0-100)
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any
from enum import Enum
from datetime import datetime


class SignalStrength(Enum):
    """Signal strength classification"""
    VERY_WEAK = "very_weak"
    WEAK = "weak"
    NEUTRAL = "neutral"
    STRONG = "strong"
    VERY_STRONG = "very_strong"


@dataclass
class ScoreResult:
    """Result of token scoring analysis"""
    symbol: str
    network: str
    total_score: float  # 0-100
    
    # Component scores (0-100 each)
    sentiment_score: float
    volume_score: float
    price_score: float
    
    # Confidence in the score (0-1)
    confidence: float
    
    # Classification
    signal_strength: SignalStrength
    
    # Metadata
    timestamp: datetime = field(default_factory=datetime.utcnow)
    data_sources: Dict[str, bool] = field(default_factory=dict)
    reasoning: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'symbol': self.symbol,
            'network': self.network,
            'total_score': round(self.total_score, 2),
            'sentiment_score': round(self.sentiment_score, 2),
            'volume_score': round(self.volume_score, 2),
            'price_score': round(self.price_score, 2),
            'confidence': round(self.confidence, 3),
            'signal_strength': self.signal_strength.value,
            'timestamp': self.timestamp.isoformat(),
            'data_sources': self.data_sources,
            'reasoning': self.reasoning
        }


@dataclass
class ScoringConfig:
    """Configuration for scoring weights and thresholds"""
    # Weights for each component (must sum to 1.0)
    sentiment_weight: float = 0.35
    volume_weight: float = 0.35
    price_weight: float = 0.30
    
    # Minimum data requirements
    min_sentiment_samples: int = 3
    min_volume_periods: int = 2
    min_price_periods: int = 2
    
    # Score thresholds for signal classification
    very_strong_threshold: float = 80.0
    strong_threshold: float = 65.0
    neutral_low: float = 40.0
    weak_threshold: float = 25.0
    
    def validate(self) -> bool:
        """Validate configuration"""
        weights_sum = self.sentiment_weight + self.volume_weight + self.price_weight
        return abs(weights_sum - 1.0) < 0.001


class TokenScorer:
    """
    Scoring engine that combines multiple signals into a single score
    
    Score interpretation:
    - 80-100: Very Strong bullish signal
    - 65-79: Strong bullish signal
    - 40-64: Neutral / No clear signal
    - 25-39: Weak bearish signal
    - 0-24: Very Weak bearish signal
    """
    
    def __init__(self, config: Optional[ScoringConfig] = None):
        self.config = config or ScoringConfig()
        if not self.config.validate():
            raise ValueError("Scoring weights must sum to 1.0")
    
    def calculate_score(
        self,
        symbol: str,
        network: str,
        sentiment_data: Optional[Dict[str, Any]] = None,
        volume_data: Optional[Dict[str, Any]] = None,
        price_data: Optional[Dict[str, Any]] = None
    ) -> ScoreResult:
        """
        Calculate unified score for a token
        
        Args:
            symbol: Token symbol (e.g., 'PEPE')
            network: Network (e.g., 'base', 'ethereum')
            sentiment_data: Dict with 'score' (-1 to 1), 'sample_count'
            volume_data: Dict with 'change_24h' (%), 'avg_volume', 'current_volume'
            price_data: Dict with 'change_24h' (%), 'change_7d' (%), 'volatility'
        
        Returns:
            ScoreResult with combined analysis
        """
        data_sources = {
            'sentiment': sentiment_data is not None,
            'volume': volume_data is not None,
            'price': price_data is not None
        }
        
        # Calculate individual scores
        sentiment_score, sentiment_conf = self._score_sentiment(sentiment_data)
        volume_score, volume_conf = self._score_volume(volume_data)
        price_score, price_conf = self._score_price(price_data)
        
        # Calculate weighted total score
        # Adjust weights based on available data
        available_weights = []
        if sentiment_data:
            available_weights.append(('sentiment', self.config.sentiment_weight, sentiment_score))
        if volume_data:
            available_weights.append(('volume', self.config.volume_weight, volume_score))
        if price_data:
            available_weights.append(('price', self.config.price_weight, price_score))
        
        if not available_weights:
            return ScoreResult(
                symbol=symbol,
                network=network,
                total_score=50.0,  # Neutral
                sentiment_score=50.0,
                volume_score=50.0,
                price_score=50.0,
                confidence=0.0,
                signal_strength=SignalStrength.NEUTRAL,
                data_sources=data_sources,
                reasoning="INSUFFICIENT_DATA: No data available for scoring"
            )
        
        # Normalize weights for available data
        total_weight = sum(w[1] for w in available_weights)
        total_score = sum((w[1] / total_weight) * w[2] for w in available_weights)
        
        # Calculate overall confidence
        confidence = self._calculate_confidence(
            sentiment_conf, volume_conf, price_conf,
            data_sources
        )
        
        # Classify signal strength
        signal_strength = self._classify_signal(total_score)
        
        # Generate reasoning
        reasoning = self._generate_reasoning(
            total_score, sentiment_score, volume_score, price_score,
            data_sources, signal_strength
        )
        
        return ScoreResult(
            symbol=symbol,
            network=network,
            total_score=total_score,
            sentiment_score=sentiment_score,
            volume_score=volume_score,
            price_score=price_score,
            confidence=confidence,
            signal_strength=signal_strength,
            data_sources=data_sources,
            reasoning=reasoning
        )
    
    def _score_sentiment(self, data: Optional[Dict[str, Any]]) -> tuple[float, float]:
        """Convert sentiment (-1 to 1) to score (0-100)"""
        if not data:
            return 50.0, 0.0
        
        raw_score = data.get('score', 0)  # -1 to 1
        sample_count = data.get('sample_count', 0)
        
        # Normalize to 0-100
        score = (raw_score + 1) * 50
        
        # Confidence based on sample count
        min_samples = self.config.min_sentiment_samples
        confidence = min(1.0, sample_count / (min_samples * 3)) if sample_count > 0 else 0.0
        
        return max(0, min(100, score)), confidence
    
    def _score_volume(self, data: Optional[Dict[str, Any]]) -> tuple[float, float]:
        """Score volume changes (positive change = higher score)"""
        if not data:
            return 50.0, 0.0
        
        change_24h = data.get('change_24h', 0)  # Percentage
        
        # Score based on volume change
        # +100% = score 75, +200% = score 85, etc.
        # -50% = score 25, etc.
        if change_24h >= 0:
            # Positive: 50 to 100 (logarithmic scale)
            import math
            score = 50 + min(50, 25 * math.log10(1 + change_24h / 100 + 0.001) * 2)
        else:
            # Negative: 0 to 50 (linear scale)
            score = max(0, 50 + change_24h / 2)
        
        confidence = 0.8 if 'current_volume' in data else 0.5
        
        return max(0, min(100, score)), confidence
    
    def _score_price(self, data: Optional[Dict[str, Any]]) -> tuple[float, float]:
        """Score price movements"""
        if not data:
            return 50.0, 0.0
        
        change_24h = data.get('change_24h', 0)
        change_7d = data.get('change_7d', 0)
        
        # Combine short and long term changes
        # 24h has more weight for momentum
        combined_change = change_24h * 0.6 + change_7d * 0.4
        
        # Convert to score (soft sigmoid-like)
        import math
        score = 50 + 50 * math.tanh(combined_change / 30)
        
        confidence = 0.7 if 'change_7d' in data else 0.4
        
        return max(0, min(100, score)), confidence
    
    def _calculate_confidence(
        self,
        sent_conf: float,
        vol_conf: float,
        price_conf: float,
        data_sources: Dict[str, bool]
    ) -> float:
        """Calculate overall confidence in the score"""
        sources_available = sum(data_sources.values())
        
        if sources_available == 0:
            return 0.0
        
        # Base confidence from data availability
        data_confidence = sources_available / 3
        
        # Component confidence average
        confs = []
        if data_sources.get('sentiment'):
            confs.append(sent_conf)
        if data_sources.get('volume'):
            confs.append(vol_conf)
        if data_sources.get('price'):
            confs.append(price_conf)
        
        comp_confidence = sum(confs) / len(confs) if confs else 0
        
        # Combined confidence
        return min(1.0, data_confidence * 0.5 + comp_confidence * 0.5)
    
    def _classify_signal(self, score: float) -> SignalStrength:
        """Classify score into signal strength"""
        if score >= self.config.very_strong_threshold:
            return SignalStrength.VERY_STRONG
        elif score >= self.config.strong_threshold:
            return SignalStrength.STRONG
        elif score >= self.config.neutral_low:
            return SignalStrength.NEUTRAL
        elif score >= self.config.weak_threshold:
            return SignalStrength.WEAK
        else:
            return SignalStrength.VERY_WEAK
    
    def _generate_reasoning(
        self,
        total: float,
        sentiment: float,
        volume: float,
        price: float,
        sources: Dict[str, bool],
        strength: SignalStrength
    ) -> str:
        """Generate human-readable reasoning for the score"""
        parts = []
        
        # Data availability
        available = [k for k, v in sources.items() if v]
        if len(available) < 3:
            missing = [k for k, v in sources.items() if not v]
            parts.append(f"⚠️ Limited data: missing {', '.join(missing)}")
        
        # Component analysis
        if sources.get('sentiment'):
            if sentiment > 65:
                parts.append("📈 Positive social sentiment")
            elif sentiment < 35:
                parts.append("📉 Negative social sentiment")
        
        if sources.get('volume'):
            if volume > 70:
                parts.append("🔥 High volume increase")
            elif volume < 30:
                parts.append("📉 Volume declining")
        
        if sources.get('price'):
            if price > 65:
                parts.append("💹 Bullish price action")
            elif price < 35:
                parts.append("🔻 Bearish price action")
        
        # Overall conclusion
        if strength == SignalStrength.VERY_STRONG:
            parts.append(f"✅ STRONG BUY signal (score: {total:.1f})")
        elif strength == SignalStrength.STRONG:
            parts.append(f"🟢 Bullish signal (score: {total:.1f})")
        elif strength == SignalStrength.NEUTRAL:
            parts.append(f"⚪ Neutral, no clear direction (score: {total:.1f})")
        elif strength == SignalStrength.WEAK:
            parts.append(f"🟡 Slightly bearish (score: {total:.1f})")
        else:
            parts.append(f"🔴 Bearish signal (score: {total:.1f})")
        
        return " | ".join(parts)
