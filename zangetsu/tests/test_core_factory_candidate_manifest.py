import pathlib
from zangetsu.core_factory.candidate_manifest import (
    candidate_id_for, expand_formulas_to_candidates, write_manifest_jsonl, read_manifest_jsonl,
)
from zangetsu.core_factory.combination_grammar import generate_formulas

def test_candidate_id_deterministic():
    cid1 = candidate_id_for(generation_id='g1', axis_id='H', alpha_hash='abc',
                            symbol='BTCUSDT', timeframe='15m', intended_side_mode='LONG')
    cid2 = candidate_id_for(generation_id='g1', axis_id='H', alpha_hash='abc',
                            symbol='BTCUSDT', timeframe='15m', intended_side_mode='LONG')
    assert cid1 == cid2 and len(cid1) == 64

def test_candidate_id_differs_by_axis():
    cid_h = candidate_id_for(generation_id='g1', axis_id='H', alpha_hash='abc',
                             symbol='BTCUSDT', timeframe='15m', intended_side_mode='LONG')
    cid_c = candidate_id_for(generation_id='g1', axis_id='C', alpha_hash='abc',
                             symbol='BTCUSDT', timeframe='15m', intended_side_mode='LONG')
    assert cid_h != cid_c

def test_manifest_roundtrip(tmp_path):
    formulas = list(generate_formulas('H', 4, seed=0))
    formulas = [s for s in formulas if s.primitive_family != 'UNSUPPORTED']
    cands = list(expand_formulas_to_candidates(formulas, generation_id='t',
                                               symbols=('BTCUSDT',), timeframe='15m',
                                               side_modes=('LONG','SHORT')))
    p = tmp_path / 'm.jsonl'
    n = write_manifest_jsonl(cands, p)
    assert n == len(cands)
    back = read_manifest_jsonl(p)
    assert len(back) == n
    assert back[0].candidate_id == cands[0].candidate_id
