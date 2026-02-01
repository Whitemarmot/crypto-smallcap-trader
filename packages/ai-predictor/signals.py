"""
Trading Signal Generator
Converts AI predictions into actionable trading signals
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Union
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta
import logging

from .predictor import PricePredictor, PredictionResult, EnsemblePrediction, Direction

logger = logging.getLogger(__name__)


class SignalType(Enum):
    """Type of trading signal"""
    STRONG_BUY = "STRONG_BUY"
    BUY = "BUY"
    HOLD = "HOLD"
    SELL = "SELL"
    STRONG_SELL = "STRONG_SELL"


class SignalSource(Enum):
    """Source of the signal"""
    AI_PREDICTION = "AI_PREDICTION"
    TECHNICAL = "TECHNICAL"
    SENTIMENT = "SENTIMENT"
    COMBINED = "COMBINED"


@dataclass
class TradingSignal:
    """A trading signal with all relevant information"""
    token: str
    signal_type: SignalType
    confidence: float
    source: SignalSource
    
    # Prediction details
    predicted_direction: Direction
    predicted_return: float
    predicted_price: Optional[float] = None
    current_price: Optional[float] = None
    
    # Risk management
    entry_price: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    position_size_pct: float = 0.0
    risk_reward_ratio: float = 0.0
    
    # Metadata
    timeframe: str = ""
    timestamp: datetime = field(default_factory=datetime.now)
    expiry: Optional[datetime] = None
    notes: str = ""
    
    # Scoring
    score: float = 0.0  # Combined score from multiple factors
    
    def to_dict(self) -> Dict:
        return {
            'token': self.token,
            'signal_type': self.signal_type.value,
            'confidence': self.confidence,
            'source': self.source.value,
            'predicted_direction': self.predicted_direction.value,
            'predicted_return': self.predicted_return,
            'predicted_price': self.predicted_price,
            'current_price': self.current_price,
            'entry_price': self.entry_price,
            'stop_loss': self.stop_loss,
            'take_profit': self.take_profit,
            'position_size_pct': self.position_size_pct,
            'risk_reward_ratio': self.risk_reward_ratio,
            'timeframe': self.timeframe,
            'timestamp': self.timestamp.isoformat(),
            'expiry': self.expiry.isoformat() if self.expiry else None,
            'notes': self.notes,
            'score': self.score
        }
    
    def is_actionable(self) -> bool:
        """Check if signal is actionable (not HOLD and not expired)"""
        if self.signal_type == SignalType.HOLD:
            return False
        if self.expiry and datetime.now() > self.expiry:
            return False
        return True
    
    def __str__(self) -> str:
        return (
            f"{self.signal_type.value} {self.token} | "
            f"Confidence: {self.confidence:.1%} | "
            f"Target: {self.predicted_return:+.2%} | "
            f"RR: {self.risk_reward_ratio:.1f}"
        )


@dataclass
class SignalConfig:
    """Configuration for signal generation"""
    # Confidence thresholds
    min_confidence: float = 0.5
    strong_signal_confidence: float = 0.75
    
    # Return thresholds
    min_expected_return: float = 0.02  # 2%
    strong_return_threshold: float = 0.05  # 5%
    
    # Risk management
    default_stop_loss_pct: float = 0.05  # 5%
    default_take_profit_pct: float = 0.10  # 10%
    max_position_size_pct: float = 0.1  # 10% of portfolio
    min_risk_reward: float = 1.5
    
    # Signal validity
    signal_validity_hours: int = 24
    
    # Position sizing
    use_kelly_criterion: bool = True
    kelly_fraction: float = 0.25  # Fractional Kelly


class SignalGenerator:
    """
    Generate trading signals from AI predictions.
    
    Features:
    - Converts predictions to actionable signals
    - Calculates risk management levels
    - Position sizing based on confidence
    - Signal filtering and prioritization
    """
    
    def __init__(
        self,
        predictor: Optional[PricePredictor] = None,
        config: Optional[SignalConfig] = None
    ):
        self.predictor = predictor
        self.config = config or SignalConfig()
        
        # Signal history
        self.signal_history: List[TradingSignal] = []
    
    def generate_signal(
        self,
        token: str,
        prediction: Union[PredictionResult, EnsemblePrediction],
        current_price: float,
        additional_data: Optional[Dict] = None
    ) -> TradingSignal:
        """
        Generate a trading signal from a prediction.
        
        Args:
            token: Token symbol
            prediction: Prediction result
            current_price: Current market price
            additional_data: Additional data for signal enhancement
            
        Returns:
            TradingSignal with full details
        """
        # Determine signal type
        signal_type = self._determine_signal_type(prediction)
        
        # Calculate risk levels
        stop_loss, take_profit = self._calculate_risk_levels(
            prediction.direction,
            current_price,
            prediction.predicted_return
        )
        
        # Calculate position size
        position_size = self._calculate_position_size(
            prediction.confidence,
            prediction.predicted_return,
            stop_loss / current_price - 1 if stop_loss else self.config.default_stop_loss_pct
        )
        
        # Calculate risk-reward ratio
        if stop_loss and take_profit:
            risk = abs(current_price - stop_loss)
            reward = abs(take_profit - current_price)
            risk_reward = reward / risk if risk > 0 else 0
        else:
            risk_reward = 0
        
        # Calculate signal score
        score = self._calculate_signal_score(
            prediction, signal_type, risk_reward, additional_data
        )
        
        # Determine entry price (slightly above/below current for limit orders)
        if prediction.direction == Direction.UP:
            entry_price = current_price * 0.998  # Buy slightly below
        elif prediction.direction == Direction.DOWN:
            entry_price = current_price * 1.002  # Sell slightly above
        else:
            entry_price = current_price
        
        # Create signal
        signal = TradingSignal(
            token=token,
            signal_type=signal_type,
            confidence=prediction.confidence,
            source=SignalSource.AI_PREDICTION,
            predicted_direction=prediction.direction,
            predicted_return=prediction.predicted_return,
            predicted_price=prediction.predicted_price,
            current_price=current_price,
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            position_size_pct=position_size,
            risk_reward_ratio=risk_reward,
            timeframe=getattr(prediction, 'timeframe', '24h'),
            timestamp=datetime.now(),
            expiry=datetime.now() + timedelta(hours=self.config.signal_validity_hours),
            score=score
        )
        
        # Add to history
        self.signal_history.append(signal)
        
        return signal
    
    def generate_signals_batch(
        self,
        predictions: Dict[str, Union[PredictionResult, EnsemblePrediction]],
        prices: Dict[str, float]
    ) -> List[TradingSignal]:
        """
        Generate signals for multiple tokens.
        
        Args:
            predictions: Dictionary of token -> prediction
            prices: Dictionary of token -> current price
            
        Returns:
            List of signals sorted by score
        """
        signals = []
        
        for token, prediction in predictions.items():
            if token not in prices:
                continue
            
            signal = self.generate_signal(token, prediction, prices[token])
            signals.append(signal)
        
        # Sort by score (highest first)
        signals.sort(key=lambda s: s.score, reverse=True)
        
        return signals
    
    def filter_signals(
        self,
        signals: List[TradingSignal],
        min_confidence: Optional[float] = None,
        min_score: Optional[float] = None,
        signal_types: Optional[List[SignalType]] = None,
        max_signals: int = 10
    ) -> List[TradingSignal]:
        """
        Filter and prioritize signals.
        
        Args:
            signals: List of signals to filter
            min_confidence: Minimum confidence threshold
            min_score: Minimum score threshold
            signal_types: Allowed signal types
            max_signals: Maximum number of signals to return
            
        Returns:
            Filtered and sorted signals
        """
        filtered = signals.copy()
        
        # Apply confidence filter
        if min_confidence is not None:
            filtered = [s for s in filtered if s.confidence >= min_confidence]
        else:
            filtered = [s for s in filtered if s.confidence >= self.config.min_confidence]
        
        # Apply score filter
        if min_score is not None:
            filtered = [s for s in filtered if s.score >= min_score]
        
        # Apply signal type filter
        if signal_types:
            filtered = [s for s in filtered if s.signal_type in signal_types]
        
        # Remove non-actionable signals
        filtered = [s for s in filtered if s.is_actionable()]
        
        # Sort by score and limit
        filtered.sort(key=lambda s: s.score, reverse=True)
        
        return filtered[:max_signals]
    
    def get_portfolio_signals(
        self,
        signals: List[TradingSignal],
        current_positions: Optional[Dict[str, float]] = None,
        max_positions: int = 5,
        max_portfolio_risk: float = 0.2
    ) -> List[TradingSignal]:
        """
        Get signals for portfolio management.
        
        Considers:
        - Current positions
        - Portfolio concentration
        - Total risk exposure
        
        Args:
            signals: Available signals
            current_positions: Current token -> position size
            max_positions: Maximum positions
            max_portfolio_risk: Maximum total portfolio risk
            
        Returns:
            Optimized list of signals
        """
        current_positions = current_positions or {}
        
        # Filter only BUY signals for new positions
        buy_signals = [s for s in signals 
                       if s.signal_type in [SignalType.BUY, SignalType.STRONG_BUY]
                       and s.token not in current_positions]
        
        # Sort by score
        buy_signals.sort(key=lambda s: s.score, reverse=True)
        
        # Calculate available slots
        available_slots = max_positions - len(current_positions)
        
        if available_slots <= 0:
            return []
        
        # Select top signals respecting risk limits
        selected = []
        total_position = sum(current_positions.values())
        
        for signal in buy_signals:
            if len(selected) >= available_slots:
                break
            
            new_total = total_position + signal.position_size_pct
            if new_total <= max_portfolio_risk:
                selected.append(signal)
                total_position = new_total
        
        return selected
    
    def _determine_signal_type(
        self,
        prediction: Union[PredictionResult, EnsemblePrediction]
    ) -> SignalType:
        """Determine signal type from prediction"""
        direction = prediction.direction
        confidence = prediction.confidence
        predicted_return = abs(prediction.predicted_return)
        
        # Check for HOLD conditions
        if direction == Direction.NEUTRAL:
            return SignalType.HOLD
        
        if confidence < self.config.min_confidence:
            return SignalType.HOLD
        
        if predicted_return < self.config.min_expected_return:
            return SignalType.HOLD
        
        # Determine strength
        is_strong = (
            confidence >= self.config.strong_signal_confidence and
            predicted_return >= self.config.strong_return_threshold
        )
        
        # For ensemble predictions, also check agreement
        if isinstance(prediction, EnsemblePrediction):
            is_strong = is_strong and prediction.agreement >= 0.8
        
        # Map to signal type
        if direction == Direction.UP:
            return SignalType.STRONG_BUY if is_strong else SignalType.BUY
        else:  # DOWN
            return SignalType.STRONG_SELL if is_strong else SignalType.SELL
    
    def _calculate_risk_levels(
        self,
        direction: Direction,
        current_price: float,
        predicted_return: float
    ) -> Tuple[float, float]:
        """Calculate stop loss and take profit levels"""
        
        if direction == Direction.UP:
            # Long position
            stop_loss = current_price * (1 - self.config.default_stop_loss_pct)
            
            # Take profit based on prediction, but at least min threshold
            tp_return = max(predicted_return, self.config.default_take_profit_pct)
            take_profit = current_price * (1 + tp_return)
            
        elif direction == Direction.DOWN:
            # Short position (or sell signal)
            stop_loss = current_price * (1 + self.config.default_stop_loss_pct)
            
            tp_return = max(abs(predicted_return), self.config.default_take_profit_pct)
            take_profit = current_price * (1 - tp_return)
            
        else:
            # Neutral - no risk levels
            stop_loss = None
            take_profit = None
        
        return stop_loss, take_profit
    
    def _calculate_position_size(
        self,
        confidence: float,
        expected_return: float,
        risk: float
    ) -> float:
        """
        Calculate position size based on Kelly criterion or simple scaling.
        
        Args:
            confidence: Model confidence (proxy for win probability)
            expected_return: Expected return on win
            risk: Expected loss on stop (as percentage)
            
        Returns:
            Position size as percentage of portfolio
        """
        if self.config.use_kelly_criterion:
            # Kelly Criterion: f = (bp - q) / b
            # where b = odds (expected_return / risk), p = win prob, q = 1 - p
            p = confidence
            q = 1 - p
            b = abs(expected_return) / abs(risk) if risk != 0 else 1
            
            kelly = (b * p - q) / b if b > 0 else 0
            kelly = max(0, kelly)  # No negative positions
            
            # Apply fractional Kelly
            position_size = kelly * self.config.kelly_fraction
        else:
            # Simple scaling based on confidence
            position_size = confidence * self.config.max_position_size_pct
        
        # Cap at maximum
        position_size = min(position_size, self.config.max_position_size_pct)
        
        return position_size
    
    def _calculate_signal_score(
        self,
        prediction: Union[PredictionResult, EnsemblePrediction],
        signal_type: SignalType,
        risk_reward: float,
        additional_data: Optional[Dict]
    ) -> float:
        """
        Calculate overall signal score (0-100).
        
        Factors:
        - Confidence (30%)
        - Expected return (20%)
        - Risk-reward ratio (20%)
        - Signal strength (15%)
        - Model agreement for ensemble (15%)
        """
        score = 0
        
        # Confidence component (0-30)
        score += prediction.confidence * 30
        
        # Expected return component (0-20)
        return_score = min(abs(prediction.predicted_return) / 0.1, 1) * 20
        score += return_score
        
        # Risk-reward component (0-20)
        rr_score = min(risk_reward / 3, 1) * 20  # 3:1 RR = full score
        score += rr_score
        
        # Signal strength (0-15)
        if signal_type in [SignalType.STRONG_BUY, SignalType.STRONG_SELL]:
            score += 15
        elif signal_type in [SignalType.BUY, SignalType.SELL]:
            score += 10
        # HOLD gets 0
        
        # Model agreement for ensemble (0-15)
        if isinstance(prediction, EnsemblePrediction):
            score += prediction.agreement * 15
        else:
            score += 7.5  # Half score for single model
        
        return min(score, 100)
    
    def get_signal_summary(
        self,
        signals: List[TradingSignal]
    ) -> Dict:
        """Get summary statistics for a list of signals"""
        if not signals:
            return {'count': 0}
        
        buy_signals = [s for s in signals 
                       if s.signal_type in [SignalType.BUY, SignalType.STRONG_BUY]]
        sell_signals = [s for s in signals 
                        if s.signal_type in [SignalType.SELL, SignalType.STRONG_SELL]]
        
        return {
            'count': len(signals),
            'buy_count': len(buy_signals),
            'sell_count': len(sell_signals),
            'hold_count': len([s for s in signals if s.signal_type == SignalType.HOLD]),
            'avg_confidence': np.mean([s.confidence for s in signals]),
            'avg_score': np.mean([s.score for s in signals]),
            'top_buys': [s.token for s in buy_signals[:3]],
            'top_sells': [s.token for s in sell_signals[:3]],
            'timestamp': datetime.now().isoformat()
        }
    
    def clear_expired_signals(self):
        """Remove expired signals from history"""
        now = datetime.now()
        self.signal_history = [
            s for s in self.signal_history
            if s.expiry is None or s.expiry > now
        ]


class TechnicalSignalGenerator:
    """
    Generate signals from technical analysis only.
    Can be combined with AI signals.
    """
    
    def __init__(self):
        self.indicators = {}
    
    def analyze(self, ohlcv: pd.DataFrame) -> Dict[str, float]:
        """
        Analyze OHLCV data and return technical scores.
        
        Returns:
            Dictionary of indicator -> score (-1 to 1)
        """
        close = ohlcv['close']
        
        scores = {}
        
        # RSI
        rsi = self._calculate_rsi(close)
        if rsi < 30:
            scores['rsi'] = 0.8  # Oversold = bullish
        elif rsi > 70:
            scores['rsi'] = -0.8  # Overbought = bearish
        else:
            scores['rsi'] = (50 - rsi) / 50  # Neutral zone
        
        # MACD
        macd, signal = self._calculate_macd(close)
        if macd > signal:
            scores['macd'] = min((macd - signal) / abs(signal + 1e-6), 1)
        else:
            scores['macd'] = max((macd - signal) / abs(signal + 1e-6), -1)
        
        # Moving averages
        sma_20 = close.rolling(20).mean().iloc[-1]
        sma_50 = close.rolling(50).mean().iloc[-1]
        current = close.iloc[-1]
        
        if current > sma_20 > sma_50:
            scores['ma'] = 0.7
        elif current < sma_20 < sma_50:
            scores['ma'] = -0.7
        else:
            scores['ma'] = 0
        
        # Volume trend
        vol_sma = ohlcv['volume'].rolling(20).mean().iloc[-1]
        current_vol = ohlcv['volume'].iloc[-1]
        vol_ratio = current_vol / vol_sma if vol_sma > 0 else 1
        
        # High volume confirms trend
        price_change = (current - close.iloc[-2]) / close.iloc[-2]
        if vol_ratio > 1.5:
            scores['volume'] = 0.5 * np.sign(price_change)
        else:
            scores['volume'] = 0
        
        return scores
    
    def generate_signal(
        self,
        token: str,
        ohlcv: pd.DataFrame,
        current_price: float
    ) -> TradingSignal:
        """Generate a trading signal from technical analysis"""
        scores = self.analyze(ohlcv)
        
        # Weighted average score
        weights = {'rsi': 0.25, 'macd': 0.3, 'ma': 0.3, 'volume': 0.15}
        total_score = sum(scores.get(k, 0) * v for k, v in weights.items())
        
        # Convert to direction and confidence
        if total_score > 0.3:
            direction = Direction.UP
            signal_type = SignalType.STRONG_BUY if total_score > 0.6 else SignalType.BUY
        elif total_score < -0.3:
            direction = Direction.DOWN
            signal_type = SignalType.STRONG_SELL if total_score < -0.6 else SignalType.SELL
        else:
            direction = Direction.NEUTRAL
            signal_type = SignalType.HOLD
        
        confidence = min(abs(total_score), 1)
        
        return TradingSignal(
            token=token,
            signal_type=signal_type,
            confidence=confidence,
            source=SignalSource.TECHNICAL,
            predicted_direction=direction,
            predicted_return=total_score * 0.05,  # Rough estimate
            current_price=current_price,
            timestamp=datetime.now(),
            score=abs(total_score) * 50,  # Scale to 0-50
            notes=f"Technical scores: {scores}"
        )
    
    @staticmethod
    def _calculate_rsi(prices: pd.Series, period: int = 14) -> float:
        delta = prices.diff()
        gain = delta.where(delta > 0, 0).ewm(com=period - 1).mean()
        loss = (-delta).where(delta < 0, 0).ewm(com=period - 1).mean()
        rs = gain / (loss + 1e-6)
        rsi = 100 - (100 / (1 + rs))
        return rsi.iloc[-1]
    
    @staticmethod
    def _calculate_macd(prices: pd.Series) -> Tuple[float, float]:
        ema12 = prices.ewm(span=12).mean()
        ema26 = prices.ewm(span=26).mean()
        macd = (ema12 - ema26).iloc[-1]
        signal = (ema12 - ema26).ewm(span=9).mean().iloc[-1]
        return macd, signal
