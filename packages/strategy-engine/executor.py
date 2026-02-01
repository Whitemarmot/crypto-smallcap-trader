"""
Strategy Executor - Gère l'exécution des stratégies
Intègre les stratégies avec le trading-engine
"""
import asyncio
import logging
from decimal import Decimal
from datetime import datetime
from typing import Optional, Type
from dataclasses import dataclass, field
import uuid
import sys
import os

# Add trading-engine to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "trading-engine"))

from models import (
    Strategy, StrategyConfig, StrategyStatus,
    TradeSignal, SignalType, Position,
    MarketData, ExecutionResult
)
from base import BaseStrategy
from strategies import STRATEGY_REGISTRY, create_strategy


@dataclass
class ExecutorConfig:
    """Configuration de l'executor"""
    # Polling
    analysis_interval_seconds: int = 60  # Intervalle d'analyse
    
    # Execution
    dry_run: bool = True  # Mode simulation
    max_concurrent_executions: int = 3
    execution_timeout_seconds: int = 120
    
    # Retry
    max_retries: int = 3
    retry_delay_seconds: int = 5
    
    # Logging
    log_level: str = "INFO"
    log_trades: bool = True


class StrategyExecutor:
    """
    Executor pour les stratégies de trading
    
    Responsabilités:
    - Gérer le cycle de vie des stratégies (start, pause, stop)
    - Orchestrer l'analyse périodique
    - Exécuter les signaux via le trading engine
    - Logger toutes les opérations
    """
    
    def __init__(
        self,
        config: Optional[ExecutorConfig] = None,
        trader: Optional[any] = None,  # Type: trading_engine.Trader
    ):
        self.config = config or ExecutorConfig()
        self.trader = trader
        
        # Strategies actives
        self._strategies: dict[str, BaseStrategy] = {}
        
        # Queue d'exécution
        self._execution_queue: asyncio.Queue = asyncio.Queue()
        self._running = False
        
        # Logging
        self.logger = logging.getLogger("strategy_executor")
        self.logger.setLevel(getattr(logging, self.config.log_level))
        
        # Execution history
        self._execution_history: list[ExecutionResult] = []
        
        # Market data provider (à injecter)
        self._market_data_provider: Optional[callable] = None
    
    # =========================================================================
    # Strategy Management
    # =========================================================================
    
    def register_strategy(
        self,
        strategy_type: str,
        config: StrategyConfig,
    ) -> BaseStrategy:
        """
        Enregistre et crée une nouvelle stratégie
        
        Args:
            strategy_type: Type de stratégie ("dca", "grid", "momentum")
            config: Configuration de la stratégie
        
        Returns:
            Instance de stratégie créée
        """
        if config.strategy_id in self._strategies:
            raise ValueError(f"Strategy {config.strategy_id} already registered")
        
        strategy = create_strategy(strategy_type, config)
        self._strategies[config.strategy_id] = strategy
        
        self.logger.info(f"Registered strategy: {strategy}")
        return strategy
    
    def unregister_strategy(self, strategy_id: str):
        """Supprime une stratégie"""
        if strategy_id in self._strategies:
            strategy = self._strategies[strategy_id]
            strategy.stop()
            del self._strategies[strategy_id]
            self.logger.info(f"Unregistered strategy: {strategy_id}")
    
    def get_strategy(self, strategy_id: str) -> Optional[BaseStrategy]:
        """Récupère une stratégie par ID"""
        return self._strategies.get(strategy_id)
    
    def list_strategies(self) -> list[BaseStrategy]:
        """Liste toutes les stratégies"""
        return list(self._strategies.values())
    
    def start_strategy(self, strategy_id: str):
        """Démarre une stratégie"""
        strategy = self._strategies.get(strategy_id)
        if strategy:
            strategy.start()
            self.logger.info(f"Started strategy: {strategy_id}")
    
    def pause_strategy(self, strategy_id: str):
        """Met en pause une stratégie"""
        strategy = self._strategies.get(strategy_id)
        if strategy:
            strategy.pause()
            self.logger.info(f"Paused strategy: {strategy_id}")
    
    def stop_strategy(self, strategy_id: str):
        """Arrête une stratégie"""
        strategy = self._strategies.get(strategy_id)
        if strategy:
            strategy.stop()
            self.logger.info(f"Stopped strategy: {strategy_id}")
    
    # =========================================================================
    # Market Data
    # =========================================================================
    
    def set_market_data_provider(self, provider: callable):
        """
        Configure le fournisseur de données de marché
        
        Args:
            provider: Async function(token_address, chain_id) -> MarketData
        """
        self._market_data_provider = provider
    
    async def fetch_market_data(
        self,
        token_address: str,
        chain_id: int,
    ) -> Optional[MarketData]:
        """
        Récupère les données de marché pour un token
        """
        if self._market_data_provider:
            try:
                return await self._market_data_provider(token_address, chain_id)
            except Exception as e:
                self.logger.error(f"Failed to fetch market data: {e}")
                return None
        
        # Données de marché simulées (pour tests)
        self.logger.warning("No market data provider, using mock data")
        return self._mock_market_data(token_address, chain_id)
    
    def _mock_market_data(self, token_address: str, chain_id: int) -> MarketData:
        """Données de marché simulées pour tests"""
        import random
        
        base_price = Decimal("100")
        volatility = Decimal("0.02")
        
        return MarketData(
            token_address=token_address,
            chain_id=chain_id,
            current_price=base_price * (1 + Decimal(str(random.uniform(-0.05, 0.05)))),
            rsi_14=Decimal(str(random.uniform(30, 70))),
            macd_line=Decimal(str(random.uniform(-1, 1))),
            macd_signal=Decimal(str(random.uniform(-1, 1))),
            sma_20=base_price * Decimal("0.98"),
            sma_50=base_price * Decimal("0.95"),
        )
    
    # =========================================================================
    # Main Loop
    # =========================================================================
    
    async def start(self):
        """Démarre l'executor et la boucle principale"""
        self._running = True
        self.logger.info("Strategy executor started")
        
        # Démarrer le consumer d'exécution
        consumer_task = asyncio.create_task(self._execution_consumer())
        
        # Boucle d'analyse principale
        try:
            while self._running:
                await self._analyze_all_strategies()
                await asyncio.sleep(self.config.analysis_interval_seconds)
        finally:
            consumer_task.cancel()
            self.logger.info("Strategy executor stopped")
    
    async def stop(self):
        """Arrête l'executor"""
        self._running = False
        self.logger.info("Stopping strategy executor...")
    
    async def _analyze_all_strategies(self):
        """Analyse toutes les stratégies actives"""
        active_strategies = [
            s for s in self._strategies.values() 
            if s.is_active
        ]
        
        if not active_strategies:
            self.logger.debug("No active strategies to analyze")
            return
        
        self.logger.debug(f"Analyzing {len(active_strategies)} strategies")
        
        for strategy in active_strategies:
            try:
                # Récupérer les données de marché
                market_data = await self.fetch_market_data(
                    strategy.config.token_address,
                    strategy.config.chain_id,
                )
                
                if not market_data:
                    self.logger.warning(
                        f"No market data for {strategy.config.token_symbol}, skipping"
                    )
                    continue
                
                # Exécuter l'analyse
                signals = await strategy.execute(market_data)
                
                # Mettre les signaux actionnables dans la queue
                for signal in signals:
                    if signal.is_actionable:
                        await self._execution_queue.put((strategy, signal, market_data))
                        
            except Exception as e:
                self.logger.exception(f"Error analyzing strategy {strategy.strategy_id}: {e}")
                strategy.set_error(str(e))
    
    async def _execution_consumer(self):
        """Consomme et exécute les signaux de la queue"""
        while self._running:
            try:
                # Attendre un signal avec timeout
                try:
                    item = await asyncio.wait_for(
                        self._execution_queue.get(),
                        timeout=1.0
                    )
                except asyncio.TimeoutError:
                    continue
                
                strategy, signal, market_data = item
                
                # Exécuter le signal
                result = await self._execute_signal(strategy, signal, market_data)
                
                # Logger le résultat
                self._execution_history.append(result)
                
                if result.success:
                    self.logger.info(
                        f"Signal executed: {signal.signal_type.value} "
                        f"{signal.amount} @ {result.executed_price}"
                    )
                else:
                    self.logger.error(f"Signal failed: {result.error}")
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.exception(f"Error in execution consumer: {e}")
    
    # =========================================================================
    # Signal Execution
    # =========================================================================
    
    async def _execute_signal(
        self,
        strategy: BaseStrategy,
        signal: TradeSignal,
        market_data: MarketData,
    ) -> ExecutionResult:
        """
        Exécute un signal de trading
        """
        start_time = datetime.utcnow()
        
        # Mode dry run
        if self.config.dry_run:
            return self._simulate_execution(signal, market_data, start_time)
        
        # Exécution réelle via trading engine
        if not self.trader:
            return ExecutionResult(
                signal=signal,
                success=False,
                error="No trader configured",
                error_code="NO_TRADER",
            )
        
        try:
            if signal.signal_type == SignalType.BUY:
                result = await self._execute_buy(strategy, signal, market_data)
            elif signal.signal_type in (SignalType.SELL, SignalType.CLOSE):
                result = await self._execute_sell(strategy, signal, market_data)
            else:
                return ExecutionResult(
                    signal=signal,
                    success=False,
                    error=f"Unknown signal type: {signal.signal_type}",
                )
            
            # Mettre à jour le signal
            signal.executed = True
            signal.executed_at = datetime.utcnow()
            signal.tx_hash = result.tx_hash
            
            return result
            
        except Exception as e:
            return ExecutionResult(
                signal=signal,
                success=False,
                error=str(e),
                error_code="EXECUTION_ERROR",
            )
    
    async def _execute_buy(
        self,
        strategy: BaseStrategy,
        signal: TradeSignal,
        market_data: MarketData,
    ) -> ExecutionResult:
        """Exécute un achat"""
        # Import depuis trading-engine
        try:
            from trader import Trader as TradingEngine
            from models import TradeOrder, TradeDirection
        except ImportError:
            self.logger.error("trading-engine not found")
            return ExecutionResult(
                signal=signal,
                success=False,
                error="trading-engine module not found",
            )
        
        # Créer l'ordre
        order = TradeOrder(
            id=str(uuid.uuid4()),
            wallet_address=self.trader.wallet_address,
            chain_id=signal.chain_id,
            src_token=...,  # Token de base (USDC, ETH, etc.)
            dst_token=...,  # Token cible
            src_amount=int(signal.amount * 10**18),  # Convertir en wei
            slippage=strategy.config.max_slippage,
            direction=TradeDirection.BUY,
        )
        
        # Exécuter via trader
        trade_result = await self.trader.execute_swap(order)
        
        if trade_result.success:
            # Mettre à jour la position dans la stratégie
            tokens_received = Decimal(str(trade_result.dst_amount_received)) / Decimal(10**18)
            strategy.open_position(
                entry_amount=signal.amount,
                token_amount=tokens_received,
                entry_price=market_data.current_price,
                tx_hash=trade_result.tx_hash,
            )
        
        return ExecutionResult(
            signal=signal,
            success=trade_result.success,
            tx_hash=trade_result.tx_hash,
            executed_amount=signal.amount,
            executed_price=market_data.current_price,
            gas_used=trade_result.gas_used,
            gas_cost=Decimal(str(trade_result.total_gas_cost)) / Decimal(10**18),
            execution_time_ms=trade_result.execution_time_ms,
            error=trade_result.error,
        )
    
    async def _execute_sell(
        self,
        strategy: BaseStrategy,
        signal: TradeSignal,
        market_data: MarketData,
    ) -> ExecutionResult:
        """Exécute une vente"""
        # Trouver la position à vendre
        positions = strategy.open_positions
        if not positions:
            return ExecutionResult(
                signal=signal,
                success=False,
                error="No open position to sell",
            )
        
        position = positions[0]  # Prend la première position
        
        # Simuler l'exécution (à implémenter avec trading-engine)
        return ExecutionResult(
            signal=signal,
            success=True,
            tx_hash=f"0x{uuid.uuid4().hex}",
            executed_amount=signal.amount,
            executed_price=market_data.current_price,
        )
    
    def _simulate_execution(
        self,
        signal: TradeSignal,
        market_data: MarketData,
        start_time: datetime,
    ) -> ExecutionResult:
        """Simule l'exécution d'un signal (dry run)"""
        import random
        
        # Simuler un slippage aléatoire
        slippage = Decimal(str(random.uniform(0, 0.5)))
        executed_price = market_data.current_price * (1 + slippage / 100)
        
        self.logger.info(
            f"[DRY RUN] {signal.signal_type.value.upper()} "
            f"{signal.amount} @ {executed_price}"
        )
        
        signal.executed = True
        signal.executed_at = datetime.utcnow()
        
        return ExecutionResult(
            signal=signal,
            success=True,
            tx_hash=f"DRY_RUN_{uuid.uuid4().hex[:16]}",
            executed_amount=signal.amount,
            executed_price=executed_price,
            slippage_actual=slippage,
            execution_time_ms=int((datetime.utcnow() - start_time).total_seconds() * 1000),
        )
    
    # =========================================================================
    # Reporting & Stats
    # =========================================================================
    
    def get_stats(self) -> dict:
        """Retourne les statistiques de l'executor"""
        total_executions = len(self._execution_history)
        successful = sum(1 for e in self._execution_history if e.success)
        
        return {
            "running": self._running,
            "strategies_count": len(self._strategies),
            "active_strategies": len([s for s in self._strategies.values() if s.is_active]),
            "total_executions": total_executions,
            "successful_executions": successful,
            "failed_executions": total_executions - successful,
            "success_rate": successful / total_executions if total_executions > 0 else 0,
            "dry_run_mode": self.config.dry_run,
        }
    
    def get_execution_history(self, limit: int = 50) -> list[dict]:
        """Retourne l'historique des exécutions"""
        return [
            {
                "signal_id": e.signal.signal_id,
                "signal_type": e.signal.signal_type.value,
                "success": e.success,
                "amount": str(e.executed_amount),
                "price": str(e.executed_price),
                "tx_hash": e.tx_hash,
                "executed_at": e.executed_at.isoformat(),
                "error": e.error,
            }
            for e in self._execution_history[-limit:]
        ]


