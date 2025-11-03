"""Test model forward pass."""

import numpy as np
import torch

from src.models.transformer import SeqClassifier


def test_model_forward():
    """Test model forward pass shape."""
    # Create dummy data
    batch_size = 4
    seq_length = 128
    n_features = 17
    
    X = np.random.randn(batch_size, seq_length, n_features)
    
    # Create model
    model = SeqClassifier(n_features=n_features)
    
    # Forward pass
    X_tensor = torch.FloatTensor(X)
    logits = model(X_tensor)
    
    # Check shape
    assert logits.shape == (batch_size, 3)  # 3 classes
    
    # Check output range (softmax makes it probabilities)
    probs = torch.softmax(logits, dim=1)
    assert torch.allclose(probs.sum(dim=1), torch.ones(batch_size))


def test_model_with_window():
    """Test with actual window length."""
    n_features = 17
    window = 128
    
    model = SeqClassifier(n_features=n_features, d_model=64)
    
    # Single sample
    X = np.random.randn(1, window, n_features)
    logits = model(torch.FloatTensor(X))
    
    assert logits.shape == (1, 3)


if __name__ == "__main__":
    test_model_forward()
    test_model_with_window()
    print("✓ All model tests passed")
