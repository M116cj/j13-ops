import os
import pathlib
import time

from zangetsu.dashboard.data_sources.runtime_health import freshness_for


def test_missing_file(tmp_path):
    fr = freshness_for(tmp_path / 'nope')
    assert fr.exists is False
    assert fr.state == 'MISSING'


def test_fresh_file(tmp_path):
    p = tmp_path / 'x'
    p.write_text('hello')
    fr = freshness_for(p)
    assert fr.exists is True
    assert fr.state == 'FRESH'
    assert fr.age_seconds is not None


def test_old_file(tmp_path):
    p = tmp_path / 'x'
    p.write_text('hello')
    very_old = time.time() - 60 * 60 * 24 * 365  # 1 year old
    os.utime(p, (very_old, very_old))
    fr = freshness_for(p)
    assert fr.state == 'OLD'
