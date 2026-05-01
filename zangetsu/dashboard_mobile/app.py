"""ZANGETSU Mobile Terminal V3 — FastAPI + Jinja2, mobile-first dark UI.

Read-only: no DB writes, no exchange API, no runtime mutation.
Internal-only: bind 127.0.0.1 (or Tailscale IP via ZANGETSU_DASHBOARD_HOST env).
"""
from __future__ import annotations
import os
import pathlib
from datetime import datetime, timezone
from collections import Counter

from fastapi import FastAPI, Request, Query, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from zangetsu.dashboard.data_sources.batch_artifacts import load_latest_batch
from zangetsu.dashboard.view_models.overview import build_overview
from zangetsu.dashboard.view_models.arenas import build_a1, build_a2
from zangetsu.dashboard.view_models.candidates import apply_filters
from zangetsu.dashboard.view_models.survivors import build_survivors
from zangetsu.dashboard.view_models.feedback import build_feedback
from zangetsu.dashboard.view_models.health import build_health


PKG = pathlib.Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(PKG / 'templates'))

app = FastAPI(title='ZANGETSU Mobile Terminal v3', docs_url=None, redoc_url=None,
              openapi_url=None)
app.mount('/static', StaticFiles(directory=str(PKG / 'static')), name='static')


def _head_sha() -> str | None:
    try:
        head_path = pathlib.Path('/home/j13/j13-ops/.git/HEAD')
        if not head_path.exists():
            return None
        ref = head_path.read_text().strip()
        if ref.startswith('ref: '):
            ref_path = pathlib.Path('/home/j13/j13-ops/.git') / ref[5:]
            if ref_path.exists():
                return ref_path.read_text().strip()
        return ref
    except Exception:
        return None


def _common_ctx(active: str) -> dict:
    bv = load_latest_batch()
    ov = build_overview(bv)
    fr = bv.freshness.get('run_summary')
    fr_state = fr.state if fr else 'UNKNOWN'
    fr_class = {'FRESH': 'green', 'STALE': 'yellow', 'OLD': 'red',
                'MISSING': 'gray', 'ERROR': 'red'}.get(fr_state, 'gray')
    return {
        'active': active, 'bv': bv, 'ov': ov,
        'fresh_state': fr_state, 'fresh_class': fr_class,
        'now_utc': datetime.now(tz=timezone.utc).strftime('%H:%M:%S UTC'),
    }


@app.get('/', response_class=HTMLResponse)
def overview(request: Request):
    ctx = _common_ctx('overview')
    bv = ctx['bv']; ov = ctx['ov']
    rs = bv.run_summary_raw or {}
    reasons = ((rs.get('overall_reject_summary') or {}).get('rejected_by_reason') or {})
    total_rej = sum(reasons.values()) or 1
    top_rejects = [{'label': r, 'count': c, 'pct': c / total_rej * 100}
                   for r, c in sorted(reasons.items(), key=lambda kv: kv[1], reverse=True)]
    df = bv.artifacts.get('shadow_batch_results')
    near_count = None
    symbol_rows = []
    if df and df.state == 'OK' and df.rows is not None:
        rows = df.rows
        near_count = int(((rows['status'] == 'REJECTED') &
                          (rows['net_bps'] >= -5.0) & (rows['net_bps'] <= 0.0)).sum())
        # by-symbol
        for sym in sorted(rows['symbol'].dropna().unique().tolist()):
            sub = rows[rows['symbol'] == sym]
            symbol_rows.append({
                'symbol': sym,
                'n': len(sub),
                'passed': int((sub['status'] == 'PASSED').sum()),
                'no_trade': int((sub['reject_reason'] == 'no_trades_generated').sum()),
            })
        # sort by passed desc then n desc
        symbol_rows.sort(key=lambda s: (-s['passed'], -s['n']))
    pass_rate = None
    if ov.passed is not None and ov.candidates_total:
        pass_rate = f'{(ov.passed / ov.candidates_total) * 100:.2f}%'
    return templates.TemplateResponse(request, 'overview.html', {
        **ctx, 'request': request,
        'top_rejects': top_rejects, 'near_count': near_count,
        'pass_rate': pass_rate, 'symbol_rows': symbol_rows[:20],
    })


