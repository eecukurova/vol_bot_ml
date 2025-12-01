"""Transformer encoder for sequence classification."""

import torch
import torch.nn as nn
import torch.nn.functional as F


class SeqClassifier(nn.Module):
    """
    Small Transformer encoder for 3-class sequence classification.
    
    Architecture:
    - Input projection: Linear(n_features, d_model=64)
    - Transformer encoder: 2 layers, 4 heads
    - FFN: 4 * d_model
    - Output: AdaptiveAvgPool1d → Linear(d_model, 3)
    """
    
    def __init__(
        self,
        n_features: int,
        d_model: int = 64,
        nhead: int = 4,
        num_layers: int = 2,
        dropout: float = 0.1,
    ):
        super().__init__()
        self.d_model = d_model
        
        # Input projection
        self.input_proj = nn.Linear(n_features, d_model)
        
        # Positional encoding (learned)
        self.pos_encoding = nn.Parameter(torch.randn(1000, d_model))
        
        # Transformer encoder
        encoder_layer = nn.TransformerEncoderLayer(
            d_model=d_model,
            nhead=nhead,
            dim_feedforward=d_model * 4,
            dropout=dropout,
            batch_first=True,
        )
        self.transformer = nn.TransformerEncoder(encoder_layer, num_layers=num_layers)
        
        # Pooling
        self.pool = nn.AdaptiveAvgPool1d(1)
        
        # Classifier
        self.classifier = nn.Linear(d_model, 3)
        
        # Dropout
        self.dropout = nn.Dropout(dropout)
    
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Forward pass.

        Args:
            x: (B, T, F) tensor

        Returns:
            (B, 3) logits for [Flat, Long, Short]
        """
        B, T, F = x.shape
        
        # Project to d_model
        x = self.input_proj(x)  # (B, T, d_model)
        
        # Add positional encoding
        x = x + self.pos_encoding[:T].unsqueeze(0)
        
        # Transformer encoder
        x = self.transformer(x)  # (B, T, d_model)
        
        # Transpose for pooling: (B, d_model, T)
        x = x.transpose(1, 2)
        
        # Global pooling
        x = self.pool(x)  # (B, d_model, 1)
        x = x.squeeze(2)  # (B, d_model)
        
        # Classify
        x = self.dropout(x)
        x = self.classifier(x)  # (B, 3)
        
        return x
