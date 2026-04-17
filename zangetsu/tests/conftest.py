"""Auto-load test env vars from ~/.zangetsu_test.env (j13 user-readable copy)."""
import os
from pathlib import Path

_env = Path.home() / ".zangetsu_test.env"
if _env.exists():
    for line in _env.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        os.environ.setdefault(k.strip(), v.strip())
