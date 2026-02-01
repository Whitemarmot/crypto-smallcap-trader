"""
Token Analyzer - Main interface for AI Decision module
Combines scoring and prediction into a unified analysis

This is the main entry point: analyze_token()
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any, Callable
from datetime import datetime
import json

# Support both package and direct imports
try:
    from .scorer import TokenScorer, ScoreResult, ScoringConfig
    from .predictor import TradingPredictor, Prediction, TradingAction, PredictorConfig
except ImportError:
    from scorer import TokenScorer, ScoreResult, ScoringConfig
    from predictor import TradingPredictor, Prediction, TradingAction, PredictorConfig


@dataclass
class AnalysisResult:
    """Complete token analysis result"""
    symbol: str
    network: str
    
    # Scoring
    score: ScoreResult
    
    # Prediction
    prediction: Prediction
    
    # Summary
    action: TradingAction
    confidence: float
    summary: str
    
    # Metadata
    timestamp: datetime = field(default_factory=datetime.utcnow)
    version: str = "0.1.0"
    disclaimer: str = "⚠️ EXPERIMENTAL - Not financial advice. DYOR."
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'symbol': self.symbol,
            'network': self.network,
            'action': self.action.value,
            'confidence': round(self.confidence, 3),
            'summary': self.summary,
            'score': self.score.to_dict(),
            'prediction': self.prediction.to_dict(),
            'timestamp': self.timestamp.isoformat(),
            'version': self.version,
            'disclaimer': self.disclaimer
        }
    
    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)


class TokenAnalyzer:
    """
    Main interface for token analysis
    
    Usage:
        analyzer = TokenAnalyzer()
        result = analyzer.analyze_token('PEPE', 'base', data_fetcher=my_fetcher)
        
        # Or with pre-fetched data:
        result = analyzer.analyze_with_data(
            symbol='PEPE',
            network='base',
            sentiment_data={'score': 0.6, 'sample_count': 10},
            volume_data={'change_24h': 75},
            price_data={'change_24h': 15, 'change_7d': 30}
        )
    
    ⚠️ DISCLAIMER: This is an experimental rule-based system.
    - It does NOT use machine learning
    - Past results do not predict future performance
    - Never invest more than you can afford to lose
    """
    
    def __init__(
        self,
        scorer_config: Optional[ScoringConfig] = None,
        predictor_config: Optional[PredictorConfig] = None
    ):
        self.scorer = TokenScorer(config=scorer_config)
        self.predictor = TradingPredictor(config=predictor_config)
    
    def analyze_token(
        self,
        symbol: str,
        network: str,
        data_fetcher: Optional[Callable[[str, str], Dict[str, Any]]] = None
    ) -> AnalysisResult:
        """
        Analyze a token and return recommendation
        
        Args:
            symbol: Token symbol (e.g., 'PEPE')
            network: Network (e.g., 'base', 'ethereum')
            data_fetcher: Optional function(symbol, network) -> dict with data
                Expected dict keys: 'sentiment', 'volume', 'price'
        
        Returns:
            AnalysisResult with score, prediction, and summary
        """
        # Fetch data if fetcher provided
        if data_fetcher:
            try:
                data = data_fetcher(symbol, network)
                return self.analyze_with_data(
                    symbol=symbol,
                    network=network,
                    sentiment_data=data.get('sentiment'),
                    volume_data=data.get('volume'),
                    price_data=data.get('price')
                )
            except Exception as e:
                # Return insufficient data result on fetch error
                return self._insufficient_data_result(
                    symbol, network, 
                    f"Data fetch error: {str(e)}"
                )
        
        # No data fetcher = return insufficient data
        return self._insufficient_data_result(
            symbol, network,
            "No data fetcher provided and no data available"
        )
    
    def analyze_with_data(
        self,
        symbol: str,
        network: str,
        sentiment_data: Optional[Dict[str, Any]] = None,
        volume_data: Optional[Dict[str, Any]] = None,
        price_data: Optional[Dict[str, Any]] = None
    ) -> AnalysisResult:
        """
        Analyze token with pre-fetched data
        
        Args:
            symbol: Token symbol
            network: Network
            sentiment_data: {'score': float (-1 to 1), 'sample_count': int}
            volume_data: {'change_24h': float (%)}
            price_data: {'change_24h': float (%), 'change_7d': float (%)}
        
        Returns:
            AnalysisResult
        """
        # Step 1: Calculate score
        score_result = self.scorer.calculate_score(
            symbol=symbol,
            network=network,
            sentiment_data=sentiment_data,
            volume_data=volume_data,
            price_data=price_data
        )
        
        # Step 2: Generate prediction
        prediction = self.predictor.predict(
            symbol=symbol,
            network=network,
            score=score_result.total_score,
            sentiment=sentiment_data.get('score') if sentiment_data else None,
            volume_change=volume_data.get('change_24h') if volume_data else None,
            price_change=price_data.get('change_24h') if price_data else None
        )
        
        # Step 3: Generate summary
        summary = self._generate_summary(score_result, prediction)
        
        return AnalysisResult(
            symbol=symbol,
            network=network,
            score=score_result,
            prediction=prediction,
            action=prediction.action,
            confidence=prediction.confidence,
            summary=summary
        )
    
    def _generate_summary(self, score: ScoreResult, prediction: Prediction) -> str:
        """Generate human-readable summary"""
        parts = []
        
        # Action
        action_emoji = {
            TradingAction.BUY: "🟢",
            TradingAction.SELL: "🔴",
            TradingAction.HOLD: "⚪",
            TradingAction.INSUFFICIENT_DATA: "❓"
        }
        emoji = action_emoji.get(prediction.action, "❓")
        parts.append(f"{emoji} **{prediction.action.value}** ({prediction.symbol})")
        
        # Score
        parts.append(f"Score: {score.total_score:.0f}/100 ({score.signal_strength.value})")
        
        # Confidence
        conf_pct = prediction.confidence * 100
        if conf_pct >= 70:
            parts.append(f"✅ High confidence: {conf_pct:.0f}%")
        elif conf_pct >= 50:
            parts.append(f"🟡 Medium confidence: {conf_pct:.0f}%")
        else:
            parts.append(f"⚠️ Low confidence: {conf_pct:.0f}%")
        
        # Reason
        parts.append(prediction.reason)
        
        return " | ".join(parts)
    
    def _insufficient_data_result(self, symbol: str, network: str, reason: str) -> AnalysisResult:
        """Create result for insufficient data case"""
        score = ScoreResult(
            symbol=symbol,
            network=network,
            total_score=50.0,
            sentiment_score=50.0,
            volume_score=50.0,
            price_score=50.0,
            confidence=0.0,
            signal_strength=self.scorer._classify_signal(50.0),
            reasoning=f"INSUFFICIENT_DATA: {reason}"
        )
        
        prediction = Prediction(
            symbol=symbol,
            network=network,
            action=TradingAction.INSUFFICIENT_DATA,
            confidence=0.0,
            reason=reason
        )
        
        return AnalysisResult(
            symbol=symbol,
            network=network,
            score=score,
            prediction=prediction,
            action=TradingAction.INSUFFICIENT_DATA,
            confidence=0.0,
            summary=f"❓ INSUFFICIENT_DATA ({symbol}) - {reason}"
        )
    
    def update_scorer_config(self, **kwargs):
        """Update scorer configuration"""
        for key, value in kwargs.items():
            if hasattr(self.scorer.config, key):
                setattr(self.scorer.config, key, value)
    
    def update_predictor_config(self, **kwargs):
        """Update predictor configuration"""
        self.predictor.update_config(**kwargs)
    
    def get_full_config(self) -> Dict[str, Any]:
        """Get complete configuration"""
        return {
            'scorer': {
                'sentiment_weight': self.scorer.config.sentiment_weight,
                'volume_weight': self.scorer.config.volume_weight,
                'price_weight': self.scorer.config.price_weight,
                'very_strong_threshold': self.scorer.config.very_strong_threshold,
                'strong_threshold': self.scorer.config.strong_threshold,
                'neutral_low': self.scorer.config.neutral_low,
                'weak_threshold': self.scorer.config.weak_threshold,
            },
            'predictor': self.predictor.get_config()
        }


# Convenience function
def analyze_token(
    symbol: str,
    network: str,
    sentiment_data: Optional[Dict[str, Any]] = None,
    volume_data: Optional[Dict[str, Any]] = None,
    price_data: Optional[Dict[str, Any]] = None
) -> AnalysisResult:
    """
    Quick function to analyze a token
    
    Example:
        result = analyze_token(
            'PEPE', 'base',
            sentiment_data={'score': 0.6, 'sample_count': 15},
            volume_data={'change_24h': 80},
            price_data={'change_24h': 12, 'change_7d': 25}
        )
        print(result.action)  # TradingAction.BUY
        print(result.confidence)  # 0.75
    """
    analyzer = TokenAnalyzer()
    return analyzer.analyze_with_data(
        symbol=symbol,
        network=network,
        sentiment_data=sentiment_data,
        volume_data=volume_data,
        price_data=price_data
    )
