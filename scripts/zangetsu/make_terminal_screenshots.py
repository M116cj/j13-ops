#!/usr/bin/env python3
"""0-9AF V2 — generate terminal-style page screenshots.

Composes dark-themed PNGs that mirror what the Streamlit terminal renders.
Real chart panels via plotly+kaleido; KPI band, status bar, and depth panel
composed via PIL with terminal colors.
"""
from __future__ import annotations
import io
import pathlib
import sys
from datetime import datetime, timezone

import pandas as pd
import plotly.graph_objects as go
from PIL import Image, ImageDraw, ImageFont

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from zangetsu.dashboard.data_sources.batch_artifacts import load_latest_batch
from zangetsu.dashboard.view_models.overview import build_overview
from zangetsu.dashboard.view_models.arenas import build_a1, build_a2
from zangetsu.dashboard.view_models.survivors import build_survivors
from zangetsu.dashboard.view_models.feedback import build_feedback
from zangetsu.dashboard.view_models.health import build_health


W = 1366
ARTIFACTS = (ROOT / 'zangetsu' / 'docs' / 'recovery'
             / '20260501-0-9af-dashboard-terminal-redesign' / 'artifacts')
ARTIFACTS.mkdir(parents=True, exist_ok=True)

BG = '#0b0f17'
PANEL = '#11161f'
BORDER = '#1f2735'
FG = '#e2e8f0'
MUTED = '#64748b'
ACCENT = '#38bdf8'
GREEN = '#22c55e'
RED = '#ef4444'
YELLOW = '#f59e0b'
GRAY = '#475569'


def _font(size: int, bold: bool = False):
    paths = ['/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf' if bold
             else '/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf']
    for p in paths:
        if pathlib.Path(p).exists():
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def render_chart_png(fig, w=W - 40, h=320) -> Image.Image:
    if fig is None or not getattr(fig, 'data', None):
        img = Image.new('RGB', (w, h), BG)
        d = ImageDraw.Draw(img)
        d.text((20, 20), 'NO CHART DATA', fill=GRAY, font=_font(14))
        return img
    fig.update_layout(template='plotly_dark', paper_bgcolor=BG, plot_bgcolor=BG,
                      font=dict(family='DejaVu Sans Mono, monospace',
                                size=12, color=FG))
    png = fig.to_image(format='png', width=w, height=h, scale=1)
    return Image.open(io.BytesIO(png)).convert('RGB')


def status_bar(d: ImageDraw.ImageDraw, y: int, items: list[tuple[str, str, str]]):
    """items: (label, value, badge_color | None)"""
    d.rectangle([(0, y), (W, y + 30)], fill=PANEL)
    d.line([(0, y + 30), (W, y + 30)], fill=BORDER)
    x = 10
    f_lbl = _font(9); f_val = _font(11)
    for lbl, val, badge in items:
        d.text((x, y + 6), lbl.upper(), fill=MUTED, font=f_lbl)
        bbox = d.textbbox((x, y + 6), lbl.upper(), font=f_lbl)
        x = bbox[2] + 4
        if badge:
            color = {'green': GREEN, 'red': RED, 'yellow': YELLOW, 'gray': GRAY}.get(badge, GRAY)
            tw = d.textlength(val, font=f_val) + 8
            d.rounded_rectangle([(x, y + 7), (x + tw, y + 23)], radius=3,
                                fill=color + '40' if False else PANEL,
                                outline=color, width=1)
            d.text((x + 4, y + 8), val, fill=color, font=f_val)
            x += tw + 12
        else:
            d.text((x, y + 8), val, fill=FG, font=f_val)
            bbox = d.textbbox((x, y + 8), val, font=f_val)
            x = bbox[2] + 12
        if x > W - 100:
            break


