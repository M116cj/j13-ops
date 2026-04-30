"""Candidate manifest: deterministic candidate_id, JSONL serialization."""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Iterable, Iterator, Mapping, Optional
import hashlib
import json
import os
import pathlib

from .combination_grammar import FormulaSpec


SIDE_MODES = ("LONG", "SHORT", "BOTH")


@dataclass(frozen=True)
class CandidateRecord:
    candidate_id: str
    generation_id: str
    axis_id: str
    grammar_family: str
    primitive_family: str
    formula: str          # canonical text
    alpha_hash: str
    symbol: str
    timeframe: str
    intended_side_mode: str  # one of SIDE_MODES


def candidate_id_for(
    *,
    generation_id: str,
    axis_id: str,
    alpha_hash: str,
    symbol: str,
    timeframe: str,
    intended_side_mode: str,
) -> str:
    if intended_side_mode not in SIDE_MODES:
        raise ValueError(f"intended_side_mode must be one of {SIDE_MODES}; got {intended_side_mode!r}")
    payload = "|".join((generation_id, axis_id, alpha_hash, symbol, timeframe, intended_side_mode))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def expand_formulas_to_candidates(
    formulas: Iterable[FormulaSpec],
    *,
    generation_id: str,
    symbols: tuple[str, ...],
    timeframe: str,
    side_modes: tuple[str, ...] = ("LONG", "SHORT"),
) -> Iterator[CandidateRecord]:
    """Cross formulas with (symbol, side_mode) — preserving axis identity."""
    for spec in formulas:
        for symbol in symbols:
            for mode in side_modes:
                cid = candidate_id_for(
                    generation_id=generation_id,
                    axis_id=spec.axis_id,
                    alpha_hash=spec.alpha_hash,
                    symbol=symbol,
                    timeframe=timeframe,
                    intended_side_mode=mode,
                )
                yield CandidateRecord(
                    candidate_id=cid,
                    generation_id=generation_id,
                    axis_id=spec.axis_id,
                    grammar_family=spec.grammar_family,
                    primitive_family=spec.primitive_family,
                    formula=spec.canonical_text,
                    alpha_hash=spec.alpha_hash,
                    symbol=symbol,
                    timeframe=timeframe,
                    intended_side_mode=mode,
                )


def write_manifest_jsonl(records: Iterable[CandidateRecord], path: str | pathlib.Path) -> int:
    p = pathlib.Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with p.open("w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(asdict(rec), separators=(",", ":")) + "\n")
            n += 1
    return n


def read_manifest_jsonl(path: str | pathlib.Path) -> list[CandidateRecord]:
    out: list[CandidateRecord] = []
    with pathlib.Path(path).open("r", encoding="utf-8") as f:
        for line in f:
            obj = json.loads(line)
            out.append(CandidateRecord(**obj))
    return out