# =============================================================================
# CLI / Example
# =============================================================================

async def main():
    """Example usage"""
    # Configuration
    executor_config = ExecutorConfig(
        dry_run=True,
        analysis_interval_seconds=10,
    )
    
    executor = StrategyExecutor(config=executor_config)
    
    # Créer une stratégie DCA
    dca_config = StrategyConfig(
        strategy_id="dca_eth_001",
        strategy_type="dca",
        name="DCA ETH Daily",
        token_address="0x...",
        token_symbol="SHITCOIN",
        chain_id=1,
        total_budget=Decimal("1000"),
        params={
            "amount_per_buy": 50,
            "interval_hours": 24,
        }
    )
    
    dca_strategy = executor.register_strategy("dca", dca_config)
    executor.start_strategy(dca_strategy.strategy_id)
    
    # Créer une stratégie Grid
    grid_config = StrategyConfig(
        strategy_id="grid_eth_001",
        strategy_type="grid",
        name="Grid ETH Range",
        token_address="0x...",
        token_symbol="MEMECOIN",
        chain_id=1,
        total_budget=Decimal("2000"),
        params={
            "lower_price": 90,
            "upper_price": 110,
            "num_grids": 10,
        }
    )
    
    grid_strategy = executor.register_strategy("grid", grid_config)
    executor.start_strategy(grid_strategy.strategy_id)
    
    print(f"Registered strategies: {[s.strategy_id for s in executor.list_strategies()]}")
    
    # Exécuter pendant quelques cycles
    try:
        await asyncio.wait_for(executor.start(), timeout=35)
    except asyncio.TimeoutError:
        await executor.stop()
    
    # Stats
    print("\n=== Executor Stats ===")
    for key, value in executor.get_stats().items():
        print(f"  {key}: {value}")
    
    print("\n=== Execution History ===")
    for exec in executor.get_execution_history():
        print(f"  {exec['signal_type']}: {exec['amount']} @ {exec['price']} - {exec['tx_hash'][:20]}...")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
