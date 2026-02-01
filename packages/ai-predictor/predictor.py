"""
PricePredictor - High-level prediction interface
Provides easy-to-use methods for price and direction prediction
"""

import numpy as np
import pandas as pd
import torch
from typing import Dict, List, Optional, Tuple, Union
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from datetime import datetime, timedelta
import logging
import json

from .feature_engineering import FeatureEngineer, FeatureConfig
from .models.lstm_model import LSTMPriceModel, LSTMConfig
from .models.transformer_model import TransformerPriceModel, TransformerConfig

logger = logging.getLogger(__name__)


class Direction(Enum):
    """Price direction prediction"""
    UP = "UP"
    DOWN = "DOWN"
    NEUTRAL = "NEUTRAL"


@dataclass
class PredictionResult:
    """Result of a prediction"""
    direction: Direction
    confidence: float
    predicted_return: float
    predicted_price: Optional[float] = None
    timeframe: str = ""
    timestamp: Optional[datetime] = None
    model_type: str = ""
    
    def to_dict(self) -> Dict:
        return {
            'direction': self.direction.value,
            'confidence': self.confidence,
            'predicted_return': self.predicted_return,
            'predicted_price': self.predicted_price,
            'timeframe': self.timeframe,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
            'model_type': self.model_type
        }


@dataclass
class EnsemblePrediction:
    """Ensemble prediction from multiple models"""
    direction: Direction
    confidence: float
    predicted_return: float
    predicted_price: Optional[float]
    predictions: List[PredictionResult]
    agreement: float  # How much models agree
    
    def to_dict(self) -> Dict:
        return {
            'direction': self.direction.value,
            'confidence': self.confidence,
            'predicted_return': self.predicted_return,
            'predicted_price': self.predicted_price,
            'agreement': self.agreement,
            'individual_predictions': [p.to_dict() for p in self.predictions]
        }


