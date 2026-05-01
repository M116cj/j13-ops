"""V3.1 realtime guarantees."""
import re
from fastapi.testclient import TestClient
from zangetsu.dashboard_mobile.app import app

client = TestClient(app)


def test_no_cache_headers_on_html():
    r = client.get('/')
    cc = r.headers.get('cache-control', '').lower()
    assert 'no-store' in cc and 'no-cache' in cc, f'expected no-store no-cache, got {cc!r}'


def test_refresh_meta_is_10s():
    r = client.get('/')
    assert r.status_code == 200
    m = re.search(r'http-equiv="refresh" content="(\d+)"', r.text)
    assert m, 'meta refresh tag missing'
    assert int(m.group(1)) <= 15, f'refresh interval too long: {m.group(1)}s'


def test_data_age_pill_in_topbar():
    r = client.get('/')
    assert 'live-data-age' in r.text
    assert 'live-refresh-in' in r.text


def test_data_mtime_attr_present():
    r = client.get('/')
    assert 'data-data-mtime' in r.text
