import streamlit as st
from zangetsu.dashboard.data_sources.batch_artifacts import load_latest_batch
from zangetsu.dashboard.view_models.candidates import apply_filters, candidates_dataframe

st.set_page_config(page_title='Candidates', page_icon='🔍', layout='wide')
st.title('Candidate Explorer')

bv = load_latest_batch()
df = candidates_dataframe(bv)
if df.empty:
    st.warning('NO DATA — shadow_batch_results missing or empty.')
    st.stop()

st.caption(f'{len(df)} candidates loaded from {bv.folder_name}.')

c1, c2, c3, c4, c5 = st.columns(5)
axis = c1.selectbox('Axis', ['(any)'] + sorted(df['axis_id'].dropna().unique().tolist()))
status = c2.selectbox('Status', ['(any)', 'PASSED', 'REJECTED', 'NOT_EVALUATED', 'ERROR'])
symbol = c3.selectbox('Symbol', ['(any)'] + sorted(df['symbol'].dropna().unique().tolist()))
side = c4.selectbox('Side mode', ['(any)'] + sorted(df['intended_side_mode'].dropna().unique().tolist()))
reasons = sorted([r for r in df['reject_reason'].dropna().unique().tolist()])
reason = c5.selectbox('Reject reason', ['(any)'] + reasons)

search = st.text_input('Search candidate_id / alpha_hash (substring)')

filtered = apply_filters(
    df,
    axis=None if axis == '(any)' else axis,
    status=None if status == '(any)' else status,
    symbol=None if symbol == '(any)' else symbol,
    side_mode=None if side == '(any)' else side,
    reject_reason=None if reason == '(any)' else reason,
    search=search or None,
)

st.subheader(f'Results ({len(filtered)} rows)')
display_cols = [c for c in ['candidate_id', 'axis_id', 'symbol', 'timeframe',
                            'intended_side_mode', 'status', 'reject_reason',
                            'blocker_reason', 'gross_bps', 'net_bps', 'trade_count',
                            'a1_pass', 'a2_pass', 'alpha_hash'] if c in filtered.columns]
st.dataframe(filtered[display_cols].head(2000), use_container_width=True, height=600)
