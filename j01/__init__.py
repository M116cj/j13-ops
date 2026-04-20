"""J01 — Harmonic K=2 alpha strategy.

Uses Zangetsu engine with a sign-gated harmonic-mean IC fitness computed
over two halves of the training window. F1-score analogue: collapses
toward the smaller half, reject if signs disagree.
"""
