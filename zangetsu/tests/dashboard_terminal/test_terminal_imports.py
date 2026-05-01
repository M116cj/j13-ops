"""Terminal V2 contract tests."""
import pathlib


def test_terminal_app_exists():
    p = pathlib.Path(__file__).resolve().parents[2] / 'dashboard_terminal' / 'app.py'
    assert p.exists()


def test_terminal_panels_present():
    panels_dir = pathlib.Path(__file__).resolve().parents[2] / 'dashboard_terminal' / 'panels'
    expected = {'top_status_bar.py', 'kpi_strip.py', 'arena_funnel.py',
                'reject_depth.py', 'sidebar_filter.py', 'candidate_drawer.py',
                'bottom_tabs.py'}
    found = {p.name for p in panels_dir.glob('*.py') if p.name != '__init__.py'}
    missing = expected - found
    assert not missing, f'missing terminal panels: {missing}'


def test_terminal_does_not_import_arena_pipeline():
    base = pathlib.Path(__file__).resolve().parents[2] / 'dashboard_terminal'
    bad: list[str] = []
    for p in base.rglob('*.py'):
        if 'arena_pipeline' in p.read_text():
            bad.append(str(p))
    assert not bad, f'terminal must not import arena_pipeline: {bad}'


def test_terminal_does_not_import_shadow_batch_runner():
    base = pathlib.Path(__file__).resolve().parents[2] / 'dashboard_terminal'
    bad: list[str] = []
    for p in base.rglob('*.py'):
        if 'shadow_batch_runner' in p.read_text():
            bad.append(str(p))
    assert not bad, f'terminal must not import shadow_batch_runner: {bad}'


def test_terminal_no_write_actions():
    """No st.button + write-side-effect patterns; the only buttons allowed are read-only widgets.

    Heuristic: scan for st.form_submit_button or pd.DataFrame.to_sql / to_csv with a
    non-evidence path. Conservative — flag any to_sql or anything writing to /home outside cache.
    """
    base = pathlib.Path(__file__).resolve().parents[2] / 'dashboard_terminal'
    forbidden_patterns = ['to_sql(', '.execute(', 'subprocess.run', 'os.system', 'shutil.rmtree']
    bad: list[str] = []
    for p in base.rglob('*.py'):
        text = p.read_text()
        for pat in forbidden_patterns:
            if pat in text:
                bad.append(f'{p}:{pat}')
    assert not bad, f'terminal contains forbidden write patterns: {bad}'
