"""
Transformer Model for Time Series Prediction
Lightweight architecture optimized for CPU inference
"""

import torch
import torch.nn as nn
import numpy as np
import math
from typing import Optional, Tuple, Dict, List
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class TransformerConfig:
    """Configuration for Transformer model"""
    input_size: int = 50  # Number of features
    d_model: int = 64  # Model dimension (kept small for CPU)
    nhead: int = 4  # Number of attention heads
    num_encoder_layers: int = 2  # Number of encoder layers
    dim_feedforward: int = 128  # FFN dimension
    dropout: float = 0.1
    max_seq_length: int = 120
    output_size: int = 1
    
    # Training
    learning_rate: float = 0.0005
    batch_size: int = 32
    epochs: int = 100
    patience: int = 10
    warmup_steps: int = 1000


class PositionalEncoding(nn.Module):
    """Sinusoidal positional encoding for sequences"""
    
    def __init__(self, d_model: int, max_len: int = 500, dropout: float = 0.1):
        super().__init__()
        self.dropout = nn.Dropout(p=dropout)
        
        # Create positional encoding matrix
        pe = torch.zeros(max_len, d_model)
        position = torch.arange(0, max_len, dtype=torch.float).unsqueeze(1)
        div_term = torch.exp(
            torch.arange(0, d_model, 2).float() * (-math.log(10000.0) / d_model)
        )
        
        pe[:, 0::2] = torch.sin(position * div_term)
        pe[:, 1::2] = torch.cos(position * div_term)
        pe = pe.unsqueeze(0)  # (1, max_len, d_model)
        
        self.register_buffer('pe', pe)
    
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Args:
            x: Tensor of shape (batch, seq_len, d_model)
        """
        x = x + self.pe[:, :x.size(1), :]
        return self.dropout(x)


class TemporalAttention(nn.Module):
    """Temporal attention for weighting sequence positions"""
    
    def __init__(self, d_model: int):
        super().__init__()
        self.attention = nn.Sequential(
            nn.Linear(d_model, d_model // 2),
            nn.Tanh(),
            nn.Linear(d_model // 2, 1)
        )
    
    def forward(self, x: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        Args:
            x: Tensor of shape (batch, seq_len, d_model)
            
        Returns:
            context: Weighted sum (batch, d_model)
            weights: Attention weights (batch, seq_len)
        """
        # Compute attention scores
        scores = self.attention(x).squeeze(-1)  # (batch, seq_len)
        weights = torch.softmax(scores, dim=-1)
        
        # Weighted sum
        context = torch.bmm(weights.unsqueeze(1), x).squeeze(1)  # (batch, d_model)
        
        return context, weights


