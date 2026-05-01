"""Mobile terminal V3 smoke + contract tests."""
import importlib
import pathlib
import re

import pytest
from fastapi.testclient import TestClient

from zangetsu.dashboard_mobile.app import app


client = TestClient(app)


def test_health_endpoint():
    r = client.get('/_stcore/health')
    assert r.status_code == 200
    assert r.json() == {'status': 'ok'}


def test_root_renders_200_and_dark():
    r = client.get('/')
    assert r.status_code == 200
    body = r.text
    assert 'ZANGETSU' in body
    # Must include viewport meta + theme-color black
    assert 'viewport' in body and 'width=device-width' in body
    assert '#000' in body or 'black' in body.lower()


def test_all_routes_return_200():
    for path in ('/', '/funnel', '/candidates', '/rejects', '/survivors',
                 '/feedback', '/health'):
        r = client.get(path)
        assert r.status_code == 200, f'{path} returned {r.status_code}'


def test_no_fake_zero_in_overview_when_data_exists():
    r = client.get('/')
    body = r.text
    # When data exists, NO DATA strings should NOT appear inside KPI values.
    # We check that the topbar pill values aren't all '0' from being collapsed.
    # The page must contain at least one PASSED count visible.
    assert re.search(r'PASSED.*?\d', body, re.S)


def test_not_evaluated_pill_distinct_from_rejected_in_topbar():
    r = client.get('/')
    body = r.text
    # Both NEV (not_evaluated) and ERR pills must exist in the topbar
    assert '>NEV<' in body
    assert '>ERR<' in body
    # And UNKNOWN_REJECT must be its own pill
    assert '>UNK<' in body


def test_survivors_strictly_separated():
    r = client.get('/survivors')
    assert r.status_code == 200
    body = r.text
    assert 'Survivors' in body or 'SURV' in body
    assert 'Near-survivors' in body or 'NEAR' in body
    # Two distinct sections
    assert body.count('<table') >= 2


def test_app_is_read_only_no_write_paths():
    """FastAPI app must not declare POST/PUT/PATCH/DELETE routes."""
    forbidden = {'POST', 'PUT', 'PATCH', 'DELETE'}
    for route in app.routes:
        methods = getattr(route, 'methods', None)
        if methods:
            bad = methods & forbidden
            assert not bad, f'mobile terminal must not expose {bad} on {route.path}'


def test_no_arena_pipeline_or_runner_imports():
    base = pathlib.Path(__file__).resolve().parents[2] / 'dashboard_mobile'
    bad = []
    for p in base.rglob('*.py'):
        text = p.read_text()
        if 'arena_pipeline' in text or 'shadow_batch_runner' in text:
            bad.append(str(p))
    assert not bad, f'forbidden imports in mobile terminal: {bad}'


def test_no_write_call_patterns():
    base = pathlib.Path(__file__).resolve().parents[2] / 'dashboard_mobile'
    forbidden_patterns = ['to_sql(', '.execute(', 'subprocess.run', 'os.system', 'shutil.rmtree']
    bad = []
    for p in base.rglob('*.py'):
        t = p.read_text()
        for pat in forbidden_patterns:
            if pat in t:
                bad.append(f'{p}:{pat}')
    assert not bad, f'mobile terminal contains forbidden write patterns: {bad}'


def test_candidate_detail_route_404_for_unknown():
    r = client.get('/candidate/UNKNOWN_CANDIDATE_ID')
    assert r.status_code == 404
