# secret.example/

Committed placeholder for the real `../secret/` directory. This file tree documents
*what secrets the project needs* — never real values.

## First-time setup on a new host

```bash
cp -r secret.example secret
chmod 700 secret
chmod 600 secret/*
# edit secret/.env — fill every <PLACEHOLDER> with the real value
```

## Rules (enforced at repo-, commit-, and CI-level)

- `secret/` is gitignored (see project `.gitignore`).
- Code MUST read secrets via `os.environ['KEY']` with no fallback default.
  A missing env var should raise, not silently return an empty string.
- Any new secret key added anywhere → add a `KEY=<PLACEHOLDER>` line here
  in the same PR. CI will reject diffs that widen the runtime env surface
  without updating this file.
- Systemd units load `secret/.env` via `EnvironmentFile=`.

## Current key inventory

See [`.env.example`](./.env.example).
