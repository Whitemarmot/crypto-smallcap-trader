"""
Grid Trading Strategy
Ordres d'achat/vente échelonnés sur une plage de prix
"""
from decimal import Decimal
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from enum import Enum

from base import BaseStrategy
from models import (
    StrategyConfig, TradeSignal, SignalType,
    Position, MarketData
)


class GridLevel(Enum):
    """Type de niveau de grille"""
    BUY = "buy"
    SELL = "sell"


@dataclass
class GridOrder:
    """Représente un niveau de la grille"""
    level_id: str
    price: Decimal
    order_type: GridLevel
    amount: Decimal
    filled: bool = False
    filled_at: Optional[datetime] = None
    tx_hash: Optional[str] = None


class GridStrategy(BaseStrategy):
    """
    Grid Trading Strategy
    
    Principe:
    - Place des ordres d'achat à intervalles réguliers sous le prix actuel
    - Place des ordres de vente à intervalles réguliers au-dessus
    - Profite des oscillations de prix dans un range
    
    Paramètres (dans config.params):
    - lower_price: Prix minimum de la grille
    - upper_price: Prix maximum de la grille
    - num_grids: Nombre de niveaux de grille (défaut: 10)
    - amount_per_grid: Montant par niveau (auto-calculé si non spécifié)
    - grid_type: "arithmetic" ou "geometric" (défaut: arithmetic)
    """
    
    STRATEGY_TYPE = "grid"
    STRATEGY_NAME = "Grid Trading"
    
    def __init__(self, config: StrategyConfig):
        super().__init__(config)
        
        # Paramètres de grille
        self.lower_price = Decimal(str(config.params.get("lower_price", 0)))
        self.upper_price = Decimal(str(config.params.get("upper_price", 0)))
        self.num_grids = config.params.get("num_grids", 10)
        self.grid_type = config.params.get("grid_type", "arithmetic")
        
        # Montant par niveau (auto-calculé si non spécifié)
        amount = config.params.get("amount_per_grid")
        if amount:
            self.amount_per_grid = Decimal(str(amount))
        else:
            # Diviser le budget total entre les niveaux d'achat (moitié des grids)
            buy_grids = self.num_grids // 2
            self.amount_per_grid = config.total_budget / buy_grids if buy_grids > 0 else Decimal("0")
        
        # Grille générée
        self._grid_levels: list[GridOrder] = []
        self._initialized = False
        self._initial_price: Optional[Decimal] = None
    
    def initialize_grid(self, current_price: Decimal):
        """
        Initialise la grille autour du prix actuel
        
        La grille est divisée en:
        - Niveaux d'ACHAT sous le prix actuel
        - Niveaux de VENTE au-dessus du prix actuel
        """
        if self._initialized:
            return
        
        self._initial_price = current_price
        self._grid_levels = []
        
        # Auto-calcul des bornes si non spécifiées
        if self.lower_price == 0:
            self.lower_price = current_price * Decimal("0.8")  # -20%
        if self.upper_price == 0:
            self.upper_price = current_price * Decimal("1.2")  # +20%
        
        # Validation
        if self.lower_price >= self.upper_price:
            raise ValueError("lower_price must be less than upper_price")
        if self.lower_price >= current_price or current_price >= self.upper_price:
            self.logger.warning(
                f"Current price {current_price} outside grid range "
                f"[{self.lower_price}, {self.upper_price}]"
            )
        
        # Générer les niveaux de prix
        if self.grid_type == "geometric":
            prices = self._generate_geometric_levels()
        else:
            prices = self._generate_arithmetic_levels()
        
        # Créer les ordres de grille
        for i, price in enumerate(prices):
            if price < current_price:
                order_type = GridLevel.BUY
            else:
                order_type = GridLevel.SELL
            
            self._grid_levels.append(GridOrder(
                level_id=f"grid_{i}",
                price=price,
                order_type=order_type,
                amount=self.amount_per_grid,
            ))
        
        self._initialized = True
        self.logger.info(
            f"Grid initialized: {len(self._grid_levels)} levels "
            f"from {self.lower_price} to {self.upper_price}"
        )
    
    def _generate_arithmetic_levels(self) -> list[Decimal]:
        """Génère des niveaux espacés de façon linéaire"""
        step = (self.upper_price - self.lower_price) / (self.num_grids - 1)
        return [
            self.lower_price + step * i 
            for i in range(self.num_grids)
        ]
    
    def _generate_geometric_levels(self) -> list[Decimal]:
        """Génère des niveaux espacés de façon géométrique (% constant)"""
        import math
        ratio = (float(self.upper_price) / float(self.lower_price)) ** (1 / (self.num_grids - 1))
        return [
            self.lower_price * Decimal(str(ratio ** i))
            for i in range(self.num_grids)
        ]
    
    async def analyze(self, market_data: MarketData) -> list[TradeSignal]:
        """
        Analyse Grid - vérifie les niveaux touchés
        """
        # Initialiser la grille si nécessaire
        if not self._initialized:
            self.initialize_grid(market_data.current_price)
        
        signals = []
        current_price = market_data.current_price
        
        # Vérifier chaque niveau de grille
        for level in self._grid_levels:
            if level.filled:
                continue
            
            # Niveau d'achat touché (prix descend sous le niveau)
            if level.order_type == GridLevel.BUY and current_price <= level.price:
                should_buy, amount, reason = self.should_buy(market_data, level)
                if should_buy:
                    signals.append(self.create_buy_signal(
                        amount=amount,
                        confidence=Decimal("0.9"),
                        reason=reason,
                        price_target=level.price,
                        indicators={
                            "grid_level": level.level_id,
                            "grid_price": str(level.price),
                            "grid_type": "buy",
                        }
                    ))
            
            # Niveau de vente touché (prix monte au-dessus du niveau)
            elif level.order_type == GridLevel.SELL and current_price >= level.price:
                for position in self.open_positions:
                    should_sell, amount, reason = self.should_sell(market_data, position, level)
                    if should_sell:
                        signals.append(self.create_sell_signal(
                            amount=amount,
                            confidence=Decimal("0.9"),
                            reason=reason,
                            price_target=level.price,
                            indicators={
                                "grid_level": level.level_id,
                                "grid_price": str(level.price),
                                "grid_type": "sell",
                            }
                        ))
        
        if not signals:
            signals.append(self.create_hold_signal(
                f"Price {current_price} - no grid levels triggered"
            ))
        
        return signals
    
    def should_buy(self, market_data: MarketData, level: Optional[GridOrder] = None) -> tuple[bool, Decimal, str]:
        """
        Détermine s'il faut acheter à ce niveau de grille
        """
        if level is None:
            return False, Decimal("0"), "No grid level specified"
        
        if level.filled:
            return False, Decimal("0"), f"Level {level.level_id} already filled"
        
        if level.order_type != GridLevel.BUY:
            return False, Decimal("0"), f"Level {level.level_id} is not a buy level"
        
        amount = level.amount
        valid, msg = self.validate_trade_size(amount)
        
        if not valid:
            return False, Decimal("0"), msg
        
        return True, amount, f"Grid buy at level {level.price}"
    
    def should_sell(
        self, 
        market_data: MarketData, 
        position: Position,
        level: Optional[GridOrder] = None
    ) -> tuple[bool, Decimal, str]:
        """
        Détermine s'il faut vendre à ce niveau de grille
        """
        if level is None:
            # Vérifier stop loss / take profit classiques
            if position.stop_loss_price and market_data.current_price <= position.stop_loss_price:
                return True, position.token_amount, "Stop loss triggered"
            if position.take_profit_price and market_data.current_price >= position.take_profit_price:
                return True, position.token_amount, "Take profit triggered"
            return False, Decimal("0"), "No sell condition met"
        
        if level.filled:
            return False, Decimal("0"), f"Sell level {level.level_id} already filled"
        
        if level.order_type != GridLevel.SELL:
            return False, Decimal("0"), f"Level {level.level_id} is not a sell level"
        
        # Calculer combien vendre (proportionnel au niveau)
        tokens_to_sell = position.token_amount / len([
            l for l in self._grid_levels 
            if l.order_type == GridLevel.SELL and not l.filled
        ])
        
        return True, tokens_to_sell, f"Grid sell at level {level.price}"
    
    def mark_level_filled(self, level_id: str, tx_hash: Optional[str] = None):
        """Marque un niveau comme rempli"""
        for level in self._grid_levels:
            if level.level_id == level_id:
                level.filled = True
                level.filled_at = datetime.utcnow()
                level.tx_hash = tx_hash
                
                # Inverser le type pour le prochain cycle
                if level.order_type == GridLevel.BUY:
                    level.order_type = GridLevel.SELL
                else:
                    level.order_type = GridLevel.BUY
                level.filled = False  # Prêt pour le prochain cycle
                
                self.logger.info(f"Grid level {level_id} filled, flipped to {level.order_type.value}")
                break
    
    def get_unfilled_buy_levels(self) -> list[GridOrder]:
        """Retourne les niveaux d'achat non remplis"""
        return [
            l for l in self._grid_levels 
            if l.order_type == GridLevel.BUY and not l.filled
        ]
    
    def get_unfilled_sell_levels(self) -> list[GridOrder]:
        """Retourne les niveaux de vente non remplis"""
        return [
            l for l in self._grid_levels 
            if l.order_type == GridLevel.SELL and not l.filled
        ]
    
    def calculate_grid_profit(self) -> Decimal:
        """
        Calcule le profit potentiel d'un cycle complet de grille
        """
        if not self._grid_levels:
            return Decimal("0")
        
        # Profit = différence entre niveaux de vente et d'achat
        buy_levels = sorted(
            [l for l in self._grid_levels if l.order_type == GridLevel.BUY],
            key=lambda x: x.price
        )
        sell_levels = sorted(
            [l for l in self._grid_levels if l.order_type == GridLevel.SELL],
            key=lambda x: x.price
        )
        
        if not buy_levels or not sell_levels:
            return Decimal("0")
        
        # Profit moyen par cycle
        avg_buy = sum(l.price for l in buy_levels) / len(buy_levels)
        avg_sell = sum(l.price for l in sell_levels) / len(sell_levels)
        
        return (avg_sell - avg_buy) / avg_buy * 100  # En pourcentage
    
    def get_state(self) -> dict:
        """État Grid spécifique"""
        state = super().get_state()
        state["grid"] = {
            "lower_price": str(self.lower_price),
            "upper_price": str(self.upper_price),
            "num_grids": self.num_grids,
            "grid_type": self.grid_type,
            "amount_per_grid": str(self.amount_per_grid),
            "initialized": self._initialized,
            "initial_price": str(self._initial_price) if self._initial_price else None,
            "potential_profit_pct": str(self.calculate_grid_profit()),
            "levels": [
                {
                    "level_id": l.level_id,
                    "price": str(l.price),
                    "type": l.order_type.value,
                    "amount": str(l.amount),
                    "filled": l.filled,
                }
                for l in self._grid_levels
            ],
            "unfilled_buys": len(self.get_unfilled_buy_levels()),
            "unfilled_sells": len(self.get_unfilled_sell_levels()),
        }
        return state
