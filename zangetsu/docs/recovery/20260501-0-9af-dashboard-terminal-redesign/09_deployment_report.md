# 09 — Deployment Report

**ORDER**: 0-9AF-REDESIGN — Phase 5

## Service

`zangetsu-dashboard-terminal.service` — systemd user unit, installed at `~/.config/systemd/user/`, enabled and started.

## Live State (verified)

```
$ systemctl --user is-active zangetsu-dashboard-terminal.service
active

$ ss -tlnp | grep :8785
LISTEN 0  2048  100.123.49.102:8785  0.0.0.0:*  users:(streamlit,pid=2166559)

$ curl -sS -m 5 http://100.123.49.102:8785/_stcore/health
ok
```

## Bind & Access

- Default in repo unit: `127.0.0.1:8785` (matches V1 default)
- Drop-in override (Tailscale, host-specific, NOT tracked): `~/.config/systemd/user/zangetsu-dashboard-terminal.service.d/tailscale-bind.conf` sets `ZANGETSU_DASHBOARD_HOST=100.123.49.102` so the operator's mobile can reach it via Tailscale at `http://100.123.49.102:8785/`.
- This drop-in mirrors what existed for V1 — same URL, same access pattern, no operator retraining.

## V1 Service Disposition

V1 `zangetsu-dashboard.service` was `stop`-ed and `disable`-d before V2 install. Both unit files remain in the repo (`ops/systemd/`) so V1 can be re-enabled if rollback is ever needed.

## Resource Footprint

- Memory ≈ 51 MB RSS at idle (single Streamlit process)
- Single port: 8785 (no extra port allocated)
- File handles: low (read-only access to ~12 small artifacts per page render)
- CPU: idle ≈ 0%; per-render < 100 ms

## Rollback Procedure

```
systemctl --user stop zangetsu-dashboard-terminal.service
systemctl --user disable zangetsu-dashboard-terminal.service
systemctl --user enable zangetsu-dashboard.service
systemctl --user start zangetsu-dashboard.service
```

V1 art/report-style dashboard is restored at the same URL. No DB / source-of-truth state is touched by either dashboard.
