"""
Rule-Based Trading Predictor
Generates BUY/SELL/HOLD signals based on configurable rules

⚠️ NOT machine learning - simple heuristics only
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
from enum import Enum
from datetime import datetime
import json


class TradingAction(Enum):
    """Trading action recommendation"""
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


@dataclass
class Prediction:
    """Trading prediction result"""
    symbol: str
    network: str
    action: TradingAction
    confidence: float  # 0 to 1
    reason: str
    
    # Individual rule results
    rules_triggered: List[str] = field(default_factory=list)
    rules_passed: int = 0
    rules_total: int = 0
    
    # Input data snapshot
    input_score: Optional[float] = None
    input_sentiment: Optional[float] = None
    input_volume_change: Optional[float] = None
    input_price_change: Optional[float] = None
    
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'symbol': self.symbol,
            'network': self.network,
            'action': self.action.value,
            'confidence': round(self.confidence, 3),
            'reason': self.reason,
            'rules_triggered': self.rules_triggered,
            'rules_passed': self.rules_passed,
            'rules_total': self.rules_total,
            'input_score': self.input_score,
            'input_sentiment': self.input_sentiment,
            'input_volume_change': self.input_volume_change,
            'input_price_change': self.input_price_change,
            'timestamp': self.timestamp.isoformat()
        }


@dataclass
class PredictorConfig:
    """Configuration for trading rules"""
    # Buy thresholds
    buy_score_threshold: float = 70.0  # Minimum score for BUY
    buy_sentiment_min: float = 0.3  # Minimum sentiment (-1 to 1)
    buy_volume_increase_min: float = 50.0  # Minimum volume increase %
    
    # Sell thresholds
    sell_score_threshold: float = 30.0  # Score below this = SELL
    sell_sentiment_max: float = -0.3  # Sentiment below this
    sell_volume_decrease_max: float = -30.0  # Volume decrease %
    
    # Confidence modifiers
    min_confidence_to_act: float = 0.5  # Minimum confidence to suggest action
    
    # Risk management
    require_multiple_signals: bool = True  # Need >1 positive signal
    min_buy_signals: int = 2
    min_sell_signals: int = 2


class TradingPredictor:
    """
    Rule-based trading signal generator
    
    Rules are evaluated independently and combined to produce a final signal
    This is NOT machine learning - just configurable if/then rules
    
    ⚠️ EXPERIMENTAL - Use at your own risk
    """
    
    def __init__(self, config: Optional[PredictorConfig] = None):
        self.config = config or PredictorConfig()
    
    def predict(
        self,
        symbol: str,
        network: str,
        score: Optional[float] = None,  # 0-100
        sentiment: Optional[float] = None,  # -1 to 1
        volume_change: Optional[float] = None,  # % change
        price_change: Optional[float] = None,  # % change 24h
        additional_data: Optional[Dict[str, Any]] = None
    ) -> Prediction:
        """
        Generate trading prediction based on rules
        
        Args:
            symbol: Token symbol
            network: Blockchain network
            score: Overall score (0-100)
            sentiment: Sentiment score (-1 to 1)
            volume_change: Volume change percentage
            price_change: Price change percentage
            additional_data: Extra data for custom rules
        
        Returns:
            Prediction with action (BUY/SELL/HOLD) and reasoning
        """
        # Check if we have enough data
        data_points = [score, sentiment, volume_change, price_change]
        available = sum(1 for d in data_points if d is not None)
        
        if available < 2:
            return Prediction(
                symbol=symbol,
                network=network,
                action=TradingAction.INSUFFICIENT_DATA,
                confidence=0.0,
                reason="Not enough data to make a prediction (need at least 2 data points)",
                input_score=score,
                input_sentiment=sentiment,
                input_volume_change=volume_change,
                input_price_change=price_change
            )
        
        # Evaluate all rules
        buy_signals = []
        sell_signals = []
        all_rules = []
        
        # Rule 1: Score threshold
        if score is not None:
            if score >= self.config.buy_score_threshold:
                buy_signals.append(f"Score {score:.1f} >= {self.config.buy_score_threshold} (BUY threshold)")
            elif score <= self.config.sell_score_threshold:
                sell_signals.append(f"Score {score:.1f} <= {self.config.sell_score_threshold} (SELL threshold)")
            all_rules.append("score_threshold")
        
        # Rule 2: Sentiment threshold
        if sentiment is not None:
            if sentiment >= self.config.buy_sentiment_min:
                buy_signals.append(f"Sentiment {sentiment:.2f} >= {self.config.buy_sentiment_min} (positive)")
            elif sentiment <= self.config.sell_sentiment_max:
                sell_signals.append(f"Sentiment {sentiment:.2f} <= {self.config.sell_sentiment_max} (negative)")
            all_rules.append("sentiment_threshold")
        
        # Rule 3: Volume spike
        if volume_change is not None:
            if volume_change >= self.config.buy_volume_increase_min:
                buy_signals.append(f"Volume +{volume_change:.1f}% >= {self.config.buy_volume_increase_min}% (spike)")
            elif volume_change <= self.config.sell_volume_decrease_max:
                sell_signals.append(f"Volume {volume_change:.1f}% <= {self.config.sell_volume_decrease_max}% (declining)")
            all_rules.append("volume_change")
        
        # Rule 4: Price momentum (combined with other signals)
        if price_change is not None:
            if price_change > 10 and len(buy_signals) > 0:
                buy_signals.append(f"Price +{price_change:.1f}% (bullish momentum)")
            elif price_change < -10 and len(sell_signals) > 0:
                sell_signals.append(f"Price {price_change:.1f}% (bearish momentum)")
            all_rules.append("price_momentum")
        
        # Rule 5: Combined signal (sentiment + volume)
        if sentiment is not None and volume_change is not None:
            if sentiment > 0.5 and volume_change > 50:
                buy_signals.append("Strong combined: sentiment > 0.5 AND volume > +50%")
            elif sentiment < -0.5 and volume_change < -20:
                sell_signals.append("Weak combined: sentiment < -0.5 AND volume < -20%")
            all_rules.append("combined_signal")
        
        # Determine action
        action, confidence, reason = self._determine_action(
            buy_signals, sell_signals, all_rules
        )
        
        return Prediction(
            symbol=symbol,
            network=network,
            action=action,
            confidence=confidence,
            reason=reason,
            rules_triggered=buy_signals + sell_signals,
            rules_passed=len(buy_signals) if action == TradingAction.BUY else len(sell_signals),
            rules_total=len(all_rules),
            input_score=score,
            input_sentiment=sentiment,
            input_volume_change=volume_change,
            input_price_change=price_change
        )
    
    def _determine_action(
        self,
        buy_signals: List[str],
        sell_signals: List[str],
        all_rules: List[str]
    ) -> tuple[TradingAction, float, str]:
        """Determine final action from collected signals"""
        buy_count = len(buy_signals)
        sell_count = len(sell_signals)
        total_rules = len(all_rules)
        
        if total_rules == 0:
            return TradingAction.HOLD, 0.0, "No rules evaluated"
        
        # Check if requiring multiple signals
        if self.config.require_multiple_signals:
            min_buy = self.config.min_buy_signals
            min_sell = self.config.min_sell_signals
        else:
            min_buy = 1
            min_sell = 1
        
        # BUY signal
        if buy_count >= min_buy and buy_count > sell_count:
            confidence = min(1.0, buy_count / total_rules * 1.5)
            if confidence >= self.config.min_confidence_to_act:
                reasons = " | ".join(buy_signals[:3])  # Top 3 reasons
                return TradingAction.BUY, confidence, f"BUY: {reasons}"
        
        # SELL signal
        if sell_count >= min_sell and sell_count > buy_count:
            confidence = min(1.0, sell_count / total_rules * 1.5)
            if confidence >= self.config.min_confidence_to_act:
                reasons = " | ".join(sell_signals[:3])
                return TradingAction.SELL, confidence, f"SELL: {reasons}"
        
        # Mixed or weak signals = HOLD
        if buy_count > 0 and sell_count > 0:
            return TradingAction.HOLD, 0.3, f"Mixed signals: {buy_count} bullish, {sell_count} bearish - HOLD"
        
        if buy_count > 0:
            return TradingAction.HOLD, 0.4, f"Weak bullish ({buy_count} signals, need {min_buy}) - HOLD for now"
        
        if sell_count > 0:
            return TradingAction.HOLD, 0.4, f"Weak bearish ({sell_count} signals, need {min_sell}) - HOLD for now"
        
        return TradingAction.HOLD, 0.5, "No clear signals - HOLD"
    
    def update_config(self, **kwargs):
        """Update predictor configuration"""
        for key, value in kwargs.items():
            if hasattr(self.config, key):
                setattr(self.config, key, value)
    
    def get_config(self) -> Dict[str, Any]:
        """Get current configuration as dict"""
        return {
            'buy_score_threshold': self.config.buy_score_threshold,
            'buy_sentiment_min': self.config.buy_sentiment_min,
            'buy_volume_increase_min': self.config.buy_volume_increase_min,
            'sell_score_threshold': self.config.sell_score_threshold,
            'sell_sentiment_max': self.config.sell_sentiment_max,
            'sell_volume_decrease_max': self.config.sell_volume_decrease_max,
            'min_confidence_to_act': self.config.min_confidence_to_act,
            'require_multiple_signals': self.config.require_multiple_signals,
            'min_buy_signals': self.config.min_buy_signals,
            'min_sell_signals': self.config.min_sell_signals
        }
