import pytest
from zangetsu.core_factory.primitive_inventory import (
    UnsupportedOperatorError, get_primitive, supported_primitives,
)

def test_supported_primitives_nonempty():
    s = supported_primitives()
    assert 'add' in s
    assert 'ts_mean' in s

def test_unsupported_fails_closed():
    with pytest.raises(UnsupportedOperatorError):
        get_primitive('not_an_op')

def test_get_primitive_returns_callable():
    spec = get_primitive('add')
    assert callable(spec.fn)
    assert spec.arity == 2
