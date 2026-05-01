import json
import pathlib

import pandas as pd
from zangetsu.dashboard.data_sources.parsers import (
    parse_csv, parse_json, parse_jsonl, latest_recovery_dir,
)


def test_jsonl_parse_ok(tmp_path):
    p = tmp_path / 'a.jsonl'
    p.write_text('{"x": 1}\n{"x": 2}\n')
    r = parse_jsonl(p)
    assert r.state == 'OK'
    assert len(r.rows) == 2


def test_jsonl_missing(tmp_path):
    r = parse_jsonl(tmp_path / 'nope.jsonl')
    assert r.state == 'MISSING'


def test_jsonl_empty(tmp_path):
    p = tmp_path / 'empty.jsonl'
    p.write_text('')
    r = parse_jsonl(p)
    assert r.state == 'EMPTY'


def test_jsonl_error(tmp_path):
    p = tmp_path / 'bad.jsonl'
    p.write_text('not-json\n')
    r = parse_jsonl(p)
    assert r.state == 'ERROR'


def test_json_ok(tmp_path):
    p = tmp_path / 'a.json'
    p.write_text(json.dumps({'a': 1}))
    r = parse_json(p)
    assert r.state == 'OK'


def test_csv_ok(tmp_path):
    p = tmp_path / 'a.csv'
    p.write_text('x,y\n1,2\n')
    r = parse_csv(p)
    assert r.state == 'OK'
    assert len(r.rows) == 1


def test_latest_recovery_dir(tmp_path):
    (tmp_path / '20260430-abc').mkdir()
    (tmp_path / '20260501-xyz').mkdir()
    out = latest_recovery_dir(tmp_path)
    assert out.name == '20260501-xyz'
