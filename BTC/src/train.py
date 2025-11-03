"""Training module for Volensy LLM."""

import logging
from pathlib import Path
from typing import Dict

import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset

from src.dataset import make_windows
from src.models.transformer import SeqClassifier
from src.labeling import get_class_weights
from src.utils import set_seed, save_feat_cols

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def train_model(
    X_train: np.ndarray,
    Y_train: np.ndarray,
    X_val: np.ndarray,
    Y_val: np.ndarray,
    feature_cols: list,
    config: Dict,
) -> tuple[SeqClassifier, list]:
    """
    Train Transformer model.

    Args:
        X_train: (N, T, F) training sequences
        Y_train: (N,) training labels
        X_val: (N', T, F) validation sequences
        Y_val: (N',) validation labels
        feature_cols: List of feature column names
        config: Training configuration

    Returns:
        (model, history)
    """
    set_seed(config["seed"])
    
    n_features = X_train.shape[2]
    
    # Create datasets
    train_dataset = TensorDataset(
        torch.FloatTensor(X_train),
        torch.LongTensor(Y_train)
    )
    val_dataset = TensorDataset(
        torch.FloatTensor(X_val),
        torch.LongTensor(Y_val)
    )
    
    train_loader = DataLoader(
        train_dataset,
        batch_size=config["batch_size"],
        shuffle=True,
    )
    val_loader = DataLoader(
        val_dataset,
        batch_size=config["batch_size"],
        shuffle=False,
    )
    
    # Model
    model = SeqClassifier(n_features=n_features)
    
    # Class weights for imbalanced data
    class_weights = get_class_weights(Y_train)
    criterion = nn.CrossEntropyLoss(
        weight=torch.FloatTensor(class_weights)
    )
    
    # Optimizer
    optimizer = torch.optim.AdamW(
        model.parameters(),
        lr=config["lr"]
    )
    
    # Training loop
    history = []
    
    for epoch in range(config["epochs"]):
        # Train
        model.train()
        train_loss = 0.0
        train_correct = 0
        train_total = 0
        
        for X_batch, Y_batch in train_loader:
            optimizer.zero_grad()
            logits = model(X_batch)
            loss = criterion(logits, Y_batch)
            loss.backward()
            optimizer.step()
            
            train_loss += loss.item()
            _, predicted = logits.max(1)
            train_total += Y_batch.size(0)
            train_correct += predicted.eq(Y_batch).sum().item()
        
        # Validation
        model.eval()
        val_loss = 0.0
        val_correct = 0
        val_total = 0
        
        with torch.no_grad():
            for X_batch, Y_batch in val_loader:
                logits = model(X_batch)
                loss = criterion(logits, Y_batch)
                
                val_loss += loss.item()
                _, predicted = logits.max(1)
                val_total += Y_batch.size(0)
                val_correct += predicted.eq(Y_batch).sum().item()
        
        train_acc = 100.0 * train_correct / train_total
        val_acc = 100.0 * val_correct / val_total
        
        history.append({
            "epoch": epoch + 1,
            "train_loss": train_loss / len(train_loader),
            "train_acc": train_acc,
            "val_loss": val_loss / len(val_loader),
            "val_acc": val_acc,
        })
        
        logger.info(
            f"Epoch {epoch+1}/{config['epochs']} | "
            f"Train Loss: {train_loss/len(train_loader):.4f} | "
            f"Train Acc: {train_acc:.2f}% | "
            f"Val Acc: {val_acc:.2f}%"
        )
    
    return model, history


def save_model(
    model: SeqClassifier,
    feature_cols: list,
    model_dir: Path,
    model_name: str = "seqcls",
) -> None:
    """Save model and feature columns."""
    model_dir.mkdir(parents=True, exist_ok=True)
    
    # Save model
    model_path = model_dir / f"{model_name}.pt"
    torch.save(model.state_dict(), model_path)
    logger.info(f"Model saved to {model_path}")
    
    # Save feature columns
    feat_cols_path = model_dir / f"feat_cols.json"
    save_feat_cols(feature_cols, feat_cols_path)
    logger.info(f"Feature columns saved to {feat_cols_path}")
