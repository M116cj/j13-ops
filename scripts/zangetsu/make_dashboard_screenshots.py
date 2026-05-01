#!/usr/bin/env python3
"""0-9AF — generate dashboard page screenshots from the latest mining batch.

Headless browsers are unavailable on Alaya. This script renders the same
charts the Streamlit pages render (via plotly+kaleido) and composites a
page-level mockup PNG with the page title, KPI lines, and chart panels.

Output: zangetsu/docs/recovery/20260501-0-9af-internal-observability-dashboard-v1/artifacts/*.png
"""
from __future__ import annotations
import io
import json
import pathlib
import sys
from datetime import datetime, timezone

import pandas as pd
from PIL import Image, ImageDraw, ImageFont

# Make repo importable
ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from zangetsu.dashboard.config import RECOVERY_ROOT
from zangetsu.dashboard.data_sources.batch_artifacts import load_latest_batch
from zangetsu.dashboard.view_models.overview import build_overview
from zangetsu.dashboard.view_models.arenas import build_a1, build_a2, build_a3
from zangetsu.dashboard.view_models.candidates import candidates_dataframe
from zangetsu.dashboard.view_models.survivors import build_survivors
from zangetsu.dashboard.view_models.feedback import build_feedback
from zangetsu.dashboard.view_models.health import build_health, now_iso
from zangetsu.dashboard.components.charts import (
    bar_top_n, funnel_chart, status_donut, reject_reason_stacked,
)


CANVAS_W, CANVAS_H = 1280, 800
HEADER_H = 100
KPI_H = 80
CHART_H = 480

ARTIFACTS_DIR = (
    ROOT / 'zangetsu' / 'docs' / 'recovery'
    / '20260501-0-9af-internal-observability-dashboard-v1' / 'artifacts'
)
ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)


def _font(size: int):
    for path in (
        '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
        '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
    ):
        if pathlib.Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def render_chart_png(fig, w=1240, h=CHART_H) -> Image.Image:
    if fig is None or not getattr(fig, 'data', None):
        # Fallback empty chart
        img = Image.new('RGB', (w, h), 'white')
        d = ImageDraw.Draw(img)
        d.text((20, 20), 'No chart data', fill='#636e72', font=_font(20))
        return img
    png_bytes = fig.to_image(format='png', width=w, height=h, scale=1)
    return Image.open(io.BytesIO(png_bytes)).convert('RGB')


def make_page(name: str, title: str, subtitle: str, kpis: list[tuple[str, str]],
              chart_imgs: list[Image.Image], note: str | None = None) -> pathlib.Path:
    n_charts = max(1, len(chart_imgs))
    height = HEADER_H + KPI_H + CHART_H * n_charts + 80
    img = Image.new('RGB', (CANVAS_W, height), 'white')
    d = ImageDraw.Draw(img)
    # Header
    d.rectangle([(0, 0), (CANVAS_W, HEADER_H)], fill='#0d1b2a')
    d.text((20, 20), title, fill='white', font=_font(28))
    d.text((20, 60), subtitle, fill='#a8dadc', font=_font(14))
    # KPI band
    kpi_y = HEADER_H
    d.rectangle([(0, kpi_y), (CANVAS_W, kpi_y + KPI_H)], fill='#f1f5f9')
    if kpis:
        col_w = CANVAS_W // len(kpis)
        for i, (k, v) in enumerate(kpis):
            x = i * col_w + 20
            d.text((x, kpi_y + 8), k, fill='#475569', font=_font(13))
            d.text((x, kpi_y + 30), str(v), fill='#0f172a', font=_font(24))
    # Charts
    y = HEADER_H + KPI_H + 10
    for ch in chart_imgs:
        img.paste(ch, (20, y))
        y += CHART_H + 10
    # Footer note
    if note:
        d.text((20, height - 30), note, fill='#94a3b8', font=_font(12))
    out = ARTIFACTS_DIR / f'{name}.png'
    img.save(out, format='PNG', optimize=True)
    return out


