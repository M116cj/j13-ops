"""Combination grammar for axis-specific formula construction.

Produces canonical AST tuples that hash deterministically. Each axis has its
own grammar family that biases primitives toward axis intent.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator
import hashlib
import json
import random

from .primitive_inventory import (
    UnsupportedOperatorError,
    get_primitive,
    primitives_by_family,
    supported_primitives,
)


# Canonical AST node types: ("field", name) or ("op", name, args, [window])
ASTNode = tuple


@dataclass(frozen=True)
class FormulaSpec:
    axis_id: str
    grammar_family: str
    primitive_family: str  # primary primitive family used at the root
    ast: ASTNode
    canonical_text: str
    alpha_hash: str


# Base fields that may appear in a formula. Available depends on axis component data.
BASE_FIELDS_OHLCV = ("close", "high", "low", "open", "volume")
BASE_FIELDS_FUNDING_OI = ("funding", "oi")

WINDOWS = (5, 10, 20, 60)


def _canonical_text(ast: ASTNode) -> str:
    """Stable text serialization of AST — used as alpha_hash input."""
    if ast[0] == "field":
        return ast[1]
    if ast[0] == "op":
        name = ast[1]
        args = ast[2]
        body = ",".join(_canonical_text(a) for a in args)
        if len(ast) == 4:  # has window
            return f"{name}({body};w={ast[3]})"
        return f"{name}({body})"
    raise ValueError(f"bad AST node: {ast!r}")


def alpha_hash_for(ast: ASTNode) -> str:
    text = _canonical_text(ast)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _random_field(rng: random.Random, fields: tuple[str, ...]) -> ASTNode:
    return ("field", rng.choice(fields))


def _random_window(rng: random.Random) -> int:
    return rng.choice(WINDOWS)


def _random_unary_ts(rng: random.Random, child: ASTNode) -> ASTNode:
    name = rng.choice(("delta", "ts_mean", "ts_std", "ts_rank"))
    return ("op", name, (child,), _random_window(rng))


def _random_unary_transform(rng: random.Random, child: ASTNode) -> ASTNode:
    name = rng.choice(("neg", "sign", "tanh"))
    return ("op", name, (child,))


def _random_binary(rng: random.Random, lhs: ASTNode, rhs: ASTNode) -> ASTNode:
    name = rng.choice(("add", "sub", "mul", "protected_div"))
    return ("op", name, (lhs, rhs))


def _grammar_H(rng: random.Random) -> ASTNode:
    """Hybrid grammar: regime gate * funding/OI direction * cross-sectional rank component."""
    regime_part = _random_unary_ts(rng, _random_field(rng, BASE_FIELDS_OHLCV))
    funding_part = _random_field(rng, BASE_FIELDS_FUNDING_OI)
    funding_part = _random_unary_transform(rng, _random_unary_ts(rng, funding_part))
    rank_part = _random_unary_ts(rng, _random_field(rng, BASE_FIELDS_OHLCV))
    rank_part = ("op", "ts_rank", (rank_part,), _random_window(rng))
    inner = _random_binary(rng, regime_part, funding_part)
    return _random_binary(rng, inner, rank_part)


def _grammar_C(rng: random.Random) -> ASTNode:
    """Regime-conditional grammar: nested time-series transforms over OHLCV."""
    leaf = _random_field(rng, BASE_FIELDS_OHLCV)
    a = _random_unary_ts(rng, leaf)
    b = _random_unary_transform(rng, a)
    c = _random_unary_ts(rng, b)
    return c


def _grammar_D(rng: random.Random) -> ASTNode:
    """Cross-sectional grammar: ts_rank-based + arithmetic combos."""
    leaf1 = _random_field(rng, BASE_FIELDS_OHLCV)
    leaf2 = _random_field(rng, BASE_FIELDS_OHLCV)
    rank1 = ("op", "ts_rank", (leaf1,), _random_window(rng))
    rank2 = ("op", "ts_rank", (leaf2,), _random_window(rng))
    combined = _random_binary(rng, rank1, rank2)
    return _random_unary_transform(rng, combined)


def _grammar_E(rng: random.Random) -> ASTNode:
    """Liquidity/volume shock grammar (fallback)."""
    vol = _random_field(rng, ("volume", "oi"))
    a = ("op", "delta", (vol,), _random_window(rng))
    b = _random_unary_transform(rng, a)
    return b


_GRAMMARS = {
    "H": _grammar_H,
    "C": _grammar_C,
    "D": _grammar_D,
    "E": _grammar_E,
}


def has_unsupported_operator(ast: ASTNode) -> str | None:
    """Walk AST; return the offending name if any operator is not in inventory."""
    if ast[0] == "field":
        return None
    if ast[0] == "op":
        name = ast[1]
        try:
            get_primitive(name)
        except UnsupportedOperatorError:
            return name
        for child in ast[2]:
            r = has_unsupported_operator(child)
            if r is not None:
                return r
        return None
    return f"bad_node:{ast[0]}"


def generate_formulas(
    axis_id: str,
    n: int,
    seed: int,
) -> Iterator[FormulaSpec]:
    """Generate n formulas for an axis. Deterministic on (axis_id, seed)."""
    if axis_id not in _GRAMMARS:
        raise UnsupportedOperatorError(f"axis_grammar:{axis_id}")
    grammar = _GRAMMARS[axis_id]
    rng = random.Random(f"{axis_id}:{seed}")
    for _ in range(n):
        ast = grammar(rng)
        bad = has_unsupported_operator(ast)
        if bad is not None:
            # Fail closed: skip but record. Caller tracks counts.
            yield FormulaSpec(
                axis_id=axis_id,
                grammar_family=f"axis_{axis_id}",
                primitive_family="UNSUPPORTED",
                ast=ast,
                canonical_text=_canonical_text(ast),
                alpha_hash=alpha_hash_for(ast),
            )
            continue
        primary = ast[1] if ast[0] == "op" else "field"
        yield FormulaSpec(
            axis_id=axis_id,
            grammar_family=f"axis_{axis_id}",
            primitive_family=primary,
            ast=ast,
            canonical_text=_canonical_text(ast),
            alpha_hash=alpha_hash_for(ast),
        )
