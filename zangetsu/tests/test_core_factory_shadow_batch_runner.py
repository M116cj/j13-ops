import pathlib
from zangetsu.core_factory.shadow_batch_runner import run

def test_shadow_batch_minimum(tmp_path):
    out = tmp_path / 'out'
    summary = run(generation_id='t-min', candidate_count_per_axis=24,
                  axes=('H', 'C', 'D'), symbols=('BTCUSDT',), timeframe='1h',
                  output_dir=out)
    assert summary['candidates_total'] >= 24 * 3
    for a in ('H', 'C', 'D'):
        assert summary['candidates_per_axis'][a] >= 24
    assert (out / 'candidate_manifest.jsonl').exists()
    assert (out / 'shadow_batch_results.jsonl').exists()
    assert (out / 'axis_scoreboard.csv').exists()
    assert (out / 'reject_reason_summary.json').exists()
    assert (out / 'long_short_summary.csv').exists()
    assert (out / 'feedback_weights.json').exists()
    assert (out / 'near_survivor_report.csv').exists()
    assert (out / 'formula_collision_report.csv').exists()
