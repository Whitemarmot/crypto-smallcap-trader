"""
LSTM Model for Crypto Price Prediction
Lightweight architecture optimized for CPU inference
"""

import torch
import torch.nn as nn
import numpy as np
from typing import Optional, Tuple, Dict, List
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class LSTMConfig:
    """Configuration for LSTM model"""
    input_size: int = 50  # Number of features
    hidden_size: int = 64  # LSTM hidden units (kept small for CPU)
    num_layers: int = 2  # Number of LSTM layers
    dropout: float = 0.2
    bidirectional: bool = False
    output_size: int = 1  # Predict single value (return)
    
    # Training
    learning_rate: float = 0.001
    batch_size: int = 32
    epochs: int = 100
    patience: int = 10  # Early stopping patience


class LSTMPriceModel(nn.Module):
    """
    LSTM-based model for crypto price prediction.
    
    Architecture:
    - LSTM layers with dropout
    - Attention mechanism for sequence importance
    - Fully connected output layer
    """
    
    def __init__(self, config: Optional[LSTMConfig] = None):
        super().__init__()
        self.config = config or LSTMConfig()
        
        # LSTM layers
        self.lstm = nn.LSTM(
            input_size=self.config.input_size,
            hidden_size=self.config.hidden_size,
            num_layers=self.config.num_layers,
            batch_first=True,
            dropout=self.config.dropout if self.config.num_layers > 1 else 0,
            bidirectional=self.config.bidirectional
        )
        
        # Calculate output size from LSTM
        lstm_output_size = self.config.hidden_size * (2 if self.config.bidirectional else 1)
        
        # Attention layer
        self.attention = nn.Sequential(
            nn.Linear(lstm_output_size, lstm_output_size // 2),
            nn.Tanh(),
            nn.Linear(lstm_output_size // 2, 1),
            nn.Softmax(dim=1)
        )
        
        # Output layers
        self.fc = nn.Sequential(
            nn.Linear(lstm_output_size, lstm_output_size // 2),
            nn.ReLU(),
            nn.Dropout(self.config.dropout),
            nn.Linear(lstm_output_size // 2, self.config.output_size)
        )
        
        # For direction prediction (classification head)
        self.direction_head = nn.Sequential(
            nn.Linear(lstm_output_size, 32),
            nn.ReLU(),
            nn.Linear(32, 3),  # UP, DOWN, NEUTRAL
            nn.Softmax(dim=1)
        )
        
        self._init_weights()
        
    def _init_weights(self):
        """Initialize weights using Xavier initialization"""
        for name, param in self.named_parameters():
            if 'weight_ih' in name:
                nn.init.xavier_uniform_(param)
            elif 'weight_hh' in name:
                nn.init.orthogonal_(param)
            elif 'bias' in name:
                nn.init.zeros_(param)
    
    def forward(
        self,
        x: torch.Tensor,
        return_attention: bool = False
    ) -> Tuple[torch.Tensor, Optional[torch.Tensor]]:
        """
        Forward pass.
        
        Args:
            x: Input tensor of shape (batch, seq_len, features)
            return_attention: Whether to return attention weights
            
        Returns:
            output: Predicted returns (batch, 1)
            attention_weights: Optional attention weights (batch, seq_len)
        """
        # LSTM forward
        lstm_out, (h_n, c_n) = self.lstm(x)
        # lstm_out: (batch, seq_len, hidden_size)
        
        # Attention mechanism
        attention_weights = self.attention(lstm_out)  # (batch, seq_len, 1)
        attention_weights = attention_weights.squeeze(-1)  # (batch, seq_len)
        
        # Weighted sum of LSTM outputs
        context = torch.bmm(
            attention_weights.unsqueeze(1),  # (batch, 1, seq_len)
            lstm_out  # (batch, seq_len, hidden_size)
        ).squeeze(1)  # (batch, hidden_size)
        
        # Output prediction
        output = self.fc(context)
        
        if return_attention:
            return output, attention_weights
        return output, None
    
    def predict_direction(self, x: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        Predict direction (UP/DOWN/NEUTRAL) with confidence.
        
        Args:
            x: Input tensor of shape (batch, seq_len, features)
            
        Returns:
            direction: Class indices (0=DOWN, 1=NEUTRAL, 2=UP)
            confidence: Confidence scores
        """
        # LSTM forward
        lstm_out, _ = self.lstm(x)
        
        # Use last hidden state
        last_hidden = lstm_out[:, -1, :]
        
        # Direction prediction
        probs = self.direction_head(last_hidden)
        
        direction = torch.argmax(probs, dim=1)
        confidence = torch.max(probs, dim=1).values
        
        return direction, confidence


class LSTMTrainer:
    """Trainer for LSTM model with early stopping and validation"""
    
    def __init__(
        self,
        model: LSTMPriceModel,
        config: Optional[LSTMConfig] = None
    ):
        self.model = model
        self.config = config or model.config
        
        # Use CPU by default for lightweight inference
        self.device = torch.device('cpu')
        self.model.to(self.device)
        
        # Optimizer
        self.optimizer = torch.optim.Adam(
            self.model.parameters(),
            lr=self.config.learning_rate
        )
        
        # Scheduler
        self.scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
            self.optimizer, mode='min', factor=0.5, patience=5
        )
        
        # Loss functions
        self.regression_loss = nn.MSELoss()
        self.direction_loss = nn.CrossEntropyLoss()
        
        # Training history
        self.history: Dict[str, List[float]] = {
            'train_loss': [],
            'val_loss': [],
            'val_accuracy': []
        }
        
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
        
        # For classification, convert targets to classes
        if task == 'classification':
            y_train_cls = self._returns_to_classes(y_train)
            if y_val is not None:
                y_val_cls = self._returns_to_classes(y_val)
        
        # Create data loader
        dataset = torch.utils.data.TensorDataset(X_train, y_train)
        loader = torch.utils.data.DataLoader(
            dataset,
            batch_size=self.config.batch_size,
            shuffle=True
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
                    direction, _ = self.model.predict_direction(batch_X)
                    # Need to compute loss before argmax
                    lstm_out, _ = self.model.lstm(batch_X)
                    probs = self.model.direction_head(lstm_out[:, -1, :])
                    loss = self.direction_loss(probs, batch_y_cls)
                
                loss.backward()
                torch.nn.utils.clip_grad_norm_(self.model.parameters(), 1.0)
                self.optimizer.step()
                
                train_losses.append(loss.item())
            
            avg_train_loss = np.mean(train_losses)
            self.history['train_loss'].append(avg_train_loss)
            
            # Validation
            if X_val is not None:
                val_loss, val_acc = self._validate(
                    X_val, y_val if task == 'regression' else y_val_cls,
                    task
                )
                self.history['val_loss'].append(val_loss)
                self.history['val_accuracy'].append(val_acc)
                
                # Learning rate scheduling
                self.scheduler.step(val_loss)
                
                # Early stopping
                if val_loss < best_val_loss:
                    best_val_loss = val_loss
                    patience_counter = 0
                    # Save best model state
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
                        f"val_loss={val_loss:.6f}, val_acc={val_acc:.4f}"
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
        """Validate model and return loss and accuracy"""
        self.model.eval()
        
        with torch.no_grad():
            if task == 'regression':
                output, _ = self.model(X_val)
                loss = self.regression_loss(output.squeeze(), y_val).item()
                
                # Direction accuracy for regression
                pred_direction = (output.squeeze() > 0).float()
                true_direction = (y_val > 0).float()
                accuracy = (pred_direction == true_direction).float().mean().item()
            else:
                direction, _ = self.model.predict_direction(X_val)
                lstm_out, _ = self.model.lstm(X_val)
                probs = self.model.direction_head(lstm_out[:, -1, :])
                loss = self.direction_loss(probs, y_val.long()).item()
                accuracy = (direction == y_val.long()).float().mean().item()
        
        return loss, accuracy
    
    @staticmethod
    def _returns_to_classes(returns: torch.Tensor, threshold: float = 0.005) -> torch.Tensor:
        """Convert continuous returns to directional classes"""
        classes = torch.zeros_like(returns, dtype=torch.long)
        classes[returns > threshold] = 2  # UP
        classes[returns < -threshold] = 0  # DOWN
        classes[(returns >= -threshold) & (returns <= threshold)] = 1  # NEUTRAL
        return classes
    
    def predict(self, X: np.ndarray) -> np.ndarray:
        """Make predictions on new data"""
        self.model.eval()
        X = torch.FloatTensor(X).to(self.device)
        
        with torch.no_grad():
            output, _ = self.model(X)
        
        return output.cpu().numpy()
    
    def predict_direction(
        self,
        X: np.ndarray
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Predict direction with confidence"""
        self.model.eval()
        X = torch.FloatTensor(X).to(self.device)
        
        with torch.no_grad():
            direction, confidence = self.model.predict_direction(X)
        
        return direction.cpu().numpy(), confidence.cpu().numpy()
    
    def save(self, path: str):
        """Save model to file"""
        torch.save({
            'model_state_dict': self.model.state_dict(),
            'config': self.config,
            'history': self.history
        }, path)
        logger.info(f"Model saved to {path}")
    
    def load(self, path: str):
        """Load model from file"""
        checkpoint = torch.load(path, map_location=self.device)
        self.model.load_state_dict(checkpoint['model_state_dict'])
        self.history = checkpoint.get('history', {})
        logger.info(f"Model loaded from {path}")
