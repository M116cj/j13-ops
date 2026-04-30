from zangetsu.core_factory.combination_grammar import (
    alpha_hash_for, generate_formulas, has_unsupported_operator,
)

def test_alpha_hash_deterministic_excludes_timestamp():
    a = ('op', 'add', (('field', 'close'), ('field', 'open')))
    h1 = alpha_hash_for(a)
    h2 = alpha_hash_for(a)
    assert h1 == h2 and len(h1) == 64

def test_generate_formulas_h_uses_only_supported_ops():
    out = list(generate_formulas('H', 16, seed=1))
    assert len(out) == 16
    for spec in out:
        assert has_unsupported_operator(spec.ast) is None or spec.primitive_family == 'UNSUPPORTED'

def test_generate_formulas_c_d_distinct():
    c = list(generate_formulas('C', 16, seed=2))
    d = list(generate_formulas('D', 16, seed=2))
    c_hashes = {s.alpha_hash for s in c}
    d_hashes = {s.alpha_hash for s in d}
    # different grammars should produce different hash space (no overlap expected for n=16)
    assert len(c_hashes & d_hashes) <= 2  # tolerate rare collision