class PricePredictor:
    """
    Main prediction interface for crypto price prediction.
    
    Supports:
    - Direction prediction (UP/DOWN/NEUTRAL) with confidence
    - Price prediction for various timeframes
    - Ensemble predictions from multiple models
    - Real-time and batch predictions
    """
    
    # Direction mapping
    DIRECTION_MAP = {0: Direction.DOWN, 1: Direction.NEUTRAL, 2: Direction.UP}
    
    def __init__(
        self,
        model_dir: str = './models',
        feature_config: Optional[FeatureConfig] = None,
        default_model: str = 'transformer'
    ):
        """
        Initialize predictor.
        
        Args:
            model_dir: Directory containing saved models
            feature_config: Feature engineering configuration
            default_model: Default model type ('lstm' or 'transformer')
        """
        self.model_dir = Path(model_dir)
        self.feature_engineer = FeatureEngineer(feature_config or FeatureConfig())
        self.default_model = default_model
        
        # Cache for loaded models
        self._models: Dict[str, Tuple] = {}  # token -> (model, metadata)
        
        # Device (CPU for lightweight inference)
        self.device = torch.device('cpu')
    
    def predict_direction(
        self,
        token: str,
        ohlcv: pd.DataFrame,
        timeframe: str = '24h',
        model_type: Optional[str] = None
    ) -> PredictionResult:
        """
        Predict price direction for a token.
        
        Args:
            token: Token symbol (e.g., 'BTC', 'ETH')
            ohlcv: OHLCV data (most recent data)
            timeframe: Prediction timeframe ('1h', '4h', '24h', '7d')
            model_type: 'lstm', 'transformer', or None for default
            
        Returns:
            PredictionResult with direction and confidence
        """
        model_type = model_type or self.default_model
        
        # Load or get cached model
        model, metadata = self._get_model(token, model_type)
        
        if model is None:
            logger.warning(f"No trained model found for {token}. Using untrained model.")
            # Create new model with default config
            if model_type == 'lstm':
                model = LSTMPriceModel(LSTMConfig())
            else:
                model = TransformerPriceModel(TransformerConfig())
            metadata = {}
        
        # Prepare features
        features = self._prepare_features(ohlcv)
        
        if features is None:
            return PredictionResult(
                direction=Direction.NEUTRAL,
                confidence=0.0,
                predicted_return=0.0,
                timeframe=timeframe,
                timestamp=datetime.now(),
                model_type=model_type
            )
        
        # Make prediction
        model.eval()
        with torch.no_grad():
            X = torch.FloatTensor(features).unsqueeze(0).to(self.device)
            
            if model_type == 'lstm':
                direction, confidence = model.predict_direction(X)
                output, _ = model(X)
                predicted_return = output.squeeze().item()
            else:
                direction, confidence, _ = model.predict_direction(X)
                output, _ = model(X)
                predicted_return = output.squeeze().item()
            
            direction_idx = direction.item()
            confidence_val = confidence.item()
        
        # Current price for price prediction
        current_price = ohlcv['close'].iloc[-1]
        predicted_price = current_price * (1 + predicted_return)
        
        return PredictionResult(
            direction=self.DIRECTION_MAP[direction_idx],
            confidence=confidence_val,
            predicted_return=predicted_return,
            predicted_price=predicted_price,
            timeframe=timeframe,
            timestamp=datetime.now(),
            model_type=model_type
        )
    
    def predict_price(
        self,
        token: str,
        ohlcv: pd.DataFrame,
        hours_ahead: int = 24,
        model_type: Optional[str] = None
    ) -> Tuple[float, float]:
        """
        Predict price at a future time.
        
        Args:
            token: Token symbol
            ohlcv: OHLCV data
            hours_ahead: Hours into the future
            model_type: Model type to use
            
        Returns:
            Tuple of (predicted_price, confidence)
        """
        model_type = model_type or self.default_model
        
        # Get direction prediction
        timeframe = f"{hours_ahead}h"
        result = self.predict_direction(token, ohlcv, timeframe, model_type)
        
        return result.predicted_price, result.confidence
    
    def predict_ensemble(
        self,
        token: str,
        ohlcv: pd.DataFrame,
        timeframe: str = '24h'
    ) -> EnsemblePrediction:
        """
        Make ensemble prediction using all available models.
        
        Args:
            token: Token symbol
            ohlcv: OHLCV data
            timeframe: Prediction timeframe
            
        Returns:
            EnsemblePrediction with aggregated results
        """
        predictions = []
        
        # Try both model types
        for model_type in ['lstm', 'transformer']:
            try:
                pred = self.predict_direction(token, ohlcv, timeframe, model_type)
                if pred.confidence > 0:
                    predictions.append(pred)
            except Exception as e:
                logger.warning(f"Failed to get {model_type} prediction: {e}")
        
        if not predictions:
            return EnsemblePrediction(
                direction=Direction.NEUTRAL,
                confidence=0.0,
                predicted_return=0.0,
                predicted_price=ohlcv['close'].iloc[-1],
                predictions=[],
                agreement=0.0
            )
        
        # Weight by confidence
        total_confidence = sum(p.confidence for p in predictions)
        weights = [p.confidence / total_confidence for p in predictions]
        
        # Weighted average return
        weighted_return = sum(p.predicted_return * w for p, w in zip(predictions, weights))
        
        # Direction voting (weighted)
        direction_scores = {Direction.UP: 0, Direction.DOWN: 0, Direction.NEUTRAL: 0}
        for pred, weight in zip(predictions, weights):
            direction_scores[pred.direction] += weight
        
        final_direction = max(direction_scores, key=direction_scores.get)
        
        # Agreement score (how much models agree on direction)
        agreement = direction_scores[final_direction]
        
        # Average confidence
        avg_confidence = np.mean([p.confidence for p in predictions])
        
        # Predicted price
        current_price = ohlcv['close'].iloc[-1]
        predicted_price = current_price * (1 + weighted_return)
        
        return EnsemblePrediction(
            direction=final_direction,
            confidence=avg_confidence * agreement,  # Scale by agreement
            predicted_return=weighted_return,
            predicted_price=predicted_price,
            predictions=predictions,
            agreement=agreement
        )
    
    def predict_batch(
        self,
        tokens: List[str],
        ohlcv_dict: Dict[str, pd.DataFrame],
        timeframe: str = '24h',
        use_ensemble: bool = True
    ) -> Dict[str, Union[PredictionResult, EnsemblePrediction]]:
        """
        Make predictions for multiple tokens.
        
        Args:
            tokens: List of token symbols
            ohlcv_dict: Dictionary mapping token to OHLCV data
            timeframe: Prediction timeframe
            use_ensemble: Whether to use ensemble predictions
            
        Returns:
            Dictionary mapping token to prediction
        """
        results = {}
        
        for token in tokens:
            if token not in ohlcv_dict:
                logger.warning(f"No OHLCV data for {token}")
                continue
            
            ohlcv = ohlcv_dict[token]
            
            if use_ensemble:
                results[token] = self.predict_ensemble(token, ohlcv, timeframe)
            else:
                results[token] = self.predict_direction(token, ohlcv, timeframe)
        
        return results
    
    def get_prediction_history(
        self,
        token: str,
        ohlcv: pd.DataFrame,
        n_predictions: int = 100,
        timeframe: str = '24h'
    ) -> pd.DataFrame:
        """
        Generate historical predictions for backtesting/analysis.
        
        Args:
            token: Token symbol
            ohlcv: Historical OHLCV data
            n_predictions: Number of predictions to generate
            timeframe: Prediction timeframe
            
        Returns:
            DataFrame with historical predictions
        """
        model, metadata = self._get_model(token, self.default_model)
        
        if model is None:
            logger.error(f"No model found for {token}")
            return pd.DataFrame()
        
        # Prepare full feature set
        df = self.feature_engineer.extract_all_features(ohlcv)
        feature_cols = [c for c in df.columns if c not in 
                       ['timestamp', 'open', 'high', 'low', 'close', 'volume', 'target']]
        
        # Normalize
        features = df[feature_cols].values
        features = self.feature_engineer._normalize_features(features)
        
        seq_len = self.feature_engineer.config.sequence_length
        predictions_list = []
        
        model.eval()
        
        # Generate predictions for last n points
        start_idx = max(seq_len, len(features) - n_predictions)
        
        for i in range(start_idx, len(features)):
            seq = features[i - seq_len:i]
            X = torch.FloatTensor(seq).unsqueeze(0).to(self.device)
            
            with torch.no_grad():
                if isinstance(model, LSTMPriceModel):
                    direction, confidence = model.predict_direction(X)
                    output, _ = model(X)
                else:
                    direction, confidence, _ = model.predict_direction(X)
                    output, _ = model(X)
            
            predictions_list.append({
                'index': i,
                'timestamp': df.index[i] if hasattr(df, 'index') else i,
                'close': df['close'].iloc[i],
                'predicted_return': output.squeeze().item(),
                'predicted_direction': self.DIRECTION_MAP[direction.item()].value,
                'confidence': confidence.item()
            })
        
        return pd.DataFrame(predictions_list)
    
    def _get_model(
        self,
        token: str,
        model_type: str
    ) -> Tuple[Optional[torch.nn.Module], Dict]:
        """Load or retrieve cached model"""
        cache_key = f"{token}_{model_type}"
        
        if cache_key in self._models:
            return self._models[cache_key]
        
        # Try to load model
        model_path = self.model_dir / f"{token}_{model_type}.pt"
        metadata_path = self.model_dir / f"{token}_{model_type}_metadata.json"
        
        if not model_path.exists():
            # Try generic model
            model_path = self.model_dir / f"generic_{model_type}.pt"
            metadata_path = self.model_dir / f"generic_{model_type}_metadata.json"
        
        if not model_path.exists():
            return None, {}
        
        # Load model
        try:
            checkpoint = torch.load(model_path, map_location=self.device)
            
            if model_type == 'lstm':
                config = checkpoint.get('config', LSTMConfig())
                model = LSTMPriceModel(config)
            else:
                config = checkpoint.get('config', TransformerConfig())
                model = TransformerPriceModel(config)
            
            model.load_state_dict(checkpoint['model_state_dict'])
            model.to(self.device)
            model.eval()
            
            # Load metadata
            metadata = {}
            if metadata_path.exists():
                with open(metadata_path) as f:
                    metadata = json.load(f)
            
            self._models[cache_key] = (model, metadata)
            logger.info(f"Loaded model for {token} ({model_type})")
            
            return model, metadata
            
        except Exception as e:
            logger.error(f"Failed to load model {model_path}: {e}")
            return None, {}
    
    def _prepare_features(
        self,
        ohlcv: pd.DataFrame
    ) -> Optional[np.ndarray]:
        """Prepare features for prediction"""
        try:
            # Extract features
            df = self.feature_engineer.extract_all_features(ohlcv)
            
            # Get feature columns
            feature_cols = [c for c in df.columns if c not in 
                          ['timestamp', 'open', 'high', 'low', 'close', 'volume', 'target']]
            
            # Get last sequence
            seq_len = self.feature_engineer.config.sequence_length
            
            if len(df) < seq_len:
                logger.warning(f"Not enough data: {len(df)} < {seq_len}")
                return None
            
            features = df[feature_cols].tail(seq_len).values
            
            # Normalize
            features = self.feature_engineer._normalize_features(features)
            
            return features
            
        except Exception as e:
            logger.error(f"Failed to prepare features: {e}")
            return None
    
    def clear_cache(self):
        """Clear model cache"""
        self._models.clear()
        logger.info("Model cache cleared")
    
    def list_available_models(self) -> List[Dict]:
        """List all available trained models"""
        models = []
        
        for path in self.model_dir.glob("*_metadata.json"):
            try:
                with open(path) as f:
                    metadata = json.load(f)
                    models.append(metadata)
            except:
                pass
        
        return models
