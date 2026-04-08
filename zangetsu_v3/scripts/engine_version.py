"""[F8] Indicator engine binary versioning.

Every stage 2 search MUST be locked to a specific engine build.
That build MUST be preserved for the entire lifetime of any champion derived from it.

Usage:
    from engine_version import (
        compute_engine_hash,
        archive_engine,
        verify_engine_hash,
        load_archived_engine,
        ENGINE_SO_PATH,
    )
"""
from __future__ import annotations

import hashlib
import json
import os
import platform
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

# Default .so location (editable install)
VENV_SO = Path(os.path.expanduser(
    "~/j13-ops/zangetsu_v3/.venv/lib/python3.12/site-packages/"
    "zangetsu_indicators/zangetsu_indicators.cpython-312-x86_64-linux-gnu.so"
))
ENGINE_SO_PATH = VENV_SO
ARCHIVE_ROOT = Path(os.path.expanduser("~/j13-ops/zangetsu_v3/engine_archive"))


def compute_engine_hash(so_path: Path | None = None) -> str:
    """Return sha256 hex digest of the engine .so file."""
    p = so_path or ENGINE_SO_PATH
    if not p.exists():
        raise FileNotFoundError(f"Engine .so not found: {p}")
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return f"sha256:{h.hexdigest()}"


def _build_metadata(so_path: Path) -> dict:
    """Collect build metadata for archival."""
    stat = so_path.stat()
    rust_ver = "unknown"
    try:
        rust_ver = subprocess.check_output(
            ["rustc", "--version"], text=True, stderr=subprocess.DEVNULL
        ).strip()
    except Exception:
        pass
    return {
        "archived_at": datetime.now(timezone.utc).isoformat(),
        "so_size_bytes": stat.st_size,
        "so_mtime": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
        "rust_version": rust_ver,
        "platform": platform.platform(),
        "python_version": platform.python_version(),
    }


def archive_engine(so_path: Path | None = None) -> tuple[str, Path]:
    """Archive the current .so to engine_archive/{hash[:12]}/.

    Returns (engine_hash, archive_dir).
    Idempotent: if already archived, returns existing path.
    """
    p = so_path or ENGINE_SO_PATH
    engine_hash = compute_engine_hash(p)
    short = engine_hash.split(":")[1][:12]
    archive_dir = ARCHIVE_ROOT / short
    archive_so = archive_dir / "zangetsu_indicators.so"

    if archive_so.exists():
        # Verify integrity
        existing_hash = compute_engine_hash(archive_so)
        if existing_hash == engine_hash:
            return engine_hash, archive_dir
        raise RuntimeError(
            f"Archive collision: {archive_dir} exists but hash differs "
            f"({existing_hash} != {engine_hash})"
        )

    archive_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(p, archive_so)

    meta = _build_metadata(p)
    meta["engine_hash"] = engine_hash
    with open(archive_dir / "build_metadata.json", "w") as f:
        json.dump(meta, f, indent=2)

    return engine_hash, archive_dir


def verify_engine_hash(expected_hash: str, so_path: Path | None = None) -> bool:
    """Check if current engine matches expected hash."""
    current = compute_engine_hash(so_path)
    return current == expected_hash


def load_archived_engine(engine_hash: str) -> Path:
    """Return path to archived .so for a given hash.

    Caller is responsible for loading it (e.g. via importlib or
    setting PYTHONPATH before import).
    Raises FileNotFoundError if archive doesn't exist.
    """
    short = engine_hash.split(":")[1][:12]
    archive_so = ARCHIVE_ROOT / short / "zangetsu_indicators.so"
    if not archive_so.exists():
        raise FileNotFoundError(
            f"No archived engine for {engine_hash}. "
            f"Looked at: {archive_so}"
        )
    # Verify integrity
    actual = compute_engine_hash(archive_so)
    if actual != engine_hash:
        raise RuntimeError(
            f"Archive corrupted: expected {engine_hash}, got {actual}"
        )
    return archive_so


def preflight_check(champion_engine_hash: str) -> tuple[bool, str]:
    """Pre-flight check: does current engine match champion's engine?

    Returns (ok, message).
    If not ok, provides actionable guidance.
    """
    try:
        current = compute_engine_hash()
    except FileNotFoundError as e:
        return False, f"Engine .so not found: {e}"

    if current == champion_engine_hash:
        return True, f"Engine hash matches: {current}"

    # Check if archived version exists
    try:
        archive_path = load_archived_engine(champion_engine_hash)
        return False, (
            f"Engine mismatch. Current: {current}, "
            f"Champion needs: {champion_engine_hash}. "
            f"Archived .so available at: {archive_path}. "
            f"Load from archive before proceeding."
        )
    except FileNotFoundError:
        return False, (
            f"Engine mismatch. Current: {current}, "
            f"Champion needs: {champion_engine_hash}. "
            f"NO ARCHIVE FOUND. Champion is unreproducible."
        )