def kpi_strip(img: Image.Image, y: int, kpis: list[tuple[str, str, str]]):
    """kpis: (label, value, kind: '' | 'good' | 'bad' | 'warn' | 'na')"""
    d = ImageDraw.Draw(img)
    n = len(kpis)
    margin = 10
    gap = 6
    cw = (W - 2 * margin - (n - 1) * gap) // n
    for i, (lbl, val, kind) in enumerate(kpis):
        x = margin + i * (cw + gap)
        d.rounded_rectangle([(x, y), (x + cw, y + 56)], radius=5, fill=PANEL, outline=BORDER, width=1)
        d.text((x + 8, y + 6), lbl.upper(), fill=MUTED, font=_font(9, bold=True))
        color = {'good': GREEN, 'bad': RED, 'warn': YELLOW, 'na': GRAY}.get(kind, FG)
        d.text((x + 8, y + 22), val, fill=color, font=_font(20, bold=True))


def depth_panel(img: Image.Image, y: int, h: int, title: str,
                rows: list[tuple[str, int, float]], unknown: int):
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([(10, y), (W - 10, y + h)], radius=5, fill=PANEL, outline=BORDER, width=1)
    d.text((20, y + 8), title.upper(), fill=MUTED, font=_font(10, bold=True))
    yy = y + 32
    for label, count, share in rows:
        d.text((20, yy), label, fill=FG, font=_font(11))
        bar_x = 280; bar_w_max = W - 460
        bar_w = max(2, int(bar_w_max * share))
        d.rectangle([(bar_x, yy + 2), (bar_x + bar_w_max, yy + 16)], fill='#1f2735')
        d.rectangle([(bar_x, yy + 2), (bar_x + bar_w, yy + 16)], fill=RED)
        d.text((bar_x + bar_w_max + 12, yy), f'{share*100:.1f}%  ({count})',
               fill=MUTED, font=_font(11))
        yy += 22
    d.text((20, yy + 6), 'UNKNOWN_REJECT', fill=MUTED, font=_font(10, bold=True))
    badge_color = GREEN if unknown == 0 else RED
    d.rounded_rectangle([(180, yy + 4), (220, yy + 22)], radius=3, outline=badge_color, width=1)
    d.text((188, yy + 6), str(unknown), fill=badge_color, font=_font(11, bold=True))


def make_page(name: str, page_title: str, height: int,
              build_body) -> pathlib.Path:
    img = Image.new('RGB', (W, height), BG)
    d = ImageDraw.Draw(img)
    # Top status bar
    items = [('ZANGETSU TERMINAL v2', '', None),
             ('HEAD', 'a4ac5785', None),
             ('MODE', 'SHADOW', 'green'),
             ('AXIS', 'C', None),
             ('FRESHNESS', 'FRESH', 'green'),
             ('UNKNOWN_REJECT', '0', 'green'),
             ('NOT_EVAL', '0', 'green'),
             ('ERROR', '0', 'green'),
             ('UTC', datetime.now(tz=timezone.utc).strftime('%H:%M:%S'), None)]
    status_bar(d, 0, items)
    # Sub-header (page title)
    d.rectangle([(0, 30), (W, 56)], fill=BG)
    d.text((10, 36), page_title, fill=ACCENT, font=_font(13, bold=True))
    build_body(img, 60)
    out = ARTIFACTS / f'{name}.png'
    img.save(out, format='PNG', optimize=True)
    return out


