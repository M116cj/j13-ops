"""Provenance bundle for every alpha written to champion_pipeline_staging.

Exposes the 11 NOT NULL columns the DB layer enforces (governance rule #3):
    engine_version, git_commit, config_hash, grammar_hash, fitness_version,
    patches_applied, run_id, worker_id, seed, epoch, created_ts.

Strict rules:
- `get_git_commit()` refuses to return if the working tree is dirty. The
  worker fails to start, which is the safer failure mode — we never
  stamp a row with misleading lineage.
- `compute_grammar_hash()` produces the same hash for the same primitive
  set (operator names + indicator terminal names, sorted). Determinism
  is validated in tests.
- `compute_config_hash()` hashes the Settings dataclass's current state;
  ANY configuration change moves the hash.
"""
from __future__ import annotations

import hashlib
import os
import subprocess
import uuid
from dataclasses import dataclass
from typing import Iterable

from zangetsu.engine.patches import PATCHES_APPLIED


ENGINE_VERSION = "zangetsu_v0.7.1"


class DirtyTreeError(RuntimeError):
    """Raised when git working tree is dirty at worker startup."""


@dataclass(frozen=True)
class ProvenanceBundle:
    engine_version: str
    git_commit: str
    git_ref_type: str            # 'branch:<name>' or 'detached'
    config_hash: str
    grammar_hash: str
    fitness_version: str
    patches_applied: list[str]
    run_id: str
    worker_id: int
    seed: int
    epoch: str                   # always 'B_full_space' for live workers

    def as_dict(self) -> dict:
        return {
            "engine_version": self.engine_version,
            "git_commit": self.git_commit,
            "git_ref_type": self.git_ref_type,
            "config_hash": self.config_hash,
            "grammar_hash": self.grammar_hash,
            "fitness_version": self.fitness_version,
            "patches_applied": list(self.patches_applied),
            "run_id": self.run_id,
            "worker_id": self.worker_id,
            "seed": self.seed,
            "epoch": self.epoch,
        }


def get_git_commit(repo_path: str = "/home/j13/j13-ops") -> tuple[str, str]:
    """Return (commit_sha, ref_type) — raises if tree is dirty.

    ref_type is 'detached' or 'branch:<name>'.
    """
    def _run(args: list[str]) -> str:
        return subprocess.check_output(
            args, cwd=repo_path, text=True
        ).strip()

    # Dirty check — reject any uncommitted changes
    status = _run(["git", "status", "--porcelain"])
    if status:
        raise DirtyTreeError(
            f"git working tree at {repo_path} has uncommitted changes:\n"
            + status[:500]
            + "\nWorker refuses to start to preserve provenance integrity."
        )

    commit = _run(["git", "rev-parse", "HEAD"])

    try:
        branch = _run(["git", "symbolic-ref", "--short", "HEAD"])
        ref_type = f"branch:{branch}"
    except subprocess.CalledProcessError:
        ref_type = "detached"

    return commit, ref_type


def compute_grammar_hash(operator_names: Iterable[str],
                         indicator_terminal_names: Iterable[str]) -> str:
    """Hash of the sorted union of operator + indicator terminal names.

    Deterministic: same input -> same output. Any rename, addition,
    or removal of primitives changes the hash.
    """
    body = (
        "OPS:" + ",".join(sorted(operator_names))
        + "|IND:" + ",".join(sorted(indicator_terminal_names))
    )
    return hashlib.sha256(body.encode("utf-8")).hexdigest()[:16]


def compute_config_hash(settings_obj) -> str:
    """Hash of the settings object's current state."""
    from dataclasses import asdict
    try:
        body = "|".join(f"{k}={v}" for k, v in sorted(asdict(settings_obj).items()))
    except TypeError:
        # Not a dataclass — fall back to __dict__
        body = "|".join(
            f"{k}={v}" for k, v in sorted(vars(settings_obj).items())
            if not k.startswith("_")
        )
    return hashlib.sha256(body.encode("utf-8")).hexdigest()[:16]


def compute_fitness_version(strategy_id: str) -> str:
    """Read the strategy's fitness.py file and hash it.

    Returns a string like `j01.fitness@sha256:abc0123...`. This uniquely
    identifies the exact fitness code that produced a given alpha.
    """
    path = f"/home/j13/j13-ops/{strategy_id}/fitness.py"
    with open(path, "rb") as f:
        digest = hashlib.sha256(f.read()).hexdigest()[:16]
    return f"{strategy_id}.fitness@sha256:{digest}"


def generate_run_id() -> str:
    """One per worker startup. Groups all alphas from a single session."""
    return str(uuid.uuid4())


def build_bundle(*,
                 strategy_id: str,
                 worker_id: int,
                 seed: int,
                 operator_names: Iterable[str],
                 indicator_terminal_names: Iterable[str],
                 settings_obj) -> ProvenanceBundle:
    """Build the complete bundle. Raises DirtyTreeError if git is dirty."""
    commit, ref_type = get_git_commit()
    return ProvenanceBundle(
        engine_version=ENGINE_VERSION,
        git_commit=commit,
        git_ref_type=ref_type,
        config_hash=compute_config_hash(settings_obj),
        grammar_hash=compute_grammar_hash(operator_names, indicator_terminal_names),
        fitness_version=compute_fitness_version(strategy_id),
        patches_applied=list(PATCHES_APPLIED),
        run_id=generate_run_id(),
        worker_id=worker_id,
        seed=seed,
        epoch="B_full_space",
    )


if __name__ == "__main__":  # pragma: no cover
    # Smoke test — exercises every function
    from dataclasses import dataclass as _dc

    @_dc(frozen=True)
    class _S:
        a: int = 1
        b: str = "x"

    ops = ["add", "mul", "neg"]
    inds = ["rsi_14", "ema_20"]
    h1 = compute_grammar_hash(ops, inds)
    h2 = compute_grammar_hash(ops, inds)
    assert h1 == h2, "grammar hash not deterministic"
    h3 = compute_grammar_hash(ops + ["sub"], inds)
    assert h3 != h1, "grammar hash did not change"
    print("grammar_hash deterministic:", h1)

    c1 = compute_config_hash(_S())
    c2 = compute_config_hash(_S())
    assert c1 == c2
    print("config_hash deterministic:", c1)

    print("patches:", len(PATCHES_APPLIED))
    print("run_id sample:", generate_run_id())
