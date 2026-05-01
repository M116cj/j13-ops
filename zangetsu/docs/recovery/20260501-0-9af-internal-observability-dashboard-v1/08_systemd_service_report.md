# 08 — systemd Service Report

**ORDER**: 0-9AF — Phase 5

## Unit File Location

- Repo source: `ops/systemd/zangetsu-dashboard.service`
- Installed at: `/home/j13/.config/systemd/user/zangetsu-dashboard.service` (symlinked into `default.target.wants/` by `systemctl --user enable`)

## Unit Contents (paraphrased)

```
[Unit]
Description=ZANGETSU internal observability dashboard (0-9AF)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=/home/j13/j13-ops
Environment=PYTHONPATH=/home/j13/j13-ops
Environment=ZANGETSU_DASHBOARD_HOST=127.0.0.1
Environment=ZANGETSU_DASHBOARD_PORT=8785
ExecStart=/home/j13/j13-ops/scripts/zangetsu/run_dashboard.sh
Restart=on-failure
RestartSec=5

# Hardening (read-only, internal):
NoNewPrivileges=yes
ReadWritePaths=/tmp /home/j13/.streamlit /home/j13/.cache
ProtectSystem=strict
ProtectHome=read-only
PrivateTmp=yes

[Install]
WantedBy=default.target
```

## Hardening Notes

- `ProtectHome=read-only`: dashboard cannot write under /home — only into the explicit `ReadWritePaths` (Streamlit cache + tmp).
- `ProtectSystem=strict`: the entire OS tree is read-only to this service.
- `NoNewPrivileges=yes`: cannot gain extra capabilities at runtime.
- `PrivateTmp=yes`: isolates /tmp.

This binds the dashboard to its read-only intent at the systemd layer.

## Lifecycle Commands

| Action | Command |
|---|---|
| Enable persistent | `systemctl --user enable zangetsu-dashboard.service` |
| Start | `systemctl --user start zangetsu-dashboard.service` |
| Status | `systemctl --user status zangetsu-dashboard.service` |
| Stop | `systemctl --user stop zangetsu-dashboard.service` |
| Disable | `systemctl --user disable zangetsu-dashboard.service` |
