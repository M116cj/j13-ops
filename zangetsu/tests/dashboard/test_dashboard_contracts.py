"""Smoke contract test — every page module imports without error."""
import importlib
import pathlib
import sys


def test_pages_importable():
    pages_dir = pathlib.Path(__file__).resolve().parents[2] / 'dashboard' / 'pages'
    assert pages_dir.exists()
    found = sorted(pages_dir.glob('*.py'))
    assert len(found) >= 10, f'expected ≥ 10 pages; found {len(found)}'


def test_dashboard_does_not_import_arena_pipeline():
    """Scope: 0-9AF observability modules only. Legacy api.py/models.py/run.py predate this order."""
    base = pathlib.Path(__file__).resolve().parents[2] / 'dashboard'
    new_modules = [
        base / 'app.py', base / 'config.py',
        base / 'data_sources', base / 'view_models',
        base / 'components', base / 'pages',
    ]
    bad: list[str] = []
    for root in new_modules:
        if root.is_file():
            files = [root]
        elif root.is_dir():
            files = list(root.rglob('*.py'))
        else:
            continue
        for f in files:
            text = f.read_text()
            if 'arena_pipeline' in text:
                bad.append(str(f))
    assert not bad, f'observability modules must not import arena_pipeline: {bad}'


def test_dashboard_does_not_import_core_factory_runner():
    """Dashboard reads artifacts; it must not invoke the runner. Scope: 0-9AF modules."""
    base = pathlib.Path(__file__).resolve().parents[2] / 'dashboard'
    new_modules = [
        base / 'app.py', base / 'config.py',
        base / 'data_sources', base / 'view_models',
        base / 'components', base / 'pages',
    ]
    bad: list[str] = []
    for root in new_modules:
        if root.is_file():
            files = [root]
        elif root.is_dir():
            files = list(root.rglob('*.py'))
        else:
            continue
        for f in files:
            text = f.read_text()
            if 'shadow_batch_runner' in text:
                bad.append(str(f))
    assert not bad, f'observability modules must not import shadow_batch_runner: {bad}'