class TransformerPriceModel(nn.Module):
    """
    Transformer-based model for crypto price prediction.
    
    Architecture:
    - Input projection
    - Positional encoding
    - Transformer encoder layers
    - Temporal attention
    - Output heads for regression and classification
    """
    
    def __init__(self, config: Optional[TransformerConfig] = None):
        super().__init__()
        self.config = config or TransformerConfig()
        
        # Input projection
        self.input_projection = nn.Linear(
            self.config.input_size,
            self.config.d_model
        )
        
        # Positional encoding
        self.pos_encoding = PositionalEncoding(
            self.config.d_model,
            self.config.max_seq_length,
            self.config.dropout
        )
        
        # Transformer encoder
        encoder_layer = nn.TransformerEncoderLayer(
            d_model=self.config.d_model,
            nhead=self.config.nhead,
            dim_feedforward=self.config.dim_feedforward,
            dropout=self.config.dropout,
            activation='gelu',
            batch_first=True
        )
        self.transformer_encoder = nn.TransformerEncoder(
            encoder_layer,
            num_layers=self.config.num_encoder_layers
        )
        
        # Temporal attention
        self.temporal_attention = TemporalAttention(self.config.d_model)
        
        # Output layer normalization
        self.layer_norm = nn.LayerNorm(self.config.d_model)
        
        # Regression head (for price prediction)
        self.regression_head = nn.Sequential(
            nn.Linear(self.config.d_model, self.config.d_model // 2),
            nn.GELU(),
            nn.Dropout(self.config.dropout),
            nn.Linear(self.config.d_model // 2, self.config.output_size)
        )
        
        # Classification head (for direction prediction)
        self.classification_head = nn.Sequential(
            nn.Linear(self.config.d_model, self.config.d_model // 2),
            nn.GELU(),
            nn.Dropout(self.config.dropout),
            nn.Linear(self.config.d_model // 2, 3)  # UP, DOWN, NEUTRAL
        )
        
        # Confidence estimation head
        self.confidence_head = nn.Sequential(
            nn.Linear(self.config.d_model, 16),
            nn.GELU(),
            nn.Linear(16, 1),
            nn.Sigmoid()
        )
        
        self._init_weights()
    
    def _init_weights(self):
        """Initialize weights"""
        for p in self.parameters():
            if p.dim() > 1:
                nn.init.xavier_uniform_(p)
    
    def forward(
        self,
        x: torch.Tensor,
        mask: Optional[torch.Tensor] = None,
        return_attention: bool = False
    ) -> Tuple[torch.Tensor, Optional[torch.Tensor]]:
        """
        Forward pass for regression.
        
        Args:
            x: Input tensor of shape (batch, seq_len, features)
            mask: Optional attention mask
            return_attention: Whether to return attention weights
            
        Returns:
            output: Predicted returns (batch, 1)
            attention_weights: Optional attention weights
        """
        # Project input to model dimension
        x = self.input_projection(x)  # (batch, seq_len, d_model)
        
        # Add positional encoding
        x = self.pos_encoding(x)
        
        # Transformer encoder
        encoded = self.transformer_encoder(x, mask=mask)  # (batch, seq_len, d_model)
        
        # Apply layer normalization
        encoded = self.layer_norm(encoded)
        
        # Temporal attention to aggregate sequence
        context, attention_weights = self.temporal_attention(encoded)
        
        # Regression output
        output = self.regression_head(context)
        
        if return_attention:
            return output, attention_weights
        return output, None
    
    def predict_direction(
        self,
        x: torch.Tensor,
        mask: Optional[torch.Tensor] = None
    ) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        """
        Predict direction with confidence.
        
        Args:
            x: Input tensor of shape (batch, seq_len, features)
            mask: Optional attention mask
            
        Returns:
            direction: Class indices (0=DOWN, 1=NEUTRAL, 2=UP)
            confidence: Model's confidence in prediction
            probabilities: Class probabilities
        """
        # Encode input
        x = self.input_projection(x)
        x = self.pos_encoding(x)
        encoded = self.transformer_encoder(x, mask=mask)
        encoded = self.layer_norm(encoded)
        
        # Aggregate sequence
        context, _ = self.temporal_attention(encoded)
        
        # Classification
        logits = self.classification_head(context)
        probabilities = torch.softmax(logits, dim=-1)
        
        direction = torch.argmax(probabilities, dim=-1)
        
        # Confidence estimation
        confidence = self.confidence_head(context).squeeze(-1)
        
        return direction, confidence, probabilities
    
    def predict_price(
        self,
        x: torch.Tensor,
        current_price: float,
        mask: Optional[torch.Tensor] = None
    ) -> torch.Tensor:
        """
        Predict future price.
        
        Args:
            x: Input tensor
            current_price: Current price for conversion
            mask: Optional attention mask
            
        Returns:
            Predicted price
        """
        output, _ = self.forward(x, mask)
        predicted_return = output.squeeze(-1)
        
        # Convert return to price
        predicted_price = current_price * (1 + predicted_return)
        
        return predicted_price


class TransformerTrainer:
    """Trainer for Transformer model with warmup and early stopping"""
    
    def __init__(
        self,
        model: TransformerPriceModel,
        config: Optional[TransformerConfig] = None
    ):
        self.model = model
        self.config = config or model.config
        
        self.device = torch.device('cpu')
        self.model.to(self.device)
        
        # Optimizer
        self.optimizer = torch.optim.AdamW(
            self.model.parameters(),
            lr=self.config.learning_rate,
            weight_decay=0.01
        )
        
        # Learning rate scheduler with warmup
        self.scheduler = self._get_scheduler()
        
        # Loss functions
        self.regression_loss = nn.MSELoss()
        self.classification_loss = nn.CrossEntropyLoss()
        
        # Training state
        self.global_step = 0
        self.history: Dict[str, List[float]] = {
            'train_loss': [],
            'val_loss': [],
            'val_accuracy': [],
            'learning_rate': []
        }
    
    def _get_scheduler(self):
        """Create scheduler with linear warmup"""
        def lr_lambda(step):
            if step < self.config.warmup_steps:
                return float(step) / float(max(1, self.config.warmup_steps))
            return 1.0
        
        return torch.optim.lr_scheduler.LambdaLR(self.optimizer, lr_lambda)
    
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
            X_train: Training features (samples, seq_len, features)
            y_train: Training targets
            X_val: Validation features
            y_val: Validation targets
            task: 'regression' or 'classification'
            
        Returns:
            Training history
        """
        # Convert to tensors
        X_train = torch.FloatTensor(X_train).to(self.device)
        y_train = torch.FloatTensor(y_train).to(self.device)
        
        if X_val is not None:
            X_val = torch.FloatTensor(X_val).to(self.device)
            y_val = torch.FloatTensor(y_val).to(self.device)
        
        # Create data loader
        dataset = torch.utils.data.TensorDataset(X_train, y_train)
        loader = torch.utils.data.DataLoader(
            dataset,
            batch_size=self.config.batch_size,
            shuffle=True,
            drop_last=True
        )
        
        best_val_loss = float('inf')
        patience_counter = 0
        
        for epoch in range(self.config.epochs):
            # Training
            self.model.train()
            train_losses = []
            
            for batch_X, batch_y in loader:
                self.optimizer.zero_grad()
                
                if task == 'regression':
                    output, _ = self.model(batch_X)
                    loss = self.regression_loss(output.squeeze(), batch_y)
                else:
                    batch_y_cls = self._returns_to_classes(batch_y)
                    _, _, probs = self.model.predict_direction(batch_X)
                    loss = self.classification_loss(probs, batch_y_cls)
                
                loss.backward()
                torch.nn.utils.clip_grad_norm_(self.model.parameters(), 1.0)
                self.optimizer.step()
                self.scheduler.step()
                
                train_losses.append(loss.item())
                self.global_step += 1
                
                # Log learning rate
                current_lr = self.optimizer.param_groups[0]['lr']
            
            avg_train_loss = np.mean(train_losses)
            self.history['train_loss'].append(avg_train_loss)
            self.history['learning_rate'].append(current_lr)
            
            # Validation
            if X_val is not None:
                val_loss, val_acc = self._validate(X_val, y_val, task)
                self.history['val_loss'].append(val_loss)
                self.history['val_accuracy'].append(val_acc)
                
                # Early stopping
                if val_loss < best_val_loss:
                    best_val_loss = val_loss
                    patience_counter = 0
                    self.best_state = {
                        k: v.cpu().clone() for k, v in self.model.state_dict().items()
                    }
                else:
                    patience_counter += 1
                    if patience_counter >= self.config.patience:
                        logger.info(f"Early stopping at epoch {epoch + 1}")
                        break
                
                if (epoch + 1) % 10 == 0:
                    logger.info(
                        f"Epoch {epoch + 1}: train_loss={avg_train_loss:.6f}, "
                        f"val_loss={val_loss:.6f}, val_acc={val_acc:.4f}, lr={current_lr:.6f}"
                    )
            else:
                if (epoch + 1) % 10 == 0:
                    logger.info(f"Epoch {epoch + 1}: train_loss={avg_train_loss:.6f}")
        
        # Restore best model
        if hasattr(self, 'best_state'):
            self.model.load_state_dict(self.best_state)
        
        return self.history
    
    def _validate(
        self,
        X_val: torch.Tensor,
        y_val: torch.Tensor,
        task: str
    ) -> Tuple[float, float]:
        """Validate model"""
        self.model.eval()
        
        with torch.no_grad():
            if task == 'regression':
                output, _ = self.model(X_val)
                loss = self.regression_loss(output.squeeze(), y_val).item()
                
                # Direction accuracy
                pred_dir = (output.squeeze() > 0).float()
                true_dir = (y_val > 0).float()
                accuracy = (pred_dir == true_dir).float().mean().item()
            else:
                y_val_cls = self._returns_to_classes(y_val)
                direction, _, probs = self.model.predict_direction(X_val)
                loss = self.classification_loss(probs, y_val_cls).item()
                accuracy = (direction == y_val_cls).float().mean().item()
        
        return loss, accuracy
    
    @staticmethod
    def _returns_to_classes(returns: torch.Tensor, threshold: float = 0.005) -> torch.Tensor:
        """Convert returns to classes"""
        classes = torch.ones_like(returns, dtype=torch.long)  # NEUTRAL
        classes[returns > threshold] = 2  # UP
        classes[returns < -threshold] = 0  # DOWN
        return classes
    
    def predict(self, X: np.ndarray) -> np.ndarray:
        """Make predictions"""
        self.model.eval()
        X = torch.FloatTensor(X).to(self.device)
        
        with torch.no_grad():
            output, _ = self.model(X)
        
        return output.cpu().numpy()
    
    def predict_direction(
        self,
        X: np.ndarray
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Predict direction with confidence"""
        self.model.eval()
        X = torch.FloatTensor(X).to(self.device)
        
        with torch.no_grad():
            direction, confidence, probs = self.model.predict_direction(X)
        
        return (
            direction.cpu().numpy(),
            confidence.cpu().numpy(),
            probs.cpu().numpy()
        )
    
    def save(self, path: str):
        """Save model"""
        torch.save({
            'model_state_dict': self.model.state_dict(),
            'optimizer_state_dict': self.optimizer.state_dict(),
            'config': self.config,
            'history': self.history,
            'global_step': self.global_step
        }, path)
        logger.info(f"Model saved to {path}")
    
    def load(self, path: str):
        """Load model"""
        checkpoint = torch.load(path, map_location=self.device)
        self.model.load_state_dict(checkpoint['model_state_dict'])
        self.optimizer.load_state_dict(checkpoint['optimizer_state_dict'])
        self.history = checkpoint.get('history', {})
        self.global_step = checkpoint.get('global_step', 0)
        logger.info(f"Model loaded from {path}")
