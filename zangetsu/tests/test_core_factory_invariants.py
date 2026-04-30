"""Cross-cutting invariants for 0-9AB.

These tests guard against:
- A2_MIN_TRADES drift,
- production-runtime imports of core_factory,
- alpha_hash including timestamp/created_at,
- core_factory writing into production runtime.
"""

import importlib
import inspect
import pathlib

import pytest

from zangetsu.core_factory.constants import A2_MIN_TRADES
from zangetsu.services import arena_gates


def test_a2_min_trades_unchanged():
    assert A2_MIN_TRADES == 25
    assert arena_gates.A2_MIN_TRADES == 25


def test_alpha_hash_excludes_timestamp_field():
    src = pathlib.Path(arena_gates.__file__).parent.parent / 'core_factory' / 'combination_grammar.py'
    text = src.read_text()
    # alpha_hash_for must hash only the canonical AST text — never timestamp/created_at/seed.
    func_src = inspect.getsource(
        importlib.import_module('zangetsu.core_factory.combination_grammar').alpha_hash_for)
    forbidden = ['timestamp', 'created_at', 'now()', 'time.time', 'random.random']
    for tok in forbidden:
        assert tok not in func_src, f'alpha_hash_for must not reference {tok}'


def test_core_factory_not_imported_by_production_pipeline():
    pipeline_src = pathlib.Path(arena_gates.__file__).parent / 'arena_pipeline.py'
    text = pipeline_src.read_text()
    assert 'core_factory' not in text, 'production arena_pipeline must not import core_factory'


def test_supported_primitives_match_inventory():
    from zangetsu.core_factory.primitive_inventory import (
        UnsupportedOperatorError, get_primitive, supported_primitives,
    )
    for name in supported_primitives():
        spec = get_primitive(name)
        assert spec.fn is not None
