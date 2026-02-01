"""
Feature Engineering for Crypto Price Prediction
Extracts: price, volume, RSI, MACD, social sentiment, on-chain metrics
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class FeatureConfig:
    """Configuration for feature extraction"""
    # Price features
    price_windows: List[int] = None  # SMA/EMA windows
    returns_windows: List[int] = None  # Return calculation windows
    
    # Volume features
    volume_windows: List[int] = None
    
    # Technical indicators
    rsi_period: int = 14
    macd_fast: int = 12
    macd_slow: int = 26
    macd_signal: int = 9
    bb_period: int = 20
    bb_std: float = 2.0
    
    # Sequence length for models
    sequence_length: int = 60
    
    def __post_init__(self):
        self.price_windows = self.price_windows or [7, 14, 30, 50]
        self.returns_windows = self.returns_windows or [1, 3, 7, 14]
        self.volume_windows = self.volume_windows or [7, 14, 30]


class FeatureEngineer:
    """
    Extract features from OHLCV data for ML models.
    Supports technical analysis, sentiment, and on-chain metrics.
    """
    
    def __init__(self, config: Optional[FeatureConfig] = None):
        self.config = config or FeatureConfig()
        self.feature_names: List[str] = []
        
    def extract_all_features(
        self,
        ohlcv: pd.DataFrame,
        sentiment_data: Optional[pd.DataFrame] = None,
        onchain_data: Optional[pd.DataFrame] = None
    ) -> pd.DataFrame:
        """
        Extract all features from available data sources.
        
        Args:
            ohlcv: DataFrame with columns [timestamp, open, high, low, close, volume]
            sentiment_data: Optional sentiment scores
            onchain_data: Optional on-chain metrics
            
        Returns:
            DataFrame with all features
        """
        df = ohlcv.copy()
        df = self._ensure_columns(df)
        
        # Extract feature groups
        df = self._add_price_features(df)
        df = self._add_volume_features(df)
        df = self._add_technical_indicators(df)
        df = self._add_volatility_features(df)
        df = self._add_momentum_features(df)
        
        # Add external data if available
        if sentiment_data is not None:
            df = self._add_sentiment_features(df, sentiment_data)
        
        if onchain_data is not None:
            df = self._add_onchain_features(df, onchain_data)
        
        # Store feature names (excluding target columns)
        self.feature_names = [c for c in df.columns if c not in 
                             ['timestamp', 'open', 'high', 'low', 'close', 'volume', 'target']]
        
        return df
    
    def _ensure_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """Ensure required columns exist and are properly formatted"""
        required = ['open', 'high', 'low', 'close', 'volume']
        
        # Handle different column name formats
        col_map = {}
        for col in df.columns:
            col_lower = col.lower()
            if col_lower in required:
                col_map[col] = col_lower
        
        df = df.rename(columns=col_map)
        
        for col in required:
            if col not in df.columns:
                raise ValueError(f"Missing required column: {col}")
        
        return df
    
    def _add_price_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add price-based features"""
        close = df['close']
        
        # Simple Moving Averages
        for window in self.config.price_windows:
            df[f'sma_{window}'] = close.rolling(window=window).mean()
            df[f'ema_{window}'] = close.ewm(span=window, adjust=False).mean()
            
            # Price relative to MA
            df[f'close_to_sma_{window}'] = close / df[f'sma_{window}'] - 1
        
        # Returns at different horizons
        for window in self.config.returns_windows:
            df[f'return_{window}d'] = close.pct_change(periods=window)
            df[f'log_return_{window}d'] = np.log(close / close.shift(window))
        
        # High-Low spread
        df['hl_spread'] = (df['high'] - df['low']) / df['close']
        
        # Open-Close spread
        df['oc_spread'] = (df['close'] - df['open']) / df['open']
        
        # Gap (from previous close)
        df['gap'] = (df['open'] - df['close'].shift(1)) / df['close'].shift(1)
        
        return df
    
    def _add_volume_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add volume-based features"""
        volume = df['volume']
        
        # Volume moving averages
        for window in self.config.volume_windows:
            df[f'volume_sma_{window}'] = volume.rolling(window=window).mean()
            df[f'volume_ratio_{window}'] = volume / df[f'volume_sma_{window}']
        
        # Volume change
        df['volume_change'] = volume.pct_change()
        
        # Volume-weighted price
        df['vwap'] = (df['close'] * df['volume']).rolling(20).sum() / df['volume'].rolling(20).sum()
        df['close_to_vwap'] = df['close'] / df['vwap'] - 1
        
        # On-Balance Volume (OBV)
        df['obv'] = (np.sign(df['close'].diff()) * df['volume']).cumsum()
        df['obv_change'] = df['obv'].pct_change(periods=5)
        
        return df
    
    def _add_technical_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add technical analysis indicators"""
        close = df['close']
        high = df['high']
        low = df['low']
        
        # RSI
        df['rsi'] = self._calculate_rsi(close, self.config.rsi_period)
        df['rsi_oversold'] = (df['rsi'] < 30).astype(float)
        df['rsi_overbought'] = (df['rsi'] > 70).astype(float)
        
        # MACD
        macd, signal, hist = self._calculate_macd(
            close,
            self.config.macd_fast,
            self.config.macd_slow,
            self.config.macd_signal
        )
        df['macd'] = macd
        df['macd_signal'] = signal
        df['macd_hist'] = hist
        df['macd_cross_up'] = ((macd > signal) & (macd.shift(1) <= signal.shift(1))).astype(float)
        df['macd_cross_down'] = ((macd < signal) & (macd.shift(1) >= signal.shift(1))).astype(float)
        
        # Bollinger Bands
        bb_mid = close.rolling(window=self.config.bb_period).mean()
        bb_std = close.rolling(window=self.config.bb_period).std()
        df['bb_upper'] = bb_mid + (bb_std * self.config.bb_std)
        df['bb_lower'] = bb_mid - (bb_std * self.config.bb_std)
        df['bb_width'] = (df['bb_upper'] - df['bb_lower']) / bb_mid
        df['bb_position'] = (close - df['bb_lower']) / (df['bb_upper'] - df['bb_lower'])
        
        # Stochastic Oscillator
        lowest_low = low.rolling(window=14).min()
        highest_high = high.rolling(window=14).max()
        df['stoch_k'] = 100 * (close - lowest_low) / (highest_high - lowest_low)
        df['stoch_d'] = df['stoch_k'].rolling(window=3).mean()
        
        # Average True Range (ATR)
        df['atr'] = self._calculate_atr(high, low, close, period=14)
        df['atr_ratio'] = df['atr'] / close
        
        return df
    
    def _add_volatility_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add volatility-based features"""
        returns = df['close'].pct_change()
        
        # Rolling volatility
        for window in [7, 14, 30]:
            df[f'volatility_{window}d'] = returns.rolling(window=window).std() * np.sqrt(252)
        
        # Parkinson volatility (using high-low)
        for window in [7, 14]:
            hl_ratio = np.log(df['high'] / df['low'])
            df[f'parkinson_vol_{window}d'] = np.sqrt(
                (1 / (4 * np.log(2))) * (hl_ratio ** 2).rolling(window=window).mean()
            ) * np.sqrt(252)
        
        # Volatility ratio
        df['vol_ratio_7_30'] = df['volatility_7d'] / df['volatility_30d']
        
        return df
    
    def _add_momentum_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add momentum indicators"""
        close = df['close']
        
        # Rate of Change (ROC)
        for period in [5, 10, 20]:
            df[f'roc_{period}'] = (close - close.shift(period)) / close.shift(period) * 100
        
        # Momentum
        df['momentum_10'] = close - close.shift(10)
        df['momentum_20'] = close - close.shift(20)
        
        # Williams %R
        highest_high = df['high'].rolling(14).max()
        lowest_low = df['low'].rolling(14).min()
        df['williams_r'] = -100 * (highest_high - close) / (highest_high - lowest_low)
        
        # Commodity Channel Index (CCI)
        typical_price = (df['high'] + df['low'] + df['close']) / 3
        sma_tp = typical_price.rolling(20).mean()
        mad = typical_price.rolling(20).apply(lambda x: np.abs(x - x.mean()).mean())
        df['cci'] = (typical_price - sma_tp) / (0.015 * mad)
        
        return df
    
    def _add_sentiment_features(
        self,
        df: pd.DataFrame,
        sentiment_data: pd.DataFrame
    ) -> pd.DataFrame:
        """Add social sentiment features"""
        # Merge sentiment on timestamp
        if 'timestamp' in sentiment_data.columns:
            df = df.merge(sentiment_data, on='timestamp', how='left')
        
        # Expected columns in sentiment_data
        sentiment_cols = ['sentiment_score', 'social_volume', 'bullish_ratio']
        
        for col in sentiment_cols:
            if col in df.columns:
                # Forward fill missing values
                df[col] = df[col].ffill()
                
                # Add rolling sentiment features
                df[f'{col}_ma_7'] = df[col].rolling(7).mean()
                df[f'{col}_change'] = df[col].pct_change()
        
        return df
    
    def _add_onchain_features(
        self,
        df: pd.DataFrame,
        onchain_data: pd.DataFrame
    ) -> pd.DataFrame:
        """Add on-chain metrics"""
        # Merge on-chain data on timestamp
        if 'timestamp' in onchain_data.columns:
            df = df.merge(onchain_data, on='timestamp', how='left')
        
        # Expected on-chain columns
        onchain_cols = [
            'active_addresses',
            'transaction_count',
            'exchange_inflow',
            'exchange_outflow',
            'whale_transactions',
            'hash_rate',
            'mining_difficulty'
        ]
        
        for col in onchain_cols:
            if col in df.columns:
                df[col] = df[col].ffill()
                
                # Normalize and add changes
                df[f'{col}_zscore'] = (df[col] - df[col].rolling(30).mean()) / df[col].rolling(30).std()
                df[f'{col}_change'] = df[col].pct_change()
        
        # Derived metrics
        if 'exchange_inflow' in df.columns and 'exchange_outflow' in df.columns:
            df['exchange_netflow'] = df['exchange_inflow'] - df['exchange_outflow']
            df['exchange_flow_ratio'] = df['exchange_inflow'] / (df['exchange_outflow'] + 1)
        
        return df
    
    @staticmethod
    def _calculate_rsi(prices: pd.Series, period: int = 14) -> pd.Series:
        """Calculate Relative Strength Index"""
        delta = prices.diff()
        
        gain = delta.where(delta > 0, 0)
        loss = (-delta).where(delta < 0, 0)
        
        avg_gain = gain.ewm(com=period - 1, min_periods=period).mean()
        avg_loss = loss.ewm(com=period - 1, min_periods=period).mean()
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        
        return rsi
    
    @staticmethod
    def _calculate_macd(
        prices: pd.Series,
        fast: int = 12,
        slow: int = 26,
        signal: int = 9
    ) -> Tuple[pd.Series, pd.Series, pd.Series]:
        """Calculate MACD, Signal, and Histogram"""
        ema_fast = prices.ewm(span=fast, adjust=False).mean()
        ema_slow = prices.ewm(span=slow, adjust=False).mean()
        
        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=signal, adjust=False).mean()
        histogram = macd_line - signal_line
        
        return macd_line, signal_line, histogram
    
    @staticmethod
    def _calculate_atr(
        high: pd.Series,
        low: pd.Series,
        close: pd.Series,
        period: int = 14
    ) -> pd.Series:
        """Calculate Average True Range"""
        tr1 = high - low
        tr2 = abs(high - close.shift(1))
        tr3 = abs(low - close.shift(1))
        
        true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = true_range.ewm(span=period, adjust=False).mean()
        
        return atr
    
    def prepare_sequences(
        self,
        df: pd.DataFrame,
        target_col: str = 'close',
        prediction_horizon: int = 1
    ) -> Tuple[np.ndarray, np.ndarray, List[str]]:
        """
        Prepare sequences for LSTM/Transformer training.
        
        Args:
            df: DataFrame with features
            target_col: Column to predict
            prediction_horizon: How many steps ahead to predict
            
        Returns:
            X: Shape (samples, sequence_length, features)
            y: Shape (samples,) - future returns
            feature_names: List of feature column names
        """
        # Get feature columns
        feature_cols = [c for c in df.columns if c not in 
                       ['timestamp', 'open', 'high', 'low', 'close', 'volume', 'target']]
        
        # Calculate target (future returns)
        df = df.copy()
        df['target'] = df[target_col].pct_change(periods=prediction_horizon).shift(-prediction_horizon)
        
        # Drop rows with NaN
        df = df.dropna()
        
        # Extract features
        features = df[feature_cols].values
        target = df['target'].values
        
        # Normalize features
        features = self._normalize_features(features)
        
        # Create sequences
        X, y = [], []
        seq_len = self.config.sequence_length
        
        for i in range(len(features) - seq_len):
            X.append(features[i:i + seq_len])
            y.append(target[i + seq_len - 1])
        
        return np.array(X), np.array(y), feature_cols
    
    @staticmethod
    def _normalize_features(features: np.ndarray) -> np.ndarray:
        """Normalize features using robust scaling"""
        # Use median and IQR for robustness to outliers
        median = np.nanmedian(features, axis=0)
        q75 = np.nanpercentile(features, 75, axis=0)
        q25 = np.nanpercentile(features, 25, axis=0)
        iqr = q75 - q25
        iqr[iqr == 0] = 1  # Avoid division by zero
        
        normalized = (features - median) / iqr
        
        # Clip extreme values
        normalized = np.clip(normalized, -5, 5)
        
        # Replace NaN with 0
        normalized = np.nan_to_num(normalized, 0)
        
        return normalized


