"""Feedback weights + next-batch weights view-models."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional


@dataclass
class FeedbackView:
    state: str
    feedback_weights: Optional[dict]
    next_batch_weights: Optional[dict]
    note: Optional[str] = None


def build_feedback(batch_view) -> FeedbackView:
    fw_art = batch_view.artifacts.get('feedback_weights')
    nb_art = batch_view.artifacts.get('next_batch_weights')
    fw = nb = None
    if fw_art and fw_art.path.exists():
        try:
            import json
            with fw_art.path.open('r') as f:
                fw = json.load(f)
        except Exception as exc:
            return FeedbackView('ERROR', None, None, note=f'feedback_load_error:{exc}')
    if nb_art and nb_art.path.exists():
        try:
            import json
            with nb_art.path.open('r') as f:
                nb = json.load(f)
        except Exception:
            pass
    if fw is None and nb is None:
        return FeedbackView('NO_DATA', None, None, note='no_feedback_artifacts')
    return FeedbackView('OK', fw, nb)
