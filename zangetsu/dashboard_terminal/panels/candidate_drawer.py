"""Right-side candidate detail drawer (terminal style)."""
from __future__ import annotations
from typing import Optional
import streamlit as st


def render(df, selected_id: Optional[str], manifest_df) -> None:
    st.markdown('<div class="zt-card-title">CANDIDATE DETAIL</div>', unsafe_allow_html=True)
    if df is None or df.empty:
        st.markdown('<div class="zt-card zt-muted zt-mono" style="font-size:12px;">NO DATA</div>',
                    unsafe_allow_html=True)
        return
    if not selected_id:
        st.markdown('<div class="zt-card zt-muted zt-mono" style="font-size:12px;">'
                    'Select candidate_id below to inspect.</div>', unsafe_allow_html=True)
        return
    row = df[df['candidate_id'] == selected_id]
    if row.empty:
        st.markdown(f'<div class="zt-card zt-muted">No candidate matches {selected_id[:12]}…</div>',
                    unsafe_allow_html=True)
        return
    r = row.iloc[0]
    formula = ''
    grammar = ''
    primitive = ''
    if manifest_df is not None and 'alpha_hash' in manifest_df.columns:
        m = manifest_df[manifest_df['alpha_hash'] == r['alpha_hash']]
        if not m.empty:
            mr = m.iloc[0]
            formula = mr.get('formula', '')
            grammar = mr.get('grammar_family', '')
            primitive = mr.get('primitive_family', '')
    status = r.get('status', 'UNKNOWN')
    status_cls = {'PASSED': 'zt-tag-pass', 'REJECTED': 'zt-tag-rej',
                  'NOT_EVALUATED': 'zt-tag-na', 'ERROR': 'zt-tag-rej'}.get(status, 'zt-tag-na')
    reject = r.get('reject_reason') or 'n/a'
    blocker = r.get('blocker_reason') or 'n/a'
    near_eligible = (status == 'REJECTED'
                     and r.get('net_bps') is not None
                     and -5.0 <= float(r['net_bps']) <= 0.0)
    near_html = f'<span class="zt-tag zt-tag-near">NEAR</span>' if near_eligible else '<span class="zt-muted">no</span>'

    html = f'''
<div class="zt-card">
  <div style="display:flex;gap:8px;align-items:center;">
    <span class="zt-tag {status_cls}">{status}</span>
    <span class="zt-mono zt-muted" style="font-size:11px;">{selected_id[:24]}…</span>
  </div>
  <div style="margin-top:8px;font-family:ui-monospace,JetBrains Mono;font-size:11px;">
    <div><span class="zt-muted">SYMBOL</span> {r.get('symbol', 'n/a')}
         <span class="zt-muted" style="margin-left:10px;">SIDE</span> {r.get('intended_side_mode', 'n/a')}
         <span class="zt-muted" style="margin-left:10px;">TF</span> {r.get('timeframe', 'n/a')}</div>
    <div><span class="zt-muted">AXIS</span> {r.get('axis_id', 'n/a')}
         <span class="zt-muted" style="margin-left:10px;">GRAMMAR</span> {grammar}
         <span class="zt-muted" style="margin-left:10px;">PRIMITIVE</span> {primitive}</div>
    <div><span class="zt-muted">ALPHA_HASH</span> <span class="zt-mono">{r.get('alpha_hash', 'n/a')[:32]}…</span></div>
    <div style="margin-top:6px;">
      <span class="zt-muted">GROSS</span> <span class="zt-mono">{r.get('gross_bps', 0):.3f}</span> bps
      <span class="zt-muted" style="margin-left:8px;">COST</span> <span class="zt-mono">{r.get('cost_bps', 0):.3f}</span> bps
      <span class="zt-muted" style="margin-left:8px;">NET</span>
      <span class="zt-mono" style="color:{'#22c55e' if r.get('net_bps', 0) > 0 else '#ef4444'}">{r.get('net_bps', 0):.3f}</span> bps
    </div>
    <div>
      <span class="zt-muted">TRADES</span> <span class="zt-mono">{r.get('trade_count', 0)}</span>
      <span class="zt-muted" style="margin-left:8px;">LONG</span> <span class="zt-mono">{r.get('long_trade_count', 0)}</span>
      <span class="zt-muted" style="margin-left:8px;">SHORT</span> <span class="zt-mono">{r.get('short_trade_count', 0)}</span>
    </div>
    <div style="margin-top:6px;">
      <span class="zt-muted">REJECT</span> <span>{reject}</span>
      <span class="zt-muted" style="margin-left:8px;">BLOCKER</span> <span>{blocker}</span>
    </div>
    <div><span class="zt-muted">NEAR-ELIGIBLE</span> {near_html}</div>
    <div style="margin-top:8px;"><span class="zt-muted">FORMULA</span></div>
    <pre style="background:#0b0f17;border:1px solid #1f2735;border-radius:4px;padding:6px;color:#38bdf8;font-size:10px;white-space:pre-wrap;word-break:break-all;">{formula or 'n/a'}</pre>
    <div class="zt-muted" style="font-size:10px;">Read-only · copy from row above as needed.</div>
  </div>
</div>'''
    st.markdown(html, unsafe_allow_html=True)
