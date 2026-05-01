# 07 — Deployment Report

**ORDER**: 0-9AF — Phase 5

## Target

Bind: 127.0.0.1:8785 (internal only).
Owner accesses via Tailscale (Alaya at 100.123.49.102) or SSH tunnel.
No public exposure. No reverse proxy added.

## Service Status (verified)

```
$ systemctl --user status zangetsu-dashboard.service
● zangetsu-dashboard.service - ZANGETSU internal observability dashboard (0-9AF)
     Loaded: loaded (/home/j13/.config/systemd/user/zangetsu-dashboard.service; enabled; preset: enabled)
     Active: active (running) since Fri 2026-05-01 01:37:10 UTC
   Main PID: 2141121 (streamlit)
      Tasks: 4 (limit: 38104)
     Memory: 51.2M (peak: 51.4M)
        CPU: 266ms

$ curl -sS -m 5 http://127.0.0.1:8785/_stcore/health
ok
```

## Healthcheck

The Streamlit core health endpoint `/_stcore/health` returns `ok` and is available for any future uptime monitor / Calcifer probe (no probe added in this order).

## Resource Footprint

- RSS at startup: ~51 MB (Streamlit + plotly + pandas + pyarrow + dashboard code)
- CPU: idle background ≈ 0%; per-page render ~ 50 ms based on local tests
- File handles: low (read-only access to ~12 small artifacts per page render)

## Restart Behavior

`Restart=on-failure` + `RestartSec=5s` ensures the service self-recovers from transient failures. The unit's first observed restart was due to the manual smoke test before full deploy (not a fault).

## Rollback

To stop: `systemctl --user stop zangetsu-dashboard.service`.
To disable persistence: `systemctl --user disable zangetsu-dashboard.service`.
To remove unit: `rm ~/.config/systemd/user/zangetsu-dashboard.service`.
