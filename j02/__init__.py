"""J02 — ICIR K=5 alpha strategy.

Uses Zangetsu engine with an ICIR-style fitness: reward high mean(|IC|)
across five contiguous folds of the training window, penalize the
cross-fold std, require sign-agreement across all folds. Aligns with
AlphaForge / Warm-Start-GP / Numerai era-Sharpe industry practice.
"""
