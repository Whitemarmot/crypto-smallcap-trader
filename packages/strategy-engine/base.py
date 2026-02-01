"""
Strategy Engine - Base Strategy Class
Classe abstraite pour toutes les stratégies de trading
"""
from abc import ABC, abstractmethod
from decimal import Decimal
from datetime import datetime
from typing import Optional, Any
import logging
import uuid

from models import (
    Strategy, StrategyConfig, StrategyStatus,
    TradeSignal, SignalType, Position, PositionStatus,
    MarketData, ExecutionResult
)


class BaseStrategy(ABC):
    """
    Classe de base abstraite pour les stratégies de trading
    
    Toute nouvelle stratégie doit hériter de cette classe et implémenter:
    - analyze(): Analyse le marché et génère des signaux
    - should_buy(): Logique de décision d'achat
    - should_sell(): Logique de décision de vente
    """
    
    # Nom de la stratégie (à override)
    STRATEGY_TYPE: str = "base"
    STRATEGY_NAME: str = "Base Strategy"
    
    def __init__(self, config: StrategyConfig):
        """
        Initialise la stratégie
        
        Args:
            config: Configuration de la stratégie
        """
        self.config = config
        self.strategy = Strategy(config=config)
        self.logger = logging.getLogger(f"strategy.{config.strategy_id}")
        
        # Cache de données de marché
        self._market_data: Optional[MarketData] = None
        self._last_market_fetch: Optional[datetime] = None
    
    @property
    def strategy_id(self) -> str:
        return self.config.strategy_id
    
    @property
    def is_active(self) -> bool:
        return self.strategy.status == StrategyStatus.ACTIVE
    
    @property
    def open_positions(self) -> list[Position]:
        return self.strategy.open_positions
    
    @property
    def available_capital(self) -> Decimal:
        return self.strategy.available_capital
    
    # =========================================================================
    # Lifecycle Methods
    # =========================================================================
    
    def start(self):
        """Démarre la stratégie"""
        self.strategy.status = StrategyStatus.ACTIVE
        self.strategy.started_at = datetime.utcnow()
        self.logger.info(f"Strategy {self.strategy_id} started")
    
    def pause(self):
        """Met la stratégie en pause"""
        self.strategy.status = StrategyStatus.PAUSED
        self.logger.info(f"Strategy {self.strategy_id} paused")
    
    def stop(self):
        """Arrête la stratégie"""
        self.strategy.status = StrategyStatus.STOPPED
        self.logger.info(f"Strategy {self.strategy_id} stopped")
    
    def set_error(self, error: str):
        """Met la stratégie en état d'erreur"""
        self.strategy.status = StrategyStatus.ERROR
        self.strategy.last_error = error
        self.strategy.error_count += 1
        self.logger.error(f"Strategy {self.strategy_id} error: {error}")
    
    # =========================================================================
    # Abstract Methods - À implémenter par les sous-classes
    # =========================================================================
    
    @abstractmethod
    async def analyze(self, market_data: MarketData) -> list[TradeSignal]:
        """
        Analyse les données de marché et génère des signaux
        
        Args:
            market_data: Données de marché actuelles
        
        Returns:
            Liste de signaux de trading
        """
        pass
    
    @abstractmethod
    def should_buy(self, market_data: MarketData) -> tuple[bool, Decimal, str]:
        """
        Détermine s'il faut acheter
        
        Args:
            market_data: Données de marché actuelles
        
        Returns:
            (should_buy: bool, amount: Decimal, reason: str)
        """
        pass
    
    @abstractmethod
    def should_sell(self, market_data: MarketData, position: Position) -> tuple[bool, Decimal, str]:
        """
        Détermine s'il faut vendre une position
        
        Args:
            market_data: Données de marché actuelles
            position: Position à évaluer
        
        Returns:
            (should_sell: bool, amount: Decimal, reason: str)
        """
        pass
    
    # =========================================================================
    # Signal Generation Helpers
    # =========================================================================
    
    def create_signal(
        self,
        signal_type: SignalType,
        amount: Decimal,
        confidence: Decimal = Decimal("0.5"),
        reason: str = "",
        indicators: Optional[dict[str, Any]] = None,
        price_target: Optional[Decimal] = None,
        valid_seconds: int = 300,
    ) -> TradeSignal:
        """
        Crée un signal de trading
        
        Args:
            signal_type: Type de signal (BUY, SELL, HOLD, CLOSE)
            amount: Montant suggéré
            confidence: Niveau de confiance (0-1)
            reason: Explication du signal
            indicators: Indicateurs ayant contribué au signal
            price_target: Prix cible optionnel
            valid_seconds: Durée de validité en secondes
        
        Returns:
            TradeSignal créé
        """
        from datetime import timedelta
        
        signal = TradeSignal(
            signal_id=str(uuid.uuid4()),
            strategy_id=self.strategy_id,
            signal_type=signal_type,
            token_address=self.config.token_address,
            chain_id=self.config.chain_id,
            amount=amount,
            price_target=price_target,
            confidence=min(max(confidence, Decimal("0")), Decimal("1")),
            reason=reason,
            indicators=indicators or {},
            valid_until=datetime.utcnow() + timedelta(seconds=valid_seconds),
        )
        
        self.strategy.add_signal(signal)
        self.logger.info(f"Signal generated: {signal_type.value} {amount} - {reason}")
        
        return signal
    
    def create_buy_signal(
        self,
        amount: Decimal,
        confidence: Decimal = Decimal("0.5"),
        reason: str = "",
        **kwargs
    ) -> TradeSignal:
        """Helper pour créer un signal d'achat"""
        return self.create_signal(
            SignalType.BUY,
            amount=amount,
            confidence=confidence,
            reason=reason,
            **kwargs
        )
    
    def create_sell_signal(
        self,
        amount: Decimal,
        confidence: Decimal = Decimal("0.5"),
        reason: str = "",
        **kwargs
    ) -> TradeSignal:
        """Helper pour créer un signal de vente"""
        return self.create_signal(
            SignalType.SELL,
            amount=amount,
            confidence=confidence,
            reason=reason,
            **kwargs
        )
    
    def create_hold_signal(self, reason: str = "No action needed") -> TradeSignal:
        """Helper pour créer un signal HOLD"""
        return self.create_signal(
            SignalType.HOLD,
            amount=Decimal("0"),
            confidence=Decimal("1"),
            reason=reason,
        )
    
    # =========================================================================
    # Position Management
    # =========================================================================
    
    def open_position(
        self,
        entry_amount: Decimal,
        token_amount: Decimal,
        entry_price: Decimal,
        tx_hash: Optional[str] = None,
    ) -> Position:
        """
        Ouvre une nouvelle position
        
        Args:
            entry_amount: Montant investi
            token_amount: Tokens reçus
            entry_price: Prix d'entrée
            tx_hash: Hash de transaction
        
        Returns:
            Position créée
        """
        position = Position(
            position_id=str(uuid.uuid4()),
            strategy_id=self.strategy_id,
            token_address=self.config.token_address,
            token_symbol=self.config.token_symbol,
            chain_id=self.config.chain_id,
            entry_amount=entry_amount,
            token_amount=token_amount,
            entry_price=entry_price,
            cost_basis=entry_amount,
            entry_tx_hash=tx_hash,
        )
        
        # Calculer stop loss et take profit si configurés
        if self.config.stop_loss_pct:
            position.stop_loss_price = entry_price * (1 - self.config.stop_loss_pct / 100)
        
        if self.config.take_profit_pct:
            position.take_profit_price = entry_price * (1 + self.config.take_profit_pct / 100)
        
        self.strategy.positions.append(position)
        self.strategy.allocated_capital += entry_amount
        self.strategy.available_capital = self.config.total_budget - self.strategy.allocated_capital
        
        self.logger.info(
            f"Position opened: {token_amount} {self.config.token_symbol} "
            f"@ {entry_price} (invested: {entry_amount})"
        )
        
        return position
    
    def close_position(
        self,
        position: Position,
        exit_price: Decimal,
        exit_amount: Decimal,
        tx_hash: Optional[str] = None,
    ):
        """
        Ferme une position
        
        Args:
            position: Position à fermer
            exit_price: Prix de sortie
            exit_amount: Montant récupéré
            tx_hash: Hash de transaction
        """
        position.close(exit_price, exit_amount, tx_hash)
        
        # Mettre à jour les métriques
        self.strategy.record_trade(position.realized_pnl or Decimal("0"))
        self.strategy.allocated_capital -= position.entry_amount
        self.strategy.available_capital = self.config.total_budget - self.strategy.allocated_capital
        
        self.logger.info(
            f"Position closed: PnL = {position.realized_pnl} "
            f"({position.realized_pnl_pct:.2f}%)"
        )
    
    def update_position_dca(
        self,
        position: Position,
        additional_amount: Decimal,
        additional_tokens: Decimal,
    ):
        """Met à jour une position avec un achat DCA"""
        position.update_with_dca(additional_amount, additional_tokens)
        self.strategy.allocated_capital += additional_amount
        self.strategy.available_capital -= additional_amount
        
        self.logger.info(
            f"Position DCA update: +{additional_tokens} tokens "
            f"(new avg price: {position.entry_price})"
        )
    
    # =========================================================================
    # Risk Management
    # =========================================================================
    
    def check_stop_loss(self, position: Position, current_price: Decimal) -> bool:
        """Vérifie si le stop loss est atteint"""
        if position.stop_loss_price and current_price <= position.stop_loss_price:
            self.logger.warning(
                f"Stop loss triggered for position {position.position_id} "
                f"@ {current_price}"
            )
            return True
        return False
    
    def check_take_profit(self, position: Position, current_price: Decimal) -> bool:
        """Vérifie si le take profit est atteint"""
        if position.take_profit_price and current_price >= position.take_profit_price:
            self.logger.info(
                f"Take profit triggered for position {position.position_id} "
                f"@ {current_price}"
            )
            return True
        return False
    
    def check_max_drawdown(self) -> bool:
        """Vérifie si le drawdown max est atteint"""
        # Calculer le PnL total incluant positions ouvertes
        # Note: nécessite les prix actuels
        total_pnl_pct = (
            self.strategy.total_pnl / self.config.total_budget * 100
            if self.config.total_budget > 0 else Decimal("0")
        )
        
        if abs(total_pnl_pct) > self.config.max_drawdown_pct and total_pnl_pct < 0:
            self.logger.error(f"Max drawdown reached: {total_pnl_pct}%")
            return True
        return False
    
    def validate_trade_size(self, amount: Decimal) -> tuple[bool, str]:
        """
        Valide la taille d'un trade
        
        Returns:
            (is_valid: bool, reason: str)
        """
        if amount < self.config.min_trade_size:
            return False, f"Amount {amount} below minimum {self.config.min_trade_size}"
        
        if amount > self.config.max_position_size:
            return False, f"Amount {amount} exceeds max position {self.config.max_position_size}"
        
        if amount > self.available_capital:
            return False, f"Amount {amount} exceeds available capital {self.available_capital}"
        
        return True, ""
    
    # =========================================================================
    # Execution Interface
    # =========================================================================
    
    async def execute(self, market_data: MarketData) -> list[TradeSignal]:
        """
        Point d'entrée principal - exécute un cycle d'analyse
        
        Args:
            market_data: Données de marché
        
        Returns:
            Liste de signaux générés
        """
        if not self.is_active:
            self.logger.debug("Strategy not active, skipping execution")
            return []
        
        self._market_data = market_data
        self._last_market_fetch = datetime.utcnow()
        self.strategy.last_analysis_at = datetime.utcnow()
        
        try:
            # Analyser et générer des signaux
            signals = await self.analyze(market_data)
            
            # Vérifier stop loss / take profit sur positions ouvertes
            for position in self.open_positions:
                if self.check_stop_loss(position, market_data.current_price):
                    signals.append(self.create_sell_signal(
                        amount=position.token_amount,
                        confidence=Decimal("1"),
                        reason="Stop loss triggered",
                    ))
                elif self.check_take_profit(position, market_data.current_price):
                    signals.append(self.create_sell_signal(
                        amount=position.token_amount,
                        confidence=Decimal("1"),
                        reason="Take profit triggered",
                    ))
            
            # Vérifier drawdown max
            if self.check_max_drawdown():
                self.pause()
                self.set_error("Max drawdown reached")
            
            return signals
            
        except Exception as e:
            self.logger.exception(f"Error during execution: {e}")
            self.set_error(str(e))
            return []
    
    # =========================================================================
    # Serialization
    # =========================================================================
    
    def get_state(self) -> dict:
        """Retourne l'état complet de la stratégie pour persistance"""
        return {
            "strategy_id": self.strategy_id,
            "strategy_type": self.STRATEGY_TYPE,
            "status": self.strategy.status.value,
            "config": {
                "token_address": self.config.token_address,
                "token_symbol": self.config.token_symbol,
                "chain_id": self.config.chain_id,
                "total_budget": str(self.config.total_budget),
                "params": self.config.params,
            },
            "metrics": {
                "total_trades": self.strategy.total_trades,
                "winning_trades": self.strategy.winning_trades,
                "losing_trades": self.strategy.losing_trades,
                "total_pnl": str(self.strategy.total_pnl),
                "win_rate": str(self.strategy.win_rate),
                "allocated_capital": str(self.strategy.allocated_capital),
                "available_capital": str(self.strategy.available_capital),
            },
            "positions": [
                {
                    "position_id": p.position_id,
                    "status": p.status.value,
                    "entry_amount": str(p.entry_amount),
                    "token_amount": str(p.token_amount),
                    "entry_price": str(p.entry_price),
                    "opened_at": p.opened_at.isoformat(),
                }
                for p in self.strategy.positions
            ],
            "started_at": self.strategy.started_at.isoformat() if self.strategy.started_at else None,
            "last_trade_at": self.strategy.last_trade_at.isoformat() if self.strategy.last_trade_at else None,
        }
    
    def __repr__(self) -> str:
        return (
            f"<{self.STRATEGY_NAME} id={self.strategy_id} "
            f"status={self.strategy.status.value} "
            f"positions={len(self.open_positions)}>"
        )