def main() -> int:
    bv = load_latest_batch()
    if bv.folder is None:
        print('ERROR: no batch found', file=sys.stderr)
        return 2
    folder = bv.folder_name
    rs = bv.run_summary_raw or {}
    overview = build_overview(bv)
    timestamp = now_iso()
    sub = f'{folder} · render time {timestamp}'

    # 1. Overview
    reasons = ((rs.get('overall_reject_summary') or {}).get('rejected_by_reason') or {})
    df_results = bv.artifacts['shadow_batch_results'].rows
    counts = {'PASSED': int((df_results['status'] == 'PASSED').sum()),
              'REJECTED': int((df_results['status'] == 'REJECTED').sum()),
              'NOT_EVAL': int((df_results['status'] == 'NOT_EVALUATED').sum()),
              'ERROR': int((df_results['status'] == 'ERROR').sum())}
    sym_counts = df_results['symbol'].value_counts().to_dict()
    funnel = funnel_chart([('Generated', overview.candidates_total or 0),
                           ('Evaluated', counts['PASSED'] + counts['REJECTED']),
                           ('Passed', counts['PASSED'])])
    make_page(
        'overview_page', 'Overview', sub,
        [('Candidates', overview.candidates_total or 'NO DATA'),
         ('PASSED', overview.passed if overview.passed is not None else 'NO DATA'),
         ('REJECTED', overview.rejected if overview.rejected is not None else 'NO DATA'),
         ('UNKNOWN_REJECT', overview.unknown_reject if overview.unknown_reject is not None else 'NO DATA')],
        [render_chart_png(funnel, h=300),
         render_chart_png(bar_top_n(reasons, title='Top reject reasons'), h=300),
         render_chart_png(status_donut(counts), h=300)],
        note='No fake zero · NOT_EVALUATED is distinct from REJECTED · Survivor != Deployable',
    )

    # 2. Core Factory
    mdf = bv.artifacts['candidate_manifest'].rows
    grammar_counts = mdf['grammar_family'].value_counts().to_dict() if 'grammar_family' in mdf.columns else {}
    primitive_counts = mdf['primitive_family'].value_counts().to_dict() if 'primitive_family' in mdf.columns else {}
    side_counts = mdf['intended_side_mode'].value_counts().to_dict() if 'intended_side_mode' in mdf.columns else {}
    make_page(
        'core_factory_page', 'Core Factory Funnel', sub,
        [('Candidates', len(mdf)),
         ('Unique formulas', mdf['alpha_hash'].nunique()),
         ('Symbols', mdf['symbol'].nunique() if 'symbol' in mdf.columns else 'NO DATA'),
         ('Grammar families', len(grammar_counts) if grammar_counts else 'NO DATA')],
        [render_chart_png(bar_top_n(grammar_counts, title='By grammar_family'), h=300),
         render_chart_png(bar_top_n(primitive_counts, title='By primitive_family'), h=300),
         render_chart_png(bar_top_n(sym_counts, title='Candidates per symbol', n=14), h=300)],
        note='Stages: Primitive Universe -> Combination Grammar -> Generator -> Arena -> Survivor -> Feedback',
    )

    # 3-5. Arena pages
    a1 = build_a1(bv); a2 = build_a2(bv); a3 = build_a3(bv)
    make_page(
        'arena_a1_page', 'Arena A1 — minimum-trade gate', sub,
        [('Received', a1.n_received or 'NO DATA'),
         ('A1 pass', a1.n_passed if a1.n_passed is not None else 'NO DATA'),
         ('A1 reject', a1.n_rejected if a1.n_rejected is not None else 'NO DATA'),
         ('A1 pass rate', f'{(a1.pass_rate or 0):.2%}' if a1.pass_rate is not None else 'NO DATA')],
        [render_chart_png(bar_top_n(a1.side_split or {}, title='Side split'), h=300)],
        note='A1 = trade_count >= 5 (sanity).' ,
    )
    make_page(
        'arena_a2_page', 'Arena A2 — economic gate', sub,
        [('PASSED', a2.n_passed or 0), ('REJECTED', a2.n_rejected or 0),
         ('NOT_EVALUATED', a2.n_not_evaluated or 0), ('ERROR', a2.n_error or 0)],
        [render_chart_png(bar_top_n(a2.side_split or {}, title='Side split'), h=300),
         render_chart_png(
            bar_top_n(df_results[df_results['status'] == 'REJECTED']['reject_reason'].value_counts().to_dict(),
                      title='A2 reject reasons'), h=300)],
        note=f'Dominant reject: {a2.dominant_reject_reason}; A2_MIN_TRADES={overview.a2_min_trades} unchanged',
    )
    # A3 — placeholder per NOT_AVAILABLE
    img_a3 = Image.new('RGB', (1240, 240), 'white')
    d_a3 = ImageDraw.Draw(img_a3)
    d_a3.text((20, 20), 'A3 = NOT_AVAILABLE',  fill='#d63031', font=_font(28))
    d_a3.text((20, 60), 'A3 segmented holdout is not run in current SHADOW orders.',
              fill='#475569', font=_font(16))
    d_a3.text((20, 90), 'Page is reserved for future scale-up orders.',
              fill='#475569', font=_font(16))
    make_page('arena_a3_page', 'Arena A3 — segmented holdout', sub,
              [('State', 'NOT_AVAILABLE')], [img_a3],
              note='No-fake-zero rule: shown as NOT_AVAILABLE not as 0/0.')

    # 6. Candidates
    df_cand = candidates_dataframe(bv)
    side_pass = df_cand[df_cand['status'] == 'PASSED']['intended_side_mode'].value_counts().to_dict() if not df_cand.empty else {}
    make_page(
        'candidates_page', 'Candidate Explorer', sub,
        [('Total', len(df_cand) if not df_cand.empty else 'NO DATA'),
         ('Statuses', df_cand['status'].nunique() if 'status' in df_cand.columns else 'NO DATA'),
         ('Symbols', df_cand['symbol'].nunique() if 'symbol' in df_cand.columns else 'NO DATA'),
         ('Axes', df_cand['axis_id'].nunique() if 'axis_id' in df_cand.columns else 'NO DATA')],
        [render_chart_png(bar_top_n(side_pass, title='PASSED candidates by side mode'), h=300),
         render_chart_png(
            bar_top_n(df_cand['axis_id'].value_counts().to_dict() if 'axis_id' in df_cand.columns else {},
                      title='Candidates by axis'), h=300)],
        note='Filters: axis / status / symbol / side / reject_reason / search',
    )

    # 7. Survivors
    sv = build_survivors(bv)
    n_surv = len(sv.survivors) if sv.survivors is not None and not sv.survivors.empty else 0
    n_near = len(sv.near_survivors) if sv.near_survivors is not None and not sv.near_survivors.empty else 0
    surv_by_sym = sv.survivors['symbol'].value_counts().to_dict() if (sv.survivors is not None and 'symbol' in sv.survivors.columns and not sv.survivors.empty) else {}
    make_page(
        'survivors_page', 'Survivors / Near-Survivors', sub,
        [('Survivors', n_surv), ('Near-survivors', n_near),
         ('NOT_EVALUATED', overview.not_evaluated or 0), ('ERROR', overview.error or 0)],
        [render_chart_png(bar_top_n(surv_by_sym, title='Survivors per symbol'), h=300)],
        note='Strict separation. Survivor != Deployable. NOT_EVALUATED excluded from both.',
    )

    # 8. Rejects
    rej = df_results[df_results['status'] == 'REJECTED']
    by_sym_reasons = rej.groupby(['symbol', 'reject_reason']).size().reset_index(name='n') if not rej.empty else None
    by_side_reasons = rej.groupby(['intended_side_mode', 'reject_reason']).size().reset_index(name='n') if not rej.empty else None
    make_page(
        'rejects_page', 'Reject Reason Explorer', sub,
        [('Rejected total', len(rej)),
         ('UNKNOWN_REJECT', int((rej['reject_reason'] == 'UNKNOWN_REJECT').sum()) if not rej.empty else 0),
         ('Symbols', rej['symbol'].nunique() if not rej.empty else 'NO DATA'),
         ('Sides', rej['intended_side_mode'].nunique() if not rej.empty else 'NO DATA')],
        [render_chart_png(bar_top_n(rej['reject_reason'].value_counts().to_dict() if not rej.empty else {},
                                    title='Reject reasons (overall)'), h=300),
         render_chart_png(reject_reason_stacked(by_sym_reasons, 'symbol'), h=320) if by_sym_reasons is not None else render_chart_png(None, h=300),
         render_chart_png(reject_reason_stacked(by_side_reasons, 'intended_side_mode'), h=300) if by_side_reasons is not None else render_chart_png(None, h=300)],
        note='UNKNOWN_REJECT explicit; never silent.',
    )

    # 9. Feedback
    fv = build_feedback(bv)
    fw = (fv.feedback_weights or {}).get('overall', {})
    nb = (fv.next_batch_weights or {}).get('overall', {})
    weights = fw.get('weights') or {}
    actions = nb.get('recommended_actions') or []
    make_page(
        'feedback_page', 'Feedback / Next-Batch Weights', sub,
        [('Feedback status', fw.get('status', 'NO DATA')),
         ('Rejected total', nb.get('rejected_total', 'NO DATA')),
         ('Recommended actions', len(actions)),
         ('UNKNOWN_REJECT', nb.get('unknown_reject_count', 'NO DATA'))],
        [render_chart_png(bar_top_n(weights, title='feedback_weights (share of rejections)'), h=320),
         render_chart_png(bar_top_n({a.get('reason'): a.get('share', 0) for a in actions if isinstance(a, dict)},
                                    title='Recommended action shares'), h=300)],
        note='No fake economic feedback — empty_with_reason if blocked.',
    )

    # 10. System Health
    hrows = build_health(bv)
    fresh = sum(1 for r in hrows if r.freshness_state == 'FRESH')
    stale = sum(1 for r in hrows if r.freshness_state in {'STALE', 'OLD'})
    missing = sum(1 for r in hrows if r.freshness_state == 'MISSING')
    parse_err = sum(1 for r in hrows if r.parse_state == 'ERROR')
    state_counts = {r.freshness_state: 0 for r in hrows}
    for r in hrows:
        state_counts[r.freshness_state] += 1
    make_page(
        'system_health_page', 'System Health', sub,
        [('FRESH', fresh), ('STALE/OLD', stale), ('MISSING', missing), ('PARSE_ERR', parse_err)],
        [render_chart_png(bar_top_n(state_counts, title='Source freshness states'), h=300)],
        note=f'Dashboard refresh time (UTC): {timestamp}',
    )

    print(f'[OK] 10 page artifacts written to {ARTIFACTS_DIR}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