class SentimentAnalyzer:
    """Analyze social media sentiment for crypto tokens"""
    
    def __init__(self):
        self._vader = None
        
    @property
    def vader(self):
        """Lazy load VADER sentiment analyzer"""
        if self._vader is None:
            try:
                from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
                self._vader = SentimentIntensityAnalyzer()
            except ImportError:
                logger.warning("vaderSentiment not installed")
        return self._vader
    
    def analyze_text(self, text: str) -> Dict[str, float]:
        """Analyze sentiment of a single text"""
        if self.vader is None:
            return {'compound': 0, 'pos': 0, 'neg': 0, 'neu': 1}
        
        scores = self.vader.polarity_scores(text)
        return scores
    
    def analyze_texts(self, texts: List[str]) -> Dict[str, float]:
        """Analyze sentiment of multiple texts and aggregate"""
        if not texts:
            return {'sentiment_score': 0, 'bullish_ratio': 0.5, 'social_volume': 0}
        
        scores = [self.analyze_text(t) for t in texts]
        
        avg_compound = np.mean([s['compound'] for s in scores])
        bullish = sum(1 for s in scores if s['compound'] > 0.05)
        bearish = sum(1 for s in scores if s['compound'] < -0.05)
        
        return {
            'sentiment_score': avg_compound,
            'bullish_ratio': bullish / (bullish + bearish) if (bullish + bearish) > 0 else 0.5,
            'social_volume': len(texts)
        }
