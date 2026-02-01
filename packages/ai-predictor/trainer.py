"""
Model Trainer with Backtesting
Training, validation, and backtesting pipeline for AI models
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Union
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import logging
import json
from pathlib import Path

from .feature_engineering import FeatureEngineer, FeatureConfig
from .models.lstm_model import LSTMPriceModel, LSTMTrainer, LSTMConfig
from .models.transformer_model import TransformerPriceModel, TransformerTrainer, TransformerConfig

logger = logging.getLogger(__name__)


@dataclass
class BacktestConfig:
    """Configuration for backtesting"""
    initial_capital: float = 10000.0
    position_size: float = 0.1  # 10% of capital per trade
    max_positions: int = 5
    transaction_cost: float = 0.001  # 0.1%
    slippage: float = 0.0005  # 0.05%
    stop_loss: float = 0.05  # 5%
    take_profit: float = 0.15  # 15%
    min_confidence: float = 0.6  # Minimum confidence to trade


@dataclass
class BacktestResult:
    """Results from backtesting"""
    total_return: float = 0.0
    annual_return: float = 0.0
    sharpe_ratio: float = 0.0
    max_drawdown: float = 0.0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    avg_trade_return: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    equity_curve: List[float] = field(default_factory=list)
    trades: List[Dict] = field(default_factory=list)


class ModelTrainer:
    """
    Unified trainer for LSTM and Transformer models.
    Handles data preparation, training, and evaluation.
    """
    
    def __init__(
        self,
        model_type: str = 'lstm',
        model_config: Optional[Union[LSTMConfig, TransformerConfig]] = None,
        feature_config: Optional[FeatureConfig] = None
    ):
        """
        Initialize trainer.
        
        Args:
            model_type: 'lstm' or 'transformer'
            model_config: Model configuration
            feature_config: Feature engineering configuration
        """
        self.model_type = model_type
        self.feature_engineer = FeatureEngineer(feature_config)
        
        # Initialize model based on type
        if model_type == 'lstm':
            config = model_config or LSTMConfig()
            self.model = LSTMPriceModel(config)
            self.trainer = LSTMTrainer(self.model, config)
        elif model_type == 'transformer':
            config = model_config or TransformerConfig()
            self.model = TransformerPriceModel(config)
            self.trainer = TransformerTrainer(self.model, config)
        else:
            raise ValueError(f"Unknown model type: {model_type}")
        
        self.config = config
        self.is_trained = False
        self.training_history = {}
    
    def prepare_data(
        self,
        ohlcv: pd.DataFrame,
        prediction_horizon: int = 1,
        test_size: float = 0.2,
        sentiment_data: Optional[pd.DataFrame] = None,
        onchain_data: Optional[pd.DataFrame] = None
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """
        Prepare data for training.
        
        Args:
            ohlcv: OHLCV data
            prediction_horizon: How many periods ahead to predict
            test_size: Fraction of data for testing
            sentiment_data: Optional sentiment data
            onchain_data: Optional on-chain data
            
        Returns:
            X_train, y_train, X_test, y_test
        """
        # Extract features
        df = self.feature_engineer.extract_all_features(
            ohlcv,
            sentiment_data=sentiment_data,
            onchain_data=onchain_data
        )
        
        # Prepare sequences
        X, y, feature_names = self.feature_engineer.prepare_sequences(
            df,
            target_col='close',
            prediction_horizon=prediction_horizon
        )
        
        # Update model input size
        n_features = X.shape[2]
        if self.model_type == 'lstm':
            self.model.config.input_size = n_features
        else:
            self.model.config.input_size = n_features
        
        # Split data (time series split - no shuffling)
        split_idx = int(len(X) * (1 - test_size))
        
        X_train, X_test = X[:split_idx], X[split_idx:]
        y_train, y_test = y[:split_idx], y[split_idx:]
        
        logger.info(
            f"Data prepared: {len(X_train)} train samples, "
            f"{len(X_test)} test samples, {n_features} features"
        )
        
        return X_train, y_train, X_test, y_test
    
    def train(
        self,
        X_train: np.ndarray,
        y_train: np.ndarray,
        X_val: Optional[np.ndarray] = None,
        y_val: Optional[np.ndarray] = None,
        task: str = 'regression'
    ) -> Dict[str, List[float]]:
        """
        Train the model.
        
        Args:
            X_train: Training features
            y_train: Training targets
            X_val: Validation features
            y_val: Validation targets
            task: 'regression' or 'classification'
            
        Returns:
            Training history
        """
        logger.info(f"Training {self.model_type} model...")
        
        # If no validation set, use last 20% of training data
        if X_val is None:
            split_idx = int(len(X_train) * 0.8)
            X_val = X_train[split_idx:]
            y_val = y_train[split_idx:]
            X_train = X_train[:split_idx]
            y_train = y_train[:split_idx]
        
        self.training_history = self.trainer.train(
            X_train, y_train, X_val, y_val, task=task
        )
        
        self.is_trained = True
        logger.info("Training completed")
        
        return self.training_history
    
    def evaluate(
        self,
        X_test: np.ndarray,
        y_test: np.ndarray
    ) -> Dict[str, float]:
        """
        Evaluate model on test data.
        
        Returns:
            Dictionary of metrics
        """
        import torch
        
        # Get predictions
        predictions = self.trainer.predict(X_test)
        directions, confidences = self.trainer.predict_direction(X_test)[:2]
        
        # Calculate metrics
        mse = np.mean((predictions.squeeze() - y_test) ** 2)
        mae = np.mean(np.abs(predictions.squeeze() - y_test))
        
        # Direction accuracy
        pred_dir = (predictions.squeeze() > 0).astype(int)
        true_dir = (y_test > 0).astype(int)
        direction_accuracy = np.mean(pred_dir == true_dir)
        
        # Classification accuracy (3-class)
        true_classes = self._returns_to_classes(y_test)
        class_accuracy = np.mean(directions == true_classes)
        
        # Correlation
        correlation = np.corrcoef(predictions.squeeze(), y_test)[0, 1]
        
        metrics = {
            'mse': mse,
            'rmse': np.sqrt(mse),
            'mae': mae,
            'direction_accuracy': direction_accuracy,
            'class_accuracy': class_accuracy,
            'correlation': correlation,
            'avg_confidence': np.mean(confidences)
        }
        
        logger.info(f"Evaluation: {metrics}")
        return metrics
    
    @staticmethod
    def _returns_to_classes(returns: np.ndarray, threshold: float = 0.005) -> np.ndarray:
        """Convert returns to classes"""
        classes = np.ones_like(returns, dtype=int)  # NEUTRAL
        classes[returns > threshold] = 2  # UP
        classes[returns < -threshold] = 0  # DOWN
        return classes
    
    def save(self, path: str):
        """Save model and configuration"""
        self.trainer.save(path)
    
    def load(self, path: str):
        """Load model and configuration"""
        self.trainer.load(path)
        self.is_trained = True


class Backtester:
    """
    Backtesting engine for evaluating trading strategies.
    Supports walk-forward analysis and performance metrics.
    """
    
    def __init__(self, config: Optional[BacktestConfig] = None):
        self.config = config or BacktestConfig()
    
    def run(
        self,
        trainer: ModelTrainer,
        ohlcv: pd.DataFrame,
        predictions: np.ndarray,
        confidences: np.ndarray,
        directions: np.ndarray
    ) -> BacktestResult:
        """
        Run backtest on predictions.
        
        Args:
            trainer: Trained model trainer
            ohlcv: OHLCV data aligned with predictions
            predictions: Predicted returns
            confidences: Prediction confidences
            directions: Predicted directions (0=DOWN, 1=NEUTRAL, 2=UP)
            
        Returns:
            Backtest results
        """
        capital = self.config.initial_capital
        equity_curve = [capital]
        trades = []
        position = None
        
        prices = ohlcv['close'].values[-len(predictions):]
        
        for i in range(len(predictions) - 1):
            current_price = prices[i]
            next_price = prices[i + 1]
            
            confidence = confidences[i]
            direction = directions[i]
            predicted_return = predictions[i]
            
            # Check if we should trade
            if confidence >= self.config.min_confidence and direction != 1:  # Not NEUTRAL
                # Determine trade direction
                is_long = direction == 2  # UP
                
                if position is None:
                    # Enter position
                    position_size = capital * self.config.position_size
                    entry_price = current_price * (1 + self.config.slippage)
                    entry_cost = position_size * self.config.transaction_cost
                    
                    position = {
                        'entry_price': entry_price,
                        'size': position_size,
                        'is_long': is_long,
                        'entry_idx': i,
                        'entry_cost': entry_cost
                    }
                    capital -= entry_cost
            
            # Check exit conditions if we have a position
            if position is not None:
                entry_price = position['entry_price']
                is_long = position['is_long']
                
                # Calculate current P&L
                if is_long:
                    pnl_pct = (next_price - entry_price) / entry_price
                else:
                    pnl_pct = (entry_price - next_price) / entry_price
                
                # Check stop loss / take profit
                should_exit = (
                    pnl_pct <= -self.config.stop_loss or
                    pnl_pct >= self.config.take_profit or
                    (direction == 1) or  # Exit on neutral signal
                    (is_long and direction == 0) or  # Long but now bearish
                    (not is_long and direction == 2)  # Short but now bullish
                )
                
                if should_exit:
                    # Exit position
                    exit_price = next_price * (1 - self.config.slippage if is_long else 1 + self.config.slippage)
                    exit_cost = position['size'] * self.config.transaction_cost
                    
                    # Calculate P&L
                    if is_long:
                        trade_pnl = position['size'] * (exit_price - entry_price) / entry_price
                    else:
                        trade_pnl = position['size'] * (entry_price - exit_price) / entry_price
                    
                    trade_pnl -= (position['entry_cost'] + exit_cost)
                    capital += position['size'] + trade_pnl
                    
                    trades.append({
                        'entry_idx': position['entry_idx'],
                        'exit_idx': i + 1,
                        'entry_price': entry_price,
                        'exit_price': exit_price,
                        'is_long': is_long,
                        'pnl': trade_pnl,
                        'pnl_pct': trade_pnl / position['size']
                    })
                    
                    position = None
            
            equity_curve.append(capital if position is None else 
                              capital + position['size'] * (1 + (
                                  (next_price - position['entry_price']) / position['entry_price']
                                  if position['is_long'] else
                                  (position['entry_price'] - next_price) / position['entry_price']
                              )))
        
        # Close any remaining position
        if position is not None:
            final_price = prices[-1]
            if position['is_long']:
                trade_pnl = position['size'] * (final_price - position['entry_price']) / position['entry_price']
            else:
                trade_pnl = position['size'] * (position['entry_price'] - final_price) / position['entry_price']
            trade_pnl -= position['entry_cost']
            capital += position['size'] + trade_pnl
            equity_curve[-1] = capital
        
        return self._calculate_metrics(equity_curve, trades)
    
    def _calculate_metrics(
        self,
        equity_curve: List[float],
        trades: List[Dict]
    ) -> BacktestResult:
        """Calculate backtest metrics"""
        equity = np.array(equity_curve)
        
        # Returns
        total_return = (equity[-1] - equity[0]) / equity[0]
        
        # Daily returns for Sharpe
        daily_returns = np.diff(equity) / equity[:-1]
        sharpe = np.sqrt(252) * np.mean(daily_returns) / (np.std(daily_returns) + 1e-6)
        
        # Max drawdown
        peak = np.maximum.accumulate(equity)
        drawdown = (peak - equity) / peak
        max_drawdown = np.max(drawdown)
        
        # Trade statistics
        if trades:
            pnls = [t['pnl'] for t in trades]
            winning = [p for p in pnls if p > 0]
            losing = [p for p in pnls if p <= 0]
            
            win_rate = len(winning) / len(trades) if trades else 0
            avg_win = np.mean(winning) if winning else 0
            avg_loss = np.mean(losing) if losing else 0
            profit_factor = (sum(winning) / abs(sum(losing))) if losing and sum(losing) != 0 else float('inf')
        else:
            win_rate = 0
            avg_win = 0
            avg_loss = 0
            profit_factor = 0
        
        return BacktestResult(
            total_return=total_return,
            annual_return=total_return * 252 / max(len(equity), 1),
            sharpe_ratio=sharpe,
            max_drawdown=max_drawdown,
            win_rate=win_rate,
            profit_factor=profit_factor,
            total_trades=len(trades),
            winning_trades=len([t for t in trades if t['pnl'] > 0]),
            losing_trades=len([t for t in trades if t['pnl'] <= 0]),
            avg_trade_return=np.mean([t['pnl_pct'] for t in trades]) if trades else 0,
            avg_win=avg_win,
            avg_loss=avg_loss,
            equity_curve=equity_curve,
            trades=trades
        )
    
    def walk_forward_test(
        self,
        trainer: ModelTrainer,
        ohlcv: pd.DataFrame,
        n_splits: int = 5,
        train_ratio: float = 0.7
    ) -> List[BacktestResult]:
        """
        Perform walk-forward analysis.
        
        Args:
            trainer: Model trainer
            ohlcv: Full OHLCV dataset
            n_splits: Number of train/test splits
            train_ratio: Ratio of training data in each split
            
        Returns:
            List of backtest results for each split
        """
        results = []
        n_samples = len(ohlcv)
        split_size = n_samples // n_splits
        
        for i in range(n_splits):
            # Define train/test boundaries
            train_start = i * split_size
            train_end = train_start + int(split_size * train_ratio)
            test_end = min((i + 1) * split_size, n_samples)
            
            # Prepare data for this split
            train_data = ohlcv.iloc[train_start:train_end]
            test_data = ohlcv.iloc[train_end:test_end]
            
            if len(test_data) < 10:
                continue
            
            # Train on this split
            X_train, y_train, _, _ = trainer.prepare_data(
                train_data, test_size=0.0
            )
            trainer.train(X_train, y_train)
            
            # Get predictions for test period
            X_test, y_test, _, _ = trainer.prepare_data(
                pd.concat([train_data.tail(100), test_data]), test_size=0.99
            )
            
            predictions = trainer.trainer.predict(X_test)
            directions, confidences = trainer.trainer.predict_direction(X_test)[:2]
            
            # Run backtest
            result = self.run(
                trainer, test_data,
                predictions.squeeze(), confidences, directions
            )
            results.append(result)
            
            logger.info(
                f"Split {i+1}: Return={result.total_return:.2%}, "
                f"Sharpe={result.sharpe_ratio:.2f}, "
                f"MaxDD={result.max_drawdown:.2%}"
            )
        
        return results


class TrainingPipeline:
    """
    End-to-end training pipeline.
    Combines data preparation, training, evaluation, and backtesting.
    """
    
    def __init__(
        self,
        model_type: str = 'lstm',
        model_dir: str = './models',
        feature_config: Optional[FeatureConfig] = None,
        backtest_config: Optional[BacktestConfig] = None
    ):
        self.model_type = model_type
        self.model_dir = Path(model_dir)
        self.model_dir.mkdir(parents=True, exist_ok=True)
        
        self.feature_config = feature_config
        self.backtest_config = backtest_config
        
        self.trainer: Optional[ModelTrainer] = None
        self.backtester = Backtester(backtest_config)
    
    def run(
        self,
        ohlcv: pd.DataFrame,
        token: str,
        prediction_horizon: int = 24,
        sentiment_data: Optional[pd.DataFrame] = None,
        onchain_data: Optional[pd.DataFrame] = None
    ) -> Dict:
        """
        Run full training pipeline.
        
        Args:
            ohlcv: OHLCV data
            token: Token symbol for saving
            prediction_horizon: Hours ahead to predict
            sentiment_data: Optional sentiment data
            onchain_data: Optional on-chain data
            
        Returns:
            Dictionary with training results and metrics
        """
        logger.info(f"Starting training pipeline for {token}")
        
        # Initialize trainer
        self.trainer = ModelTrainer(
            model_type=self.model_type,
            feature_config=self.feature_config
        )
        
        # Prepare data
        X_train, y_train, X_test, y_test = self.trainer.prepare_data(
            ohlcv,
            prediction_horizon=prediction_horizon,
            sentiment_data=sentiment_data,
            onchain_data=onchain_data
        )
        
        # Train model
        history = self.trainer.train(X_train, y_train)
        
        # Evaluate
        metrics = self.trainer.evaluate(X_test, y_test)
        
        # Get predictions for backtesting
        predictions = self.trainer.trainer.predict(X_test)
        directions, confidences = self.trainer.trainer.predict_direction(X_test)[:2]
        
        # Run backtest
        test_ohlcv = ohlcv.tail(len(X_test) + self.trainer.feature_engineer.config.sequence_length)
        backtest_result = self.backtester.run(
            self.trainer, test_ohlcv,
            predictions.squeeze(), confidences, directions
        )
        
        # Save model
        model_path = self.model_dir / f"{token}_{self.model_type}.pt"
        self.trainer.save(str(model_path))
        
        # Save metadata
        metadata = {
            'token': token,
            'model_type': self.model_type,
            'prediction_horizon': prediction_horizon,
            'training_date': datetime.now().isoformat(),
            'metrics': metrics,
            'backtest': {
                'total_return': backtest_result.total_return,
                'sharpe_ratio': backtest_result.sharpe_ratio,
                'max_drawdown': backtest_result.max_drawdown,
                'win_rate': backtest_result.win_rate,
                'total_trades': backtest_result.total_trades
            }
        }
        
        metadata_path = self.model_dir / f"{token}_{self.model_type}_metadata.json"
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)
        
        logger.info(f"Pipeline completed. Model saved to {model_path}")
        
        return {
            'history': history,
            'metrics': metrics,
            'backtest': backtest_result,
            'model_path': str(model_path)
        }
