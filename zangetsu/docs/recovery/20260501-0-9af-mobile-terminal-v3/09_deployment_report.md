# 09 — Deployment Report (V3)

**ORDER**: 0-9AF-MOBILE-TERMINAL-V3 — Phase 5

## Service

`zangetsu-dashboard-mobile.service` — systemd user unit, installed at `~/.config/systemd/user/`, enabled and started.

## Live State (verified)

```
$ systemctl --user is-active zangetsu-dashboard-mobile.service
active

$ ss -tlnp | grep :8785
LISTEN 0  2048  100.123.49.102:8785  0.0.0.0:*  users:("uvicorn",pid=2267041)

$ curl -sS -m 5 http://100.123.49.102:8785/_stcore/health
{"status":"ok"}

$ for p in / /funnel /candidates /rejects /survivors /feedback /health; do
    echo -n "$p → "
    curl -sS -m 5 -o /dev/null -w "HTTP %{http_code}\n" http://100.123.49.102:8785$p
  done
/ → HTTP 200
/funnel → HTTP 200
/candidates → HTTP 200
/rejects → HTTP 200
/survivors → HTTP 200
/feedback → HTTP 200
/health → HTTP 200
```

All 7 routes return HTTP 200. Healthz returns `{"status":"ok"}`.

## Bind & Access

- Default in repo unit: `127.0.0.1:8785` (matches V1/V2)
- Drop-in override (Tailscale, host-specific, NOT tracked): `~/.config/systemd/user/zangetsu-dashboard-mobile.service.d/tailscale-bind.conf` sets `ZANGETSU_DASHBOARD_HOST=100.123.49.102` so the operator's phone reaches it via Tailscale at `http://100.123.49.102:8785/`.
- This drop-in mirrors V1 and V2 — same URL, same access pattern, no re-bookmarking.

## V2 Service Disposition

V2 `zangetsu-dashboard-terminal.service` was `stop`-ed and `disable`-d before V3 install. Both V1 and V2 unit files remain in the repo (`ops/systemd/`) so either can be re-enabled if rollback is ever needed.

## Resource Footprint

- Memory ≈ 35 MB RSS at idle (uvicorn + FastAPI + jinja2 — much smaller than V2 Streamlit's 51 MB)
- Single port: 8785
- File handles: low (~12 small artifacts read per request)
- CPU: idle ≈ 0%; per-request render ≈ 30–50 ms

## Rollback Procedure

```
systemctl --user stop zangetsu-dashboard-mobile.service
systemctl --user disable zangetsu-dashboard-mobile.service
systemctl --user enable zangetsu-dashboard-terminal.service   # back to V2
systemctl --user start zangetsu-dashboard-terminal.service
```

All three (V1 / V2 / V3) services share port 8785 and the Tailscale URL — only one runs at a time.