@app.get('/funnel', response_class=HTMLResponse)
def funnel(request: Request):
    ctx = _common_ctx('funnel')
    bv = ctx['bv']; ov = ctx['ov']
    a1 = build_a1(bv); a2 = build_a2(bv)
    sv_art = bv.artifacts.get('survivor_report')
    near_art = bv.artifacts.get('near_survivor_report')
    n_surv = len(sv_art.rows) if (sv_art and sv_art.state == 'OK' and sv_art.rows is not None) else 0
    n_near = len(near_art.rows) if (near_art and near_art.state == 'OK' and near_art.rows is not None) else 0
    base = ov.candidates_total or 1
    stages = [
        {'name': 'GENERATED', 'value': ov.candidates_total or 0, 'pct': 100, 'na': False},
        {'name': 'A1 ENT', 'value': a1.n_received or 0, 'pct': (a1.n_received or 0) / base * 100, 'na': False},
        {'name': 'A1 PASS', 'value': a1.n_passed or 0, 'pct': (a1.n_passed or 0) / base * 100, 'na': False},
        {'name': 'A2 ENT', 'value': a2.n_received or 0, 'pct': (a2.n_received or 0) / base * 100, 'na': False},
        {'name': 'A2 PASS', 'value': a2.n_passed or 0, 'pct': (a2.n_passed or 0) / base * 100, 'na': False},
        {'name': 'A3', 'value': 'NOT_REACHED', 'pct': 0, 'na': True},
        {'name': 'A4', 'value': 'NOT_REACHED', 'pct': 0, 'na': True},
        {'name': 'A5', 'value': 'NOT_REACHED', 'pct': 0, 'na': True},
        {'name': 'SURVIVORS', 'value': n_surv, 'pct': max(0.5, (n_surv / base) * 100), 'na': False},
    ]
    df = bv.artifacts.get('shadow_batch_results')
    side_rows = []
    rejects = []
    if df and df.state == 'OK' and df.rows is not None:
        rows = df.rows
        side_total = len(rows)
        for side in sorted(rows['intended_side_mode'].dropna().unique().tolist()):
            sub = rows[rows['intended_side_mode'] == side]
            side_rows.append({
                'side': side, 'value': len(sub),
                'pct': len(sub) / max(side_total, 1) * 100,
                'color': '#22c55e' if side == 'LONG' else '#ef4444' if side == 'SHORT' else '#38bdf8',
            })
    rs = bv.run_summary_raw or {}
    reasons = ((rs.get('overall_reject_summary') or {}).get('rejected_by_reason') or {})
    rt = sum(reasons.values()) or 1
    rejects = [{'label': r, 'count': c, 'pct': c / rt * 100}
               for r, c in sorted(reasons.items(), key=lambda kv: kv[1], reverse=True)]
    return templates.TemplateResponse(request, 'funnel.html', {
        **ctx, 'request': request, 'stages': stages,
        'side_rows': side_rows, 'rejects': rejects,
    })


@app.get('/candidates', response_class=HTMLResponse)
def candidates(request: Request, status: str = '', symbol: str = '',
               side: str = '', q: str = '', limit: int = 200):
    ctx = _common_ctx('candidates')
    bv = ctx['bv']
    df_art = bv.artifacts.get('shadow_batch_results')
    df = df_art.rows if (df_art and df_art.state == 'OK') else None
    if df is None or df.empty:
        return templates.TemplateResponse(request, 'candidates.html', {
            **ctx, 'request': request, 'rows': [], 'shown': 0, 'total': 0,
            'status': status, 'symbol': symbol, 'side': side, 'q': q, 'symbols': [],
        })
    symbols = sorted(df['symbol'].dropna().unique().tolist())
    filtered = apply_filters(
        df,
        status=status or None, symbol=symbol or None,
        side_mode=side or None, search=q or None,
    )
    rows = filtered.head(limit).to_dict('records')
    return templates.TemplateResponse(request, 'candidates.html', {
        **ctx, 'request': request, 'rows': rows,
        'shown': len(rows), 'total': len(df),
        'status': status, 'symbol': symbol, 'side': side, 'q': q, 'symbols': symbols,
    })


@app.get('/candidate/{cid}', response_class=HTMLResponse)
def candidate_detail(request: Request, cid: str):
    ctx = _common_ctx('candidates')
    bv = ctx['bv']
    df_art = bv.artifacts.get('shadow_batch_results')
    if not df_art or df_art.state != 'OK' or df_art.rows is None:
        raise HTTPException(404, 'no batch results')
    rows = df_art.rows[df_art.rows['candidate_id'] == cid]
    if rows.empty:
        raise HTTPException(404, f'candidate {cid} not found')
    r = rows.iloc[0].to_dict()
    near_eligible = (r.get('status') == 'REJECTED' and r.get('net_bps') is not None
                     and -5.0 <= float(r['net_bps']) <= 0.0)
    formula = grammar = primitive = ''
    m_art = bv.artifacts.get('candidate_manifest')
    if m_art and m_art.state == 'OK' and m_art.rows is not None:
        m = m_art.rows[m_art.rows['alpha_hash'] == r.get('alpha_hash')]
        if not m.empty:
            mr = m.iloc[0]
            formula = mr.get('formula', '')
            grammar = mr.get('grammar_family', '')
            primitive = mr.get('primitive_family', '')
    return templates.TemplateResponse(request, 'candidate_detail.html', {
        **ctx, 'request': request, 'r': r,
        'near_eligible': near_eligible,
        'formula': formula or '—', 'grammar': grammar or '—', 'primitive': primitive or '—',
    })


