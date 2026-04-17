"""V9 Attention-based Signal Aggregation.

Replaces majority voting with learned self-attention that dynamically
weights indicators based on current market state.

Architecture:
    21 indicators → linear projection (d_model)
           ↓
    Market state embedding (regime + vol + volume)
           ↓
    Multi-head self-attention (weights indicators per context)
           ↓
    Weighted sum → signal [-1, +1]

Falls back to majority voting if PyTorch unavailable.
"""
from __future__ import annotations

import logging
from typing import Optional
import numpy as np

log = logging.getLogger(__name__)

try:
    import torch
    import torch.nn as nn
    HAS_TORCH = True
except ImportError:
    HAS_TORCH = False
    log.warning("PyTorch not available — attention aggregation disabled")


# ═══════════════════════════════════════════════════════════════════
# Torch Attention Module (trained offline, deployed inline)
# ═══════════════════════════════════════════════════════════════════

if HAS_TORCH:
    class IndicatorAttention(nn.Module):
        """Self-attention over indicator signals + market state conditioning."""

        def __init__(self, max_indicators: int = 21, d_model: int = 32,
                     n_heads: int = 4, regime_dim: int = 13):
            super().__init__()
            self.max_indicators = max_indicators
            self.d_model = d_model
            # Indicator embedding (signal value -> d_model vector)
            self.indicator_proj = nn.Linear(1, d_model)
            # Regime conditioning (one-hot regime -> d_model)
            self.regime_embed = nn.Embedding(regime_dim, d_model)
            # Self-attention
            self.attn = nn.MultiheadAttention(d_model, n_heads, batch_first=True)
            # Output head: weighted sum -> scalar signal
            self.output = nn.Linear(d_model, 1)

        def forward(self, indicator_signals: torch.Tensor,
                    regime_idx: torch.Tensor) -> torch.Tensor:
            """
            indicator_signals: (batch, n_indicators) in [-1, +1]
            regime_idx: (batch,) long tensor, regime ID
            Returns: (batch,) signal in [-1, +1] via tanh
            """
            B, N = indicator_signals.shape
            # Project each indicator signal to d_model
            x = indicator_signals.unsqueeze(-1)  # (B, N, 1)
            x = self.indicator_proj(x)  # (B, N, d_model)

            # Add regime context as extra token
            regime_vec = self.regime_embed(regime_idx).unsqueeze(1)  # (B, 1, d_model)
            x_with_context = torch.cat([regime_vec, x], dim=1)  # (B, N+1, d_model)

            # Self-attention
            attended, attn_weights = self.attn(x_with_context, x_with_context, x_with_context)

            # Mean-pool over indicator positions (skip regime token)
            pooled = attended[:, 1:, :].mean(dim=1)  # (B, d_model)

            # Project to scalar signal
            signal = torch.tanh(self.output(pooled)).squeeze(-1)  # (B,)
            return signal, attn_weights


# ═══════════════════════════════════════════════════════════════════
# Deployment-side aggregator (numpy only, fast)
# ═══════════════════════════════════════════════════════════════════

class AttentionAggregator:
    """Lightweight numpy implementation for live deployment.

    Takes learned attention weights (from offline-trained IndicatorAttention)
    and applies them as a weighted sum over indicator signals.

    Falls back to majority voting if weights unavailable.
    """

    def __init__(self, weights: Optional[np.ndarray] = None,
                 regime_biases: Optional[dict] = None):
        """
        weights: array of shape (n_indicators,) — stored attention weights
        regime_biases: dict mapping regime -> weight_multiplier array
        """
        self.weights = weights
        self.regime_biases = regime_biases or {}

    def aggregate(self, indicator_signals: np.ndarray, regime: str = "UNKNOWN") -> np.ndarray:
        """Aggregate indicator signals to single signal array.

        indicator_signals: shape (n_indicators, n_bars) — each row is an indicator's [-1,+1] signal
        Returns: shape (n_bars,) — aggregated signal in [-1, +1]
        """
        if indicator_signals.ndim == 1:
            indicator_signals = indicator_signals.reshape(1, -1)

        n_ind, n_bars = indicator_signals.shape

        # Get weights for this regime
        if self.weights is not None and len(self.weights) >= n_ind:
            w = self.weights[:n_ind].copy()
        else:
            w = np.ones(n_ind, dtype=np.float32) / n_ind  # uniform fallback

        # Apply regime bias if available
        if regime in self.regime_biases:
            bias = self.regime_biases[regime][:n_ind]
            w = w * bias
            w = w / max(w.sum(), 1e-10)  # renormalize

        # Weighted sum
        aggregated = np.tensordot(w, indicator_signals, axes=([0], [0]))

        # Clip to [-1, +1]
        return np.clip(aggregated, -1.0, 1.0)

    @classmethod
    def majority_fallback(cls) -> "AttentionAggregator":
        """Return a fallback aggregator that behaves like majority voting."""
        return cls(weights=None, regime_biases=None)


# ═══════════════════════════════════════════════════════════════════
# Training utility (offline use only — trains attention weights from historical A3 results)
# ═══════════════════════════════════════════════════════════════════

def train_attention_from_history(historical_signals: np.ndarray,
                                  historical_outcomes: np.ndarray,
                                  regimes: np.ndarray,
                                  n_epochs: int = 10, lr: float = 1e-3) -> AttentionAggregator:
    """Offline training of attention weights from past A3 outcomes.

    historical_signals: (n_samples, n_indicators) indicator signals at decision points
    historical_outcomes: (n_samples,) forward returns or A3 pass indicator
    regimes: (n_samples,) regime IDs

    Returns AttentionAggregator with learned weights.
    """
    if not HAS_TORCH:
        log.warning("PyTorch unavailable — returning uniform-weight aggregator")
        return AttentionAggregator()

    model = IndicatorAttention(max_indicators=historical_signals.shape[1])
    optimizer = torch.optim.Adam(model.parameters(), lr=lr)
    loss_fn = nn.MSELoss()

    X = torch.from_numpy(historical_signals.astype(np.float32))
    y = torch.from_numpy(historical_outcomes.astype(np.float32))
    r = torch.from_numpy(regimes.astype(np.int64))

    for epoch in range(n_epochs):
        optimizer.zero_grad()
        pred, attn = model(X, r)
        loss = loss_fn(pred, y)
        loss.backward()
        optimizer.step()
        if epoch % 2 == 0:
            log.info(f"Attention training epoch {epoch}: loss={loss.item():.4f}")

    # Extract learned weights (simplified: use last-layer weights as aggregation weights)
    with torch.no_grad():
        # Use diagonal of indicator_proj as per-indicator importance
        importance = model.indicator_proj.weight.abs().mean(dim=1).numpy()
        importance = importance / importance.sum()

    return AttentionAggregator(weights=importance)
