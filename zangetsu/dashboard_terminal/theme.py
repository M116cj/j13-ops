"""ZANGETSU Terminal — dark theme + dense layout CSS injection."""
from __future__ import annotations

TERMINAL_CSS = '''
<style>
:root {
  --bg: #0b0f17;
  --panel: #11161f;
  --panel-2: #161c27;
  --border: #1f2735;
  --fg: #e2e8f0;
  --muted: #64748b;
  --accent: #38bdf8;
  --green: #22c55e;
  --red: #ef4444;
  --yellow: #f59e0b;
  --gray: #475569;
  --mono: ui-monospace, SFMono-Regular, 'JetBrains Mono', Menlo, monospace;
}
.stApp { background: var(--bg); color: var(--fg); }
section.main > div { padding-top: 0.4rem !important; padding-bottom: 0.6rem !important; }
.block-container { padding: 0.4rem 0.8rem 0.6rem 0.8rem !important; max-width: 100% !important; }
[data-testid="stHeader"] { background: var(--bg); }
[data-testid="stSidebar"] { background: var(--panel) !important; border-right: 1px solid var(--border); }
.zt-status-bar {
  position: sticky; top: 0; z-index: 999;
  background: var(--panel-2); border-bottom: 1px solid var(--border);
  padding: 6px 10px; margin: -8px -16px 8px -16px;
  font-family: var(--mono); font-size: 12px; color: var(--fg);
  display: flex; flex-wrap: wrap; gap: 14px;
}
.zt-status-bar .item { display: inline-flex; align-items: center; gap: 4px; }
.zt-status-bar .label { color: var(--muted); text-transform: uppercase; font-size: 10px; letter-spacing: 0.6px; }
.zt-status-bar .val { color: var(--fg); }
.zt-status-bar .badge {
  display: inline-block; padding: 1px 6px; border-radius: 4px;
  font-size: 10px; font-weight: 700;
}
.zt-status-bar .badge-green { background: rgba(34,197,94,0.18); color: var(--green); }
.zt-status-bar .badge-red { background: rgba(239,68,68,0.18); color: var(--red); }
.zt-status-bar .badge-yellow { background: rgba(245,158,11,0.18); color: var(--yellow); }
.zt-status-bar .badge-gray { background: rgba(71,85,105,0.30); color: var(--gray); }

.zt-card {
  background: var(--panel); border: 1px solid var(--border);
  border-radius: 6px; padding: 8px 10px; margin-bottom: 6px;
}
.zt-card-title {
  color: var(--muted); text-transform: uppercase; letter-spacing: 0.6px;
  font-size: 10px; margin-bottom: 4px;
}
.zt-kpi {
  background: var(--panel); border: 1px solid var(--border);
  border-radius: 6px; padding: 6px 10px; height: 60px;
}
.zt-kpi .label { color: var(--muted); font-size: 10px; text-transform: uppercase; letter-spacing: 0.6px; }
.zt-kpi .val { color: var(--fg); font-family: var(--mono); font-size: 22px; font-weight: 700; }
.zt-kpi .sub { color: var(--muted); font-size: 10px; }
.zt-kpi.zt-good .val { color: var(--green); }
.zt-kpi.zt-bad .val { color: var(--red); }
.zt-kpi.zt-warn .val { color: var(--yellow); }
.zt-kpi.zt-na .val { color: var(--gray); }

div[data-testid="stMetric"] {
  background: var(--panel); border: 1px solid var(--border);
  border-radius: 6px; padding: 6px 10px;
}
div[data-testid="stMetricLabel"] p { color: var(--muted) !important; font-size: 10px !important; text-transform: uppercase; }
div[data-testid="stMetricValue"] { color: var(--fg) !important; font-family: var(--mono); font-size: 20px !important; font-weight: 700 !important; }

.stTabs [data-baseweb="tab-list"] { gap: 0; border-bottom: 1px solid var(--border); }
.stTabs [data-baseweb="tab"] {
  background: transparent; color: var(--muted); padding: 6px 12px;
  font-size: 12px; text-transform: uppercase; letter-spacing: 0.5px;
}
.stTabs [aria-selected="true"] { color: var(--accent); border-bottom: 2px solid var(--accent); }

[data-testid="stDataFrame"] {
  background: var(--panel); border: 1px solid var(--border); border-radius: 6px;
}

.zt-depth-row { display: flex; align-items: center; gap: 8px; padding: 3px 0; font-family: var(--mono); font-size: 12px; }
.zt-depth-row .lbl { width: 220px; color: var(--fg); }
.zt-depth-row .bar-wrap { flex: 1; background: rgba(71,85,105,0.18); border-radius: 2px; height: 14px; position: relative; }
.zt-depth-row .bar { height: 14px; border-radius: 2px; background: linear-gradient(90deg, var(--red) 0%, rgba(239,68,68,0.3) 100%); }
.zt-depth-row .pct { width: 60px; text-align: right; color: var(--muted); }

.zt-tag { display: inline-block; padding: 1px 6px; border-radius: 3px; font-family: var(--mono); font-size: 10px; }
.zt-tag-pass { background: rgba(34,197,94,0.18); color: var(--green); }
.zt-tag-rej { background: rgba(239,68,68,0.18); color: var(--red); }
.zt-tag-near { background: rgba(245,158,11,0.18); color: var(--yellow); }
.zt-tag-na { background: rgba(71,85,105,0.30); color: var(--gray); }

p, div, span { color: var(--fg); }
.zt-mono { font-family: var(--mono); }
.zt-muted { color: var(--muted); }
.zt-green { color: var(--green); }
.zt-red { color: var(--red); }
.zt-yellow { color: var(--yellow); }
</style>
'''