@app.get('/rejects', response_class=HTMLResponse)
def rejects(request: Request):
    ctx = _common_ctx('rejects')
    bv = ctx['bv']
    df_art = bv.artifacts.get('shadow_batch_results')
    df = df_art.rows if (df_art and df_art.state == 'OK') else None
    rej_total = 0; by_reason = []; by_symbol = []; by_side = []
    if df is not None and not df.empty:
        rej = df[df['status'] == 'REJECTED']
        rej_total = len(rej)
        if rej_total:
            counts = rej['reject_reason'].value_counts()
            for r, c in counts.items():
                by_reason.append({'label': r, 'count': int(c), 'pct': c / rej_total * 100})
            for sym in sorted(rej['symbol'].dropna().unique().tolist()):
                sub = rej[rej['symbol'] == sym]
                by_symbol.append({
                    'symbol': sym, 'rej': len(sub),
                    'no_trade': int((sub['reject_reason'] == 'no_trades_generated').sum()),
                    'non_pos': int((sub['reject_reason'] == 'non_positive_net').sum()),
                    'too_few': int((sub['reject_reason'] == 'too_few_trades').sum()),
                })
            for side in sorted(rej['intended_side_mode'].dropna().unique().tolist()):
                sub = rej[rej['intended_side_mode'] == side]
                by_side.append({
                    'side': side, 'rej': len(sub),
                    'no_trade': int((sub['reject_reason'] == 'no_trades_generated').sum()),
                    'non_pos': int((sub['reject_reason'] == 'non_positive_net').sum()),
                    'too_few': int((sub['reject_reason'] == 'too_few_trades').sum()),
                })
    return templates.TemplateResponse(request, 'rejects.html', {
        **ctx, 'request': request,
        'rej_total': rej_total, 'by_reason': by_reason,
        'by_symbol': by_symbol, 'by_side': by_side,
    })


@app.get('/survivors', response_class=HTMLResponse)
def survivors(request: Request):
    ctx = _common_ctx('survivors')
    bv = ctx['bv']
    view = build_survivors(bv)
    n_surv = 0; n_near = 0; surv = []; near = []
    df_art = bv.artifacts.get('shadow_batch_results')
    df_results = df_art.rows if (df_art and df_art.state == 'OK') else None
    if view.survivors is not None and not view.survivors.empty:
        n_surv = len(view.survivors)
        # Enrich with net_bps + symbol from results if missing
        for _, sr in view.survivors.head(50).iterrows():
            cid = sr.get('candidate_id')
            base = {'candidate_id': cid,
                    'symbol': sr.get('symbol', ''),
                    'intended_side_mode': sr.get('intended_side_mode', ''),
                    'net_bps': float(sr.get('net_bps', 0) or 0)}
            if df_results is not None:
                hit = df_results[df_results['candidate_id'] == cid]
                if not hit.empty:
                    h = hit.iloc[0]
                    base['symbol'] = h.get('symbol', base['symbol'])
                    base['intended_side_mode'] = h.get('intended_side_mode', base['intended_side_mode'])
                    base['net_bps'] = float(h.get('net_bps', 0) or 0)
            surv.append(base)
    if view.near_survivors is not None and not view.near_survivors.empty:
        n_near = len(view.near_survivors)
        for _, sr in view.near_survivors.head(50).iterrows():
            near.append({
                'candidate_id': sr.get('candidate_id', ''),
                'symbol': sr.get('symbol', ''),
                'intended_side_mode': sr.get('intended_side_mode', ''),
                'net_bps': float(sr.get('net_bps', 0) or 0),
            })
    return templates.TemplateResponse(request, 'survivors.html', {
        **ctx, 'request': request, 'n_surv': n_surv, 'n_near': n_near,
        'survivors': surv, 'near': near,
    })


@app.get('/feedback', response_class=HTMLResponse)
def feedback(request: Request):
    ctx = _common_ctx('feedback')
    bv = ctx['bv']
    fv = build_feedback(bv)
    fw = (fv.feedback_weights or {}).get('overall', {})
    nb = (fv.next_batch_weights or {}).get('overall', {})
    weights = []
    fw_status = fw.get('status') or 'NO DATA'
    if fw_status == 'OK':
        for label, share in (fw.get('weights') or {}).items():
            weights.append({'label': label, 'pct': share * 100})
    actions = nb.get('recommended_actions') or []
    return templates.TemplateResponse(request, 'feedback.html', {
        **ctx, 'request': request,
        'fw_status': fw_status, 'rejected_total': nb.get('rejected_total'),
        'weights': weights, 'actions': actions,
    })


@app.get('/health', response_class=HTMLResponse)
def health(request: Request):
    ctx = _common_ctx('health')
    bv = ctx['bv']
    rows = build_health(bv)
    counts = Counter()
    counts['FRESH'] = sum(1 for r in rows if r.freshness_state == 'FRESH')
    counts['STALE_OR_OLD'] = sum(1 for r in rows if r.freshness_state in {'STALE', 'OLD'})
    counts['MISSING'] = sum(1 for r in rows if r.freshness_state == 'MISSING')
    counts['PARSE_ERR'] = sum(1 for r in rows if r.parse_state == 'ERROR')
    return templates.TemplateResponse(request, 'health.html', {
        **ctx, 'request': request, 'rows': rows,
        'counts': dict(counts), 'head_sha': _head_sha(),
    })


@app.get('/_stcore/health')
def healthz():
    return {'status': 'ok'}


@app.get('/healthz')
def healthz_simple():
    return {'ok': True}
