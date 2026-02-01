"""
Momentum Strategy
Suit les tendances basées sur des indicateurs techniques (RSI, MACD)
"""
from decimal import Decimal
from datetime import datetime
from typing import Optional
from enum import Enum

from base import BaseStrategy
from models import (
    StrategyConfig, TradeSignal, SignalType,
    Position, MarketData
)


class TrendDirection(Enum):
    """Direction de la tendance"""
    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"


class MomentumStrategy(BaseStrategy):
    """
    Momentum Strategy
    
    Principe:
    - Achète quand le momentum est positif (tendance haussière confirmée)
    - Vend quand le momentum s'inverse
    - Utilise RSI, MACD, et moyennes mobiles
    
    Paramètres (dans config.params):
    - rsi_oversold: Seuil RSI survendu (défaut: 30)
    - rsi_overbought: Seuil RSI suracheté (défaut: 70)
    - macd_signal_threshold: Sensibilité MACD (défaut: 0)
    - sma_fast: Période SMA rapide (défaut: 20)
    - sma_slow: Période SMA lente (défaut: 50)
    - trend_confirmation: Nombre de signaux requis (défaut: 2)
    - position_sizing: "fixed" ou "dynamic" (défaut: fixed)
    """
    
    STRATEGY_TYPE = "momentum"
    STRATEGY_NAME = "Momentum Trading"
    
    def __init__(self, config: StrategyConfig):
        super().__init__(config)
        
        # Paramètres RSI
        self.rsi_oversold = Decimal(str(config.params.get("rsi_oversold", 30)))
        self.rsi_overbought = Decimal(str(config.params.get("rsi_overbought", 70)))
        
        # Paramètres MACD
        self.macd_signal_threshold = Decimal(str(config.params.get("macd_signal_threshold", 0)))
        
        # Moyennes mobiles
        self.sma_fast = config.params.get("sma_fast", 20)
        self.sma_slow = config.params.get("sma_slow", 50)
        
        # Confirmation
        self.trend_confirmation = config.params.get("trend_confirmation", 2)
        self.position_sizing = config.params.get("position_sizing", "fixed")
        
        # État interne
        self._current_trend: TrendDirection = TrendDirection.NEUTRAL
        self._trend_strength: Decimal = Decimal("0")
        self._last_signals: list[dict] = []  # Historique des signaux récents
    
    async def analyze(self, market_data: MarketData) -> list[TradeSignal]:
        """
        Analyse Momentum - évalue les indicateurs techniques
        """
        signals = []
        
        # Analyser les indicateurs
        trend, strength, analysis = self._analyze_indicators(market_data)
        self._current_trend = trend
        self._trend_strength = strength
        
        # Générer des signaux basés sur l'analyse
        if trend == TrendDirection.BULLISH:
            should_buy, amount, reason = self.should_buy(market_data)
            if should_buy:
                signals.append(self.create_buy_signal(
                    amount=amount,
                    confidence=strength,
                    reason=reason,
                    indicators=analysis,
                ))
        
        elif trend == TrendDirection.BEARISH and self.open_positions:
            for position in self.open_positions:
                should_sell, amount, reason = self.should_sell(market_data, position)
                if should_sell:
                    signals.append(self.create_sell_signal(
                        amount=amount,
                        confidence=strength,
                        reason=reason,
                        indicators=analysis,
                    ))
        
        if not signals:
            signals.append(self.create_hold_signal(
                f"Trend: {trend.value} (strength: {strength:.2f})"
            ))
        
        return signals
    
    def _analyze_indicators(self, market_data: MarketData) -> tuple[TrendDirection, Decimal, dict]:
        """
        Analyse les indicateurs techniques et détermine la tendance
        
        Returns:
            (trend_direction, strength, indicators_dict)
        """
        bullish_signals = 0
        bearish_signals = 0
        analysis = {}
        
        # === RSI Analysis ===
        if market_data.rsi_14 is not None:
            rsi = market_data.rsi_14
            analysis["rsi"] = {
                "value": str(rsi),
                "signal": None,
            }
            
            if rsi <= self.rsi_oversold:
                bullish_signals += 1
                analysis["rsi"]["signal"] = "oversold_bullish"
                self.logger.debug(f"RSI oversold ({rsi}) - bullish signal")
            elif rsi >= self.rsi_overbought:
                bearish_signals += 1
                analysis["rsi"]["signal"] = "overbought_bearish"
                self.logger.debug(f"RSI overbought ({rsi}) - bearish signal")
            
            # RSI momentum (direction du RSI)
            if rsi > 50:
                bullish_signals += 0.5
                analysis["rsi"]["momentum"] = "positive"
            elif rsi < 50:
                bearish_signals += 0.5
                analysis["rsi"]["momentum"] = "negative"
        
        # === MACD Analysis ===
        if market_data.macd_line is not None and market_data.macd_signal is not None:
            macd = market_data.macd_line
            signal = market_data.macd_signal
            histogram = market_data.macd_histogram or (macd - signal)
            
            analysis["macd"] = {
                "line": str(macd),
                "signal": str(signal),
                "histogram": str(histogram),
                "cross": None,
            }
            
            # MACD cross
            if macd > signal + self.macd_signal_threshold:
                bullish_signals += 1
                analysis["macd"]["cross"] = "bullish"
                self.logger.debug(f"MACD bullish cross")
            elif macd < signal - self.macd_signal_threshold:
                bearish_signals += 1
                analysis["macd"]["cross"] = "bearish"
                self.logger.debug(f"MACD bearish cross")
            
            # Histogram momentum
            if histogram > 0:
                bullish_signals += 0.5
                analysis["macd"]["histogram_trend"] = "positive"
            elif histogram < 0:
                bearish_signals += 0.5
                analysis["macd"]["histogram_trend"] = "negative"
        
        # === Moving Averages Analysis ===
        if market_data.sma_20 is not None and market_data.sma_50 is not None:
            sma_fast = market_data.sma_20
            sma_slow = market_data.sma_50
            price = market_data.current_price
            
            analysis["moving_averages"] = {
                "sma_fast": str(sma_fast),
                "sma_slow": str(sma_slow),
                "price_vs_sma": None,
                "golden_cross": None,
            }
            
            # Prix au-dessus/dessous des moyennes
            if price > sma_fast and price > sma_slow:
                bullish_signals += 1
                analysis["moving_averages"]["price_vs_sma"] = "above_both"
            elif price < sma_fast and price < sma_slow:
                bearish_signals += 1
                analysis["moving_averages"]["price_vs_sma"] = "below_both"
            
            # Golden/Death cross
            if sma_fast > sma_slow:
                bullish_signals += 0.5
                analysis["moving_averages"]["golden_cross"] = True
            else:
                bearish_signals += 0.5
                analysis["moving_averages"]["golden_cross"] = False
        
        # === EMA Analysis ===
        if market_data.ema_12 is not None and market_data.ema_26 is not None:
            ema_fast = market_data.ema_12
            ema_slow = market_data.ema_26
            
            analysis["ema"] = {
                "ema_12": str(ema_fast),
                "ema_26": str(ema_slow),
            }
            
            if ema_fast > ema_slow:
                bullish_signals += 0.5
                analysis["ema"]["trend"] = "bullish"
            else:
                bearish_signals += 0.5
                analysis["ema"]["trend"] = "bearish"
        
        # === Bollinger Bands ===
        if market_data.bollinger_upper is not None and market_data.bollinger_lower is not None:
            upper = market_data.bollinger_upper
            lower = market_data.bollinger_lower
            price = market_data.current_price
            
            analysis["bollinger"] = {
                "upper": str(upper),
                "lower": str(lower),
                "position": None,
            }
            
            # Prix proche des bandes
            if price <= lower * Decimal("1.02"):
                bullish_signals += 1  # Potentiel rebond
                analysis["bollinger"]["position"] = "near_lower"
            elif price >= upper * Decimal("0.98"):
                bearish_signals += 0.5  # Potentiel retour
                analysis["bollinger"]["position"] = "near_upper"
        
        # === Déterminer la tendance ===
        total_signals = bullish_signals + bearish_signals
        
        if total_signals == 0:
            return TrendDirection.NEUTRAL, Decimal("0.5"), analysis
        
        # Calculer la force de la tendance
        if bullish_signals >= self.trend_confirmation and bullish_signals > bearish_signals:
            strength = Decimal(str(min(bullish_signals / total_signals, 1)))
            return TrendDirection.BULLISH, strength, analysis
        
        elif bearish_signals >= self.trend_confirmation and bearish_signals > bullish_signals:
            strength = Decimal(str(min(bearish_signals / total_signals, 1)))
            return TrendDirection.BEARISH, strength, analysis
        
        return TrendDirection.NEUTRAL, Decimal("0.5"), analysis
    
    def should_buy(self, market_data: MarketData) -> tuple[bool, Decimal, str]:
        """
        Détermine s'il faut acheter
        
        Momentum achète quand:
        - Tendance bullish confirmée
        - Force suffisante
        - Capital disponible
        """
        if self._current_trend != TrendDirection.BULLISH:
            return False, Decimal("0"), f"Trend not bullish ({self._current_trend.value})"
        
        # Déjà en position ?
        if self.open_positions:
            # On peut pyramider si la tendance est forte
            if self._trend_strength < Decimal("0.8"):
                return False, Decimal("0"), "Already in position, trend not strong enough to add"
        
        # Calculer le montant
        amount = self._calculate_position_size(market_data)
        valid, msg = self.validate_trade_size(amount)
        
        if not valid:
            return False, Decimal("0"), msg
        
        return True, amount, f"Bullish momentum (strength: {self._trend_strength:.2f})"
    
    def should_sell(self, market_data: MarketData, position: Position) -> tuple[bool, Decimal, str]:
        """
        Détermine s'il faut vendre
        
        Momentum vend quand:
        - Tendance bearish
        - Stop loss / Take profit atteint
        - RSI extrême
        """
        # Stop loss / Take profit
        if position.stop_loss_price and market_data.current_price <= position.stop_loss_price:
            return True, position.token_amount, "Stop loss triggered"
        
        if position.take_profit_price and market_data.current_price >= position.take_profit_price:
            return True, position.token_amount, "Take profit triggered"
        
        # Tendance bearish
        if self._current_trend == TrendDirection.BEARISH:
            return True, position.token_amount, f"Bearish momentum (strength: {self._trend_strength:.2f})"
        
        # RSI overbought extrême
        if market_data.rsi_14 and market_data.rsi_14 >= self.rsi_overbought + 10:
            return True, position.token_amount, f"RSI extreme overbought ({market_data.rsi_14})"
        
        # PnL trailing stop (optionnel)
        pnl, pnl_pct = position.calculate_pnl(market_data.current_price)
        if pnl_pct >= Decimal("20") and self._trend_strength < Decimal("0.5"):
            # Prendre profits si +20% et momentum faiblit
            return True, position.token_amount, f"Taking profits ({pnl_pct:.1f}%), momentum weakening"
        
        return False, Decimal("0"), "Hold - no sell signal"
    
    def _calculate_position_size(self, market_data: MarketData) -> Decimal:
        """
        Calcule la taille de position
        
        - Fixed: utilise max_position_size
        - Dynamic: ajuste selon la force du signal
        """
        base_size = self.config.max_position_size
        
        if self.position_sizing == "dynamic":
            # Ajuster selon la force de la tendance
            multiplier = Decimal("0.5") + (self._trend_strength * Decimal("0.5"))
            base_size = base_size * multiplier
            
            # Ajuster selon la volatilité (si disponible)
            if market_data.bollinger_upper and market_data.bollinger_lower:
                width = market_data.bollinger_upper - market_data.bollinger_lower
                avg_price = (market_data.bollinger_upper + market_data.bollinger_lower) / 2
                volatility = width / avg_price
                
                # Réduire la taille si volatilité élevée
                if volatility > Decimal("0.1"):
                    base_size = base_size * Decimal("0.8")
        
        # Ne pas dépasser le capital disponible
        return min(base_size, self.available_capital)
    
    def get_trend_summary(self) -> str:
        """Résumé de la tendance actuelle"""
        return f"{self._current_trend.value.upper()} (strength: {self._trend_strength:.0%})"
    
    def get_state(self) -> dict:
        """État Momentum spécifique"""
        state = super().get_state()
        state["momentum"] = {
            "current_trend": self._current_trend.value,
            "trend_strength": str(self._trend_strength),
            "rsi_thresholds": {
                "oversold": str(self.rsi_oversold),
                "overbought": str(self.rsi_overbought),
            },
            "position_sizing": self.position_sizing,
            "trend_confirmation": self.trend_confirmation,
        }
        return state
