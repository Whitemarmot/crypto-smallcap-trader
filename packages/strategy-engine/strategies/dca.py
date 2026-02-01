"""
DCA Strategy - Dollar Cost Averaging
Achats réguliers à intervalles fixes, indépendamment du prix
"""
from decimal import Decimal
from datetime import datetime, timedelta
from typing import Optional

from base import BaseStrategy
from models import (
    StrategyConfig, TradeSignal, SignalType,
    Position, MarketData
)


class DCAStrategy(BaseStrategy):
    """
    Dollar Cost Averaging Strategy
    
    Principe:
    - Achète un montant fixe à intervalles réguliers
    - Ignore les variations de prix (réduit l'impact de la volatilité)
    - Idéal pour accumuler sur le long terme
    
    Paramètres (dans config.params):
    - amount_per_buy: Montant par achat (défaut: 50)
    - interval_hours: Intervalle entre achats en heures (défaut: 24)
    - max_buys: Nombre max d'achats (None = illimité)
    - buy_on_dip_bonus: Bonus % si prix baisse de X% (optionnel)
    - dip_threshold: Seuil de baisse pour bonus (défaut: 5%)
    """
    
    STRATEGY_TYPE = "dca"
    STRATEGY_NAME = "Dollar Cost Averaging"
    
    def __init__(self, config: StrategyConfig):
        super().__init__(config)
        
        # Paramètres DCA
        self.amount_per_buy = Decimal(str(config.params.get("amount_per_buy", 50)))
        self.interval_hours = config.params.get("interval_hours", 24)
        self.max_buys = config.params.get("max_buys", None)
        self.buy_on_dip_bonus = Decimal(str(config.params.get("buy_on_dip_bonus", 0)))
        self.dip_threshold = Decimal(str(config.params.get("dip_threshold", 5)))
        
        # État interne
        self._last_buy_time: Optional[datetime] = None
        self._buy_count: int = 0
        self._reference_price: Optional[Decimal] = None  # Pour calculer les dips
    
    async def analyze(self, market_data: MarketData) -> list[TradeSignal]:
        """
        Analyse DCA - vérifie si c'est le moment d'acheter
        """
        signals = []
        
        # Vérifier si on a atteint le max d'achats
        if self.max_buys and self._buy_count >= self.max_buys:
            self.logger.info(f"Max buys reached ({self.max_buys})")
            return [self.create_hold_signal("Max buys reached")]
        
        # Vérifier l'intervalle
        should_buy, amount, reason = self.should_buy(market_data)
        
        if should_buy:
            signals.append(self.create_buy_signal(
                amount=amount,
                confidence=Decimal("0.8"),
                reason=reason,
                indicators={
                    "buy_count": self._buy_count,
                    "current_price": str(market_data.current_price),
                    "interval_hours": self.interval_hours,
                }
            ))
        else:
            signals.append(self.create_hold_signal(reason))
        
        return signals
    
    def should_buy(self, market_data: MarketData) -> tuple[bool, Decimal, str]:
        """
        Détermine s'il faut acheter
        
        DCA achète:
        - Si l'intervalle depuis le dernier achat est dépassé
        - Avec un montant fixe (+ bonus optionnel si dip)
        """
        now = datetime.utcnow()
        
        # Premier achat ?
        if self._last_buy_time is None:
            # Initialiser le prix de référence
            self._reference_price = market_data.current_price
            
            amount = self._calculate_buy_amount(market_data)
            valid, msg = self.validate_trade_size(amount)
            
            if valid:
                return True, amount, "Initial DCA buy"
            return False, Decimal("0"), msg
        
        # Vérifier l'intervalle
        time_since_last = now - self._last_buy_time
        interval_delta = timedelta(hours=self.interval_hours)
        
        if time_since_last < interval_delta:
            remaining = interval_delta - time_since_last
            hours_left = remaining.total_seconds() / 3600
            return False, Decimal("0"), f"Next buy in {hours_left:.1f}h"
        
        # C'est le moment d'acheter
        amount = self._calculate_buy_amount(market_data)
        valid, msg = self.validate_trade_size(amount)
        
        if not valid:
            return False, Decimal("0"), msg
        
        # Mettre à jour le prix de référence (moyenne mobile)
        if self._reference_price:
            self._reference_price = (
                self._reference_price * Decimal("0.9") + 
                market_data.current_price * Decimal("0.1")
            )
        
        return True, amount, f"Scheduled DCA buy (#{self._buy_count + 1})"
    
    def should_sell(self, market_data: MarketData, position: Position) -> tuple[bool, Decimal, str]:
        """
        DCA ne vend normalement pas automatiquement
        La vente est déclenchée par stop loss / take profit dans la classe de base
        """
        # Vérifier seulement les conditions de sortie configurées
        if position.stop_loss_price and market_data.current_price <= position.stop_loss_price:
            return True, position.token_amount, "Stop loss triggered"
        
        if position.take_profit_price and market_data.current_price >= position.take_profit_price:
            return True, position.token_amount, "Take profit triggered"
        
        return False, Decimal("0"), "DCA hold - no sell signal"
    
    def _calculate_buy_amount(self, market_data: MarketData) -> Decimal:
        """
        Calcule le montant à acheter, avec bonus potentiel sur les dips
        """
        base_amount = self.amount_per_buy
        
        # Bonus sur les dips
        if self.buy_on_dip_bonus > 0 and self._reference_price:
            price_change = (
                (market_data.current_price - self._reference_price) 
                / self._reference_price * 100
            )
            
            # Si le prix a baissé de plus que le seuil, appliquer le bonus
            if price_change <= -self.dip_threshold:
                dip_multiplier = abs(price_change) / self.dip_threshold
                bonus = min(self.buy_on_dip_bonus * dip_multiplier, self.buy_on_dip_bonus * 2)
                base_amount = base_amount * (1 + bonus / 100)
                self.logger.info(
                    f"Dip detected ({price_change:.1f}%), "
                    f"buying with {bonus:.1f}% bonus"
                )
        
        # Ne pas dépasser le capital disponible
        return min(base_amount, self.available_capital)
    
    def record_buy(self, amount: Decimal, tokens: Decimal, price: Decimal):
        """
        Enregistre un achat effectué
        À appeler après exécution réussie du signal
        """
        self._last_buy_time = datetime.utcnow()
        self._buy_count += 1
        
        # Mise à jour de la position (DCA accumule dans une seule position)
        if self.open_positions:
            position = self.open_positions[0]
            self.update_position_dca(position, amount, tokens)
        else:
            self.open_position(
                entry_amount=amount,
                token_amount=tokens,
                entry_price=price,
            )
    
    def get_next_buy_time(self) -> Optional[datetime]:
        """Retourne la prochaine date d'achat programmée"""
        if self._last_buy_time is None:
            return datetime.utcnow()  # Prêt à acheter
        return self._last_buy_time + timedelta(hours=self.interval_hours)
    
    def get_state(self) -> dict:
        """État DCA spécifique"""
        state = super().get_state()
        state["dca"] = {
            "amount_per_buy": str(self.amount_per_buy),
            "interval_hours": self.interval_hours,
            "buy_count": self._buy_count,
            "max_buys": self.max_buys,
            "last_buy_time": self._last_buy_time.isoformat() if self._last_buy_time else None,
            "next_buy_time": self.get_next_buy_time().isoformat() if self.get_next_buy_time() else None,
            "reference_price": str(self._reference_price) if self._reference_price else None,
        }
        return state