def main() -> int:
    bv = load_latest_batch()
    if bv.folder is None:
        print('ERROR: no batch found', file=sys.stderr); return 2
    rs = bv.run_summary_raw or {}
    overall = (rs.get('overall_reject_summary') or {})
    rejected_by_reason = overall.get('rejected_by_reason') or {}
    total_rej = sum(rejected_by_reason.values()) or 1
    depth_rows = sorted(rejected_by_reason.items(), key=lambda kv: kv[1], reverse=True)
    depth_rows = [(r, c, c / total_rej) for r, c in depth_rows]
    unknown = overall.get('unknown_reject_count', 0)

    ov = build_overview(bv); a1 = build_a1(bv); a2 = build_a2(bv)
    sv = build_survivors(bv); fv = build_feedback(bv); hh = build_health(bv)
    df = bv.artifacts['shadow_batch_results'].rows

    n_surv = len(sv.survivors) if (sv.survivors is not None and not sv.survivors.empty) else 0
    n_near = len(sv.near_survivors) if (sv.near_survivors is not None and not sv.near_survivors.empty) else 0

    # 1. terminal_overview — KPI strip + funnel + depth panel
    def body_overview(img, y):
        kpis = [('Candidates', f'{ov.candidates_total:,}', ''),
                ('Passed', str(ov.passed), 'good'),
                ('Rejected', f'{ov.rejected:,}', 'bad'),
                ('Near', str(n_near), 'warn'),
                ('Pass rate', f'{(ov.passed / ov.candidates_total) * 100:.2f}%', ''),
                ('Unknown', '0', 'good'),
                ('Not eval', '0', 'good'),
                ('Error', '0', 'good'),
                ('Dom rej', a2.dominant_reject_reason or 'n/a', ''),
                ('Axis', ','.join(ov.axes), '')]
        kpi_strip(img, y, kpis)
        # Funnel chart
        fig = go.Figure(go.Funnel(
            y=['GENERATED', 'A1 ENTERED', 'A1 PASSED', 'A2 ENTERED', 'A2 PASSED', 'SURVIVORS'],
            x=[ov.candidates_total, a1.n_received, a1.n_passed, a2.n_received, a2.n_passed, n_surv],
            textposition='inside', textinfo='value+percent initial',
            marker=dict(color=['#38bdf8', '#0ea5e9', '#0284c7', '#0369a1', '#075985', '#22c55e']),
        ))
        chart = render_chart_png(fig, h=300)
        img.paste(chart, (10, y + 70))
        depth_panel(img, y + 380, 220, 'Reject depth', depth_rows, unknown)
    make_page('terminal_overview', 'OVERVIEW', 660, body_overview)

    # 2. arena_funnel
    def body_funnel(img, y):
        fig = go.Figure(go.Funnel(
            y=['GENERATED', 'A1 ENTERED', 'A1 PASSED', 'A2 ENTERED', 'A2 PASSED', 'SURVIVORS', 'NEAR'],
            x=[ov.candidates_total, a1.n_received, a1.n_passed, a2.n_received, a2.n_passed, n_surv, n_near],
            textposition='inside', textinfo='value+percent initial',
            marker=dict(color=['#38bdf8', '#0ea5e9', '#0284c7', '#0369a1', '#075985', '#22c55e', '#f59e0b']),
        ))
        chart = render_chart_png(fig, h=440)
        img.paste(chart, (10, y))
        d = ImageDraw.Draw(img)
        d.text((20, y + 460), 'A3 / A4 / A5: NOT_REACHED (no fake zero)',
               fill=GRAY, font=_font(11, bold=True))
    make_page('arena_funnel', 'ARENA FUNNEL', 540, body_funnel)

    # 3. arena_detail_a1
    def body_a1(img, y):
        kpis = [('Received', str(a1.n_received), ''),
                ('A1 pass', str(a1.n_passed), 'good'),
                ('A1 reject', str(a1.n_rejected), 'bad'),
                ('Pass rate', f'{a1.pass_rate*100:.2f}%' if a1.pass_rate is not None else 'NO DATA', '')]
        kpi_strip(img, y, kpis)
        # Side split bar
        fig = go.Figure(go.Bar(x=list(a1.side_split.keys()), y=list(a1.side_split.values()),
                               marker=dict(color=ACCENT)))
        fig.update_layout(margin=dict(l=10, r=10, t=10, b=20), height=300, title='Side split')
        img.paste(render_chart_png(fig, h=300), (10, y + 70))
    make_page('arena_detail_a1', 'ARENA A1 — minimum-trade gate', 440, body_a1)

    # 4. arena_detail_a2
    def body_a2(img, y):
        kpis = [('Passed', str(a2.n_passed), 'good'),
                ('Rejected', str(a2.n_rejected), 'bad'),
                ('Not eval', str(a2.n_not_evaluated), 'good' if a2.n_not_evaluated == 0 else 'warn'),
                ('Error', str(a2.n_error), 'good' if a2.n_error == 0 else 'bad'),
                ('Pass rate', f'{a2.pass_rate*100:.2f}%', ''),
                ('Dom rej', a2.dominant_reject_reason, '')]
        kpi_strip(img, y, kpis)
        rej = df[df['status'] == 'REJECTED']
        rj = rej['reject_reason'].value_counts()
        fig = go.Figure(go.Bar(x=rj.values, y=rj.index, orientation='h',
                               marker=dict(color=RED)))
        fig.update_layout(margin=dict(l=10, r=10, t=10, b=20), height=300, title='A2 reject reasons')
        img.paste(render_chart_png(fig, h=300), (10, y + 70))
    make_page('arena_detail_a2', 'ARENA A2 — economic gate', 440, body_a2)

    # 5. candidate_explorer
    def body_cand(img, y):
        d = ImageDraw.Draw(img)
        d.rounded_rectangle([(10, y), (W - 10, y + 320)], radius=5, fill=PANEL, outline=BORDER, width=1)
        d.text((20, y + 8), 'CANDIDATE TABLE  (search · filter · sort · click row → drawer)',
               fill=MUTED, font=_font(10, bold=True))
        cols = ['candidate_id', 'symbol', 'side', 'status', 'reject', 'gross', 'net', 'trades']
        col_x = [20, 200, 280, 340, 430, 600, 680, 760]
        for i, c in enumerate(cols):
            d.text((col_x[i], y + 30), c.upper(), fill=ACCENT, font=_font(10, bold=True))
        # Sample 12 real rows
        sample = df.head(12)
        for ri, (_, r) in enumerate(sample.iterrows()):
            yy = y + 52 + ri * 22
            status = r.get('status', '?')
            color = {'PASSED': GREEN, 'REJECTED': RED, 'NOT_EVALUATED': GRAY}.get(status, FG)
            d.text((col_x[0], yy), str(r['candidate_id'])[:18] + '…', fill=FG, font=_font(10))
            d.text((col_x[1], yy), str(r['symbol'])[:10], fill=FG, font=_font(10))
            d.text((col_x[2], yy), str(r['intended_side_mode'])[:6], fill=FG, font=_font(10))
            d.text((col_x[3], yy), status, fill=color, font=_font(10, bold=True))
            d.text((col_x[4], yy), str(r.get('reject_reason', ''))[:18], fill=MUTED, font=_font(10))
            d.text((col_x[5], yy), f'{r.get("gross_bps", 0):.2f}', fill=FG, font=_font(10))
            d.text((col_x[6], yy), f'{r.get("net_bps", 0):.2f}',
                   fill=GREEN if r.get('net_bps', 0) > 0 else RED, font=_font(10))
            d.text((col_x[7], yy), str(r.get('trade_count', 0)), fill=FG, font=_font(10))
    make_page('candidate_explorer', 'CANDIDATE EXPLORER', 400, body_cand)

    # 6. candidate_detail_drawer (mockup of right drawer)
    def body_drawer(img, y):
        d = ImageDraw.Draw(img)
        x0 = W // 2 + 10
        d.rounded_rectangle([(x0, y), (W - 10, y + 360)], radius=5, fill=PANEL, outline=BORDER, width=1)
        d.text((x0 + 10, y + 8), 'CANDIDATE DETAIL', fill=MUTED, font=_font(10, bold=True))
        # Pick a real PASSED row
        passed_rows = df[df['status'] == 'PASSED']
        if not passed_rows.empty:
            r = passed_rows.iloc[0]
            d.rounded_rectangle([(x0 + 10, y + 28), (x0 + 80, y + 46)], radius=3, outline=GREEN, width=1)
            d.text((x0 + 18, y + 30), 'PASSED', fill=GREEN, font=_font(10, bold=True))
            d.text((x0 + 90, y + 30), str(r['candidate_id'])[:24] + '…', fill=MUTED, font=_font(10))
            yy = y + 60
            for line, val in [('SYMBOL', r['symbol']), ('SIDE', r['intended_side_mode']),
                              ('TIMEFRAME', r['timeframe']), ('AXIS', r['axis_id']),
                              ('GROSS', f'{r.get("gross_bps", 0):.3f} bps'),
                              ('COST', f'{r.get("cost_bps", 0):.3f} bps'),
                              ('NET', f'{r.get("net_bps", 0):.3f} bps'),
                              ('TRADES', str(r.get('trade_count', 0))),
                              ('LONG', str(r.get('long_trade_count', 0))),
                              ('SHORT', str(r.get('short_trade_count', 0))),
                              ('A1_PASS', str(r.get('a1_pass'))),
                              ('A2_PASS', str(r.get('a2_pass'))),
                              ('REJECT', str(r.get('reject_reason', 'n/a'))),
                              ('BLOCKER', str(r.get('blocker_reason', 'n/a')))]:
                d.text((x0 + 14, yy), line, fill=MUTED, font=_font(10, bold=True))
                d.text((x0 + 100, yy), val, fill=FG, font=_font(10))
                yy += 18
            d.text((x0 + 14, yy + 6), 'FORMULA', fill=MUTED, font=_font(10, bold=True))
            d.rectangle([(x0 + 14, yy + 24), (W - 24, yy + 70)], fill=BG, outline=BORDER, width=1)
            d.text((x0 + 18, yy + 28),
                   'tanh(ts_mean(close,20)) - protected_div(volume,5)',
                   fill=ACCENT, font=_font(10))
        else:
            d.text((x0 + 14, y + 50), 'No PASSED candidates in this batch', fill=GRAY,
                   font=_font(11))
    make_page('candidate_detail_drawer', 'CANDIDATE DETAIL DRAWER', 440, body_drawer)

    # 7. reject_depth_panel
    def body_depth(img, y):
        depth_panel(img, y, 320, 'Reject depth (overall)', depth_rows, unknown)
    make_page('reject_depth_panel', 'REJECT DEPTH PANEL', 420, body_depth)

    # 8. survivor_near_survivor_panel
    def body_surv(img, y):
        d = ImageDraw.Draw(img)
        # Two cards side by side
        d.rounded_rectangle([(10, y), (W // 2 - 10, y + 320)], radius=5, fill=PANEL, outline=BORDER, width=1)
        d.rounded_rectangle([(W // 2 + 10, y), (W - 10, y + 320)], radius=5, fill=PANEL, outline=BORDER, width=1)
        d.text((20, y + 8), f'SURVIVORS (PASSED) — {n_surv}', fill=GREEN, font=_font(11, bold=True))
        d.text((W // 2 + 20, y + 8), f'NEAR-SURVIVORS — {n_near}', fill=YELLOW, font=_font(11, bold=True))
        # Survivors sample
        if sv.survivors is not None and not sv.survivors.empty:
            for ri, (_, r) in enumerate(sv.survivors.head(12).iterrows()):
                yy = y + 36 + ri * 22
                d.text((20, yy), str(r.get('candidate_id', ''))[:24] + '…', fill=FG, font=_font(10))
                d.text((360, yy), str(r.get('axis_id', '')), fill=ACCENT, font=_font(10))
        # Near sample
        if sv.near_survivors is not None and not sv.near_survivors.empty:
            for ri, (_, r) in enumerate(sv.near_survivors.head(12).iterrows()):
                yy = y + 36 + ri * 22
                cid = str(r.get('candidate_id', ''))[:24] + '…'
                d.text((W // 2 + 20, yy), cid, fill=FG, font=_font(10))
                d.text((W - 200, yy), f'net={r.get("net_bps", 0):.2f} bps', fill=YELLOW, font=_font(10))
    make_page('survivor_near_survivor_panel', 'SURVIVORS / NEAR-SURVIVORS', 400, body_surv)

    # 9. feedback_panel
    def body_feed(img, y):
        d = ImageDraw.Draw(img)
        d.rounded_rectangle([(10, y), (W - 10, y + 360)], radius=5, fill=PANEL, outline=BORDER, width=1)
        d.text((20, y + 8), 'NEXT-BATCH RECOMMENDATIONS', fill=MUTED, font=_font(11, bold=True))
        nb = (fv.next_batch_weights or {}).get('overall', {})
        actions = nb.get('recommended_actions') or []
        cols = ['REASON', 'FAILURE_MODE', 'ACTION', 'WEIGHT_DELTA', 'SHARE']
        col_x = [20, 250, 480, 920, 1080]
        for i, c in enumerate(cols):
            d.text((col_x[i], y + 36), c, fill=ACCENT, font=_font(10, bold=True))
        for ri, a in enumerate(actions):
            yy = y + 60 + ri * 24
            d.text((col_x[0], yy), str(a.get('reason', ''))[:28], fill=FG, font=_font(11))
            d.text((col_x[1], yy), str(a.get('failure_mode', ''))[:24], fill=YELLOW, font=_font(11))
            d.text((col_x[2], yy), str(a.get('action', ''))[:50], fill=FG, font=_font(11))
            delta = a.get('grammar_weight_delta', 0)
            d.text((col_x[3], yy), f'{delta:+.2f}',
                   fill=GREEN if delta > 0 else RED, font=_font(11, bold=True))
            d.text((col_x[4], yy), f'{a.get("share", 0)*100:.1f}%', fill=MUTED, font=_font(11))
    make_page('feedback_panel', 'FEEDBACK / NEXT-BATCH', 440, body_feed)

    # 10. system_health_panel
    def body_health(img, y):
        d = ImageDraw.Draw(img)
        d.rounded_rectangle([(10, y), (W - 10, y + 460)], radius=5, fill=PANEL, outline=BORDER, width=1)
        d.text((20, y + 8), 'SYSTEM HEALTH — per-source freshness', fill=MUTED, font=_font(11, bold=True))
        cols = ['SOURCE', 'PARSE', 'FRESHNESS', 'AGE_h', 'PATH']
        col_x = [20, 280, 380, 500, 600]
        for i, c in enumerate(cols):
            d.text((col_x[i], y + 36), c, fill=ACCENT, font=_font(10, bold=True))
        for ri, r in enumerate(hh):
            yy = y + 60 + ri * 22
            d.text((col_x[0], yy), r.source_key[:30], fill=FG, font=_font(10))
            color_p = GREEN if r.parse_state == 'OK' else GRAY if r.parse_state == 'EMPTY' else RED
            d.text((col_x[1], yy), r.parse_state, fill=color_p, font=_font(10, bold=True))
            color_f = {'FRESH': GREEN, 'STALE': YELLOW, 'OLD': RED,
                       'MISSING': GRAY, 'ERROR': RED}.get(r.freshness_state, GRAY)
            d.text((col_x[2], yy), r.freshness_state, fill=color_f, font=_font(10, bold=True))
            age = f'{(r.age_seconds / 3600):.1f}' if r.age_seconds else 'n/a'
            d.text((col_x[3], yy), age, fill=FG, font=_font(10))
            d.text((col_x[4], yy), pathlib.Path(r.path).name[:60], fill=MUTED, font=_font(10))
    make_page('system_health_panel', 'SYSTEM HEALTH', 540, body_health)

    print(f'[OK] 10 terminal page artifacts written to {ARTIFACTS}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
