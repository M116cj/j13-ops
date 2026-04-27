"""Tests for watchdog cold-boot recovery (post-reboot tmpfs wipe).

Order: TEAM ORDER 0-9X-POST-DB-COLD-BOOT-RECOVERY-FAST
Scope: zangetsu/watchdog.sh cold-boot pass only — no alpha / Arena /
threshold logic touched here.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import textwrap
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
WATCHDOG = REPO_ROOT / "zangetsu" / "watchdog.sh"

EXPECTED_REQUIRED_WORKERS = (
    "arena_pipeline_w0",
    "arena_pipeline_w1",
    "arena_pipeline_w2",
    "arena_pipeline_w3",
    "arena23_orchestrator",
    "arena45_orchestrator",
)

COLD_BOOT_LOG_RE = re.compile(
    r"^\[ZANGETSU_COLD_BOOT\] worker=(\S+) action=(started|skipped|blocked) "
    r"reason=(\S+) ts=\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$"
)


# ---------- Structural assertions on watchdog.sh ----------

def _watchdog_text() -> str:
    return WATCHDOG.read_text()


def test_watchdog_script_exists_and_is_executable():
    assert WATCHDOG.exists(), f"missing {WATCHDOG}"
    assert os.access(WATCHDOG, os.X_OK), "watchdog.sh must be executable"


def test_required_workers_array_contains_all_six_names():
    text = _watchdog_text()
    block = re.search(r"REQUIRED_WORKERS=\((.*?)\)", text, re.DOTALL)
    assert block is not None, "REQUIRED_WORKERS array not found"
    body = block.group(1)
    for name in EXPECTED_REQUIRED_WORKERS:
        assert name in body, f"REQUIRED_WORKERS missing {name}"


def test_cold_boot_pass_runs_after_lockfile_loop():
    """The cold-boot pass must be additive — existing stale-lock recovery
    in the lockfile-driven loop must run first and unchanged."""
    text = _watchdog_text()
    lockfile_loop = text.find("for lock in $LOCK_DIR/*.lock")
    cold_boot_loop = text.find('for name in "${REQUIRED_WORKERS[@]}"')
    assert lockfile_loop != -1, "lockfile-driven loop missing"
    assert cold_boot_loop != -1, "cold-boot pass missing"
    assert lockfile_loop < cold_boot_loop, (
        "cold-boot pass must come AFTER the lockfile-driven loop "
        "(it is additive, not a replacement)"
    )


def test_disable_marker_honored():
    text = _watchdog_text()
    assert "/tmp/zangetsu_disable_autostart" in text
    assert 'reason="disable_marker_present"' in text or \
           "reason=disable_marker_present" in text or \
           '"disable_marker_present"' in text, (
        "disable-marker branch must emit blocked-reason log"
    )


def test_log_line_format_compliant_with_order():
    """Order requires:
        [ZANGETSU_COLD_BOOT] worker=<name> action=<...> reason=<...> ts=<utc>
    """
    text = _watchdog_text()
    assert "[ZANGETSU_COLD_BOOT]" in text
    # Validate against the exact format using a synthesized line
    sample = "[ZANGETSU_COLD_BOOT] worker=arena_pipeline_w0 action=started " \
             "reason=cold_boot_post_reboot ts=2026-04-27T07:30:00"
    assert COLD_BOOT_LOG_RE.match(sample) is not None


def test_existing_reclaim_lock_logic_preserved():
    """reclaim_lock SIGTERM->wait->SIGKILL->verify must remain intact."""
    text = _watchdog_text()
    assert "reclaim_lock()" in text
    assert "kill -TERM" in text
    assert "kill -KILL" in text
    assert "kill -0" in text


def test_no_alpha_or_arena_threshold_changes():
    """Patch must not introduce any alpha-formula / Arena pass-fail /
    threshold edits in watchdog.sh."""
    text = _watchdog_text()
    forbidden_substrings = (
        "A2_MIN_TRADES",
        "fitness_fn",
        "alpha_zoo",
        "mutation",
        "crossover",
        "validation_threshold",
        "deployable_count =",
    )
    for tok in forbidden_substrings:
        assert tok not in text, f"forbidden token {tok!r} appears in watchdog.sh"


# ---------- Behavioural smoke test (sandbox) ----------

@pytest.fixture
def sandbox(tmp_path: Path):
    """Spin up an isolated sandbox so the test never touches /tmp/zangetsu/."""
    lock_dir = tmp_path / "locks"
    log_dir = tmp_path / "logs"
    base_dir = tmp_path / "base"
    venv_bin = base_dir / ".venv" / "bin"
    services_dir = base_dir / "services"
    for p in (lock_dir, log_dir, venv_bin, services_dir):
        p.mkdir(parents=True)

    # Stub python interpreter — never actually invoked because we override
    # restart_service in the wrapper.
    (venv_bin / "python3").write_text("#!/bin/bash\nsleep 1\n")
    (venv_bin / "python3").chmod(0o755)
    (services_dir / "arena_pipeline.py").write_text("# stub")
    (services_dir / "arena23_orchestrator.py").write_text("# stub")
    (services_dir / "arena45_orchestrator.py").write_text("# stub")

    return {"lock_dir": lock_dir, "log_dir": log_dir, "base": base_dir,
            "tmp": tmp_path}


def _run_wrapper(sandbox, *, disable_marker: bool = False,
                 prepopulate_locks: tuple[str, ...] = ()) -> str:
    """Run a wrapper that sources watchdog.sh's cold-boot logic with
    restart_service replaced by a logger stub. Returns stdout.

    Strategy: build a synthetic script that defines the same env hooks
    watchdog.sh uses, stubs restart_service+systemctl, then runs only
    the cold-boot pass. We extract the cold-boot pass by reading the
    file and isolating the section between sentinels.
    """
    text = WATCHDOG.read_text()
    start = text.find("# --- COLD-BOOT pass:")
    end = text.find("# 4. Also check systemd-only services")
    assert start != -1 and end != -1, "cold-boot section sentinels missing"
    cold_boot_section = text[start:end]

    for name in prepopulate_locks:
        (sandbox["lock_dir"] / f"{name}.lock").write_text("99999")

    if disable_marker:
        (sandbox["tmp"] / "zangetsu_disable_autostart").write_text("")

    wrapper = textwrap.dedent(f"""\
        #!/bin/bash
        set -u
        LOCK_DIR={sandbox['lock_dir']}
        BASE={sandbox['base']}
        VENV={sandbox['base']}/.venv/bin/python3
        LOG_DIR={sandbox['log_dir']}
        dead_count=0
        running_count=0
        timestamp() {{ date -u '+%Y-%m-%dT%H:%M:%S'; }}
        # Stub: never actually spawn processes during tests.
        restart_service() {{
          echo "STUB_RESTART name=$1"
        }}
        # Override DISABLE_MARKER to point inside the sandbox.
    """)

    cold_boot_section = cold_boot_section.replace(
        "DISABLE_MARKER=/tmp/zangetsu_disable_autostart",
        f"DISABLE_MARKER={sandbox['tmp']}/zangetsu_disable_autostart",
    )

    full = wrapper + cold_boot_section
    script = sandbox["tmp"] / "wrapper.sh"
    script.write_text(full)
    script.chmod(0o755)

    proc = subprocess.run(
        ["bash", str(script)],
        capture_output=True, text=True, timeout=20,
    )
    assert proc.returncode == 0, (
        f"wrapper failed rc={proc.returncode} stderr={proc.stderr!r} "
        f"stdout={proc.stdout!r}"
    )
    return proc.stdout


def test_cold_boot_starts_all_six_when_locks_absent(sandbox):
    out = _run_wrapper(sandbox)
    started = [
        m for m in (COLD_BOOT_LOG_RE.match(line) for line in out.splitlines())
        if m and m.group(2) == "started"
    ]
    started_names = {m.group(1) for m in started}
    assert started_names == set(EXPECTED_REQUIRED_WORKERS), (
        f"expected cold-boot for all 6, got: {sorted(started_names)}\n"
        f"full output:\n{out}"
    )
    # Ensure restart_service stub fired exactly once per worker.
    assert out.count("STUB_RESTART") == 6


def test_cold_boot_skips_workers_with_existing_lockfile(sandbox):
    out = _run_wrapper(sandbox, prepopulate_locks=("arena23_orchestrator",))
    skipped_owned = [
        m for m in (COLD_BOOT_LOG_RE.match(line) for line in out.splitlines())
        if m and m.group(2) == "skipped"
        and m.group(3) == "lockfile_present_main_loop_owns"
    ]
    assert any(m.group(1) == "arena23_orchestrator" for m in skipped_owned), (
        f"arena23_orchestrator should be skipped when lock present\n{out}"
    )
    # Other 5 still cold-boot.
    started = [
        m for m in (COLD_BOOT_LOG_RE.match(line) for line in out.splitlines())
        if m and m.group(2) == "started"
    ]
    assert len(started) == 5
    # No duplicate worker storm.
    assert out.count("STUB_RESTART name=arena23_orchestrator") == 0


def test_disable_marker_blocks_all_cold_boots(sandbox):
    out = _run_wrapper(sandbox, disable_marker=True)
    blocked = [
        m for m in (COLD_BOOT_LOG_RE.match(line) for line in out.splitlines())
        if m and m.group(2) == "blocked"
        and m.group(3) == "disable_marker_present"
    ]
    blocked_names = {m.group(1) for m in blocked}
    assert blocked_names == set(EXPECTED_REQUIRED_WORKERS), (
        f"disable marker should block all 6 cold-boots; got {blocked_names}\n{out}"
    )
    assert "STUB_RESTART" not in out, "no worker should be launched when disabled"


def test_full_watchdog_script_passes_bash_n():
    """Order Phase 3 mandates `bash -n zangetsu/watchdog.sh` returns 0."""
    proc = subprocess.run(
        ["bash", "-n", str(WATCHDOG)],
        capture_output=True, text=True,
    )
    assert proc.returncode == 0, (
        f"bash -n failed rc={proc.returncode} stderr={proc.stderr!r}"
    )


# ---------- Regression: A1 worker_process_alive must read /proc/PID/environ ----------

def test_worker_process_alive_uses_proc_environ_for_a1():
    """A1 workers are spawned by `env A1_WORKER_ID=$wid ... arena_pipeline.py`.
    The worker ID is an env var, NOT a cmdline arg — so a `pgrep -fa | grep`
    against cmdline is silently broken (always false-negative). The patched
    function must inspect /proc/<pid>/environ instead."""
    text = _watchdog_text()
    # Scope to worker_process_alive() body; the file also has an
    # arena_pipeline_w*) case in restart_service() which is unrelated.
    fn = re.search(
        r"^worker_process_alive\(\)\s*\{(?P<fn>.*?)^\}",
        text, re.DOTALL | re.MULTILINE,
    )
    assert fn is not None, "worker_process_alive() function body not found"
    block = re.search(
        r"arena_pipeline_w\*\)(?P<body>.*?);;",
        fn.group("fn"), re.DOTALL,
    )
    assert block is not None, "arena_pipeline_w* case in worker_process_alive missing"
    body = block.group("body")
    assert "/proc/" in body and "environ" in body, (
        "worker_process_alive arena_pipeline_w* branch must inspect "
        "/proc/<pid>/environ — env-var-bearing identifiers are not in cmdline."
    )
    # Belt-and-braces: forbid the broken pgrep|grep cmdline pattern from
    # silently re-appearing.
    assert not re.search(
        r"pgrep\s+-fa\s+arena_pipeline\.py.*\|\s*grep\s+-qE",
        body, re.DOTALL,
    ), "worker_process_alive must not match A1_WORKER_ID via cmdline grep"
