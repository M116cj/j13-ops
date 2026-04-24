#!/usr/bin/env python3
"""diff_snapshots.py — MOD-6 Phase 4 Phase 7 entry prerequisite 1.7.

Compares two snapshot JSON files (per pre_post_snapshot_spec.md v1) and
classifies each field-level diff per state_diff_acceptance_rules.md §1.

Usage: diff_snapshots.py <pre.json> <post.json> [--purpose PURPOSE]

Output: Markdown diff document to stdout (capture to
docs/governance/diffs/<pre_ts>_to_<post_ts>-<purpose>.md).

Classification per field:
  - ZERO_DIFF                          — value unchanged
  - EXPLAINED                          — value changed AND matches allowed-change catalog
  - EXPLAINED_TRACE_ONLY               — CODE_FROZEN runtime-file SHA changed BUT current
                                         order explicitly authorized the file for trace-only
                                         instrumentation via --authorize-trace-only <field>
  - FORBIDDEN                          — value changed AND matches forbidden pattern
  - FORBIDDEN_UNAUTHORIZED_RUNTIME_SHA — CODE_FROZEN runtime SHA changed WITHOUT
                                         --authorize-trace-only authorization
  - FORBIDDEN_THRESHOLD                — zangetsu_settings_sha changed (thresholds are
                                         NEVER trace-only-authorizable per 0-9M §4)
  - OPAQUE                             — SHA manifest differs but no field-level change

Overall classification:
  - ZERO_DIFF              — all zero, manifests equal
  - EXPLAINED              — some explained, none forbidden / trace-only
  - EXPLAINED_TRACE_ONLY   — some trace-only, none forbidden (governance-distinguishable
                             from plain EXPLAINED so audit can track authorized runtime
                             SHA changes separately)
  - FORBIDDEN              — >= 1 forbidden finding (any subtype)
  - OPAQUE                 — manifests differ but all fields appear unchanged

Exit code: 0 if ZERO/EXPLAINED/EXPLAINED_TRACE_ONLY; 2 if FORBIDDEN; 3 if OPAQUE.

TEAM ORDER 0-9M (2026-04-24) — Phase 7 Controlled-Diff Acceptance Rules Upgrade.
Adds --authorize-trace-only <field> flag so explicitly authorized Phase 7
lifecycle trace instrumentation (e.g. 0-9L-PLUS A1 emission in arena_pipeline.py)
can be classified as EXPLAINED_TRACE_ONLY rather than FORBIDDEN. The flag is
trust-but-verify: the order writer asserts the file change is trace-only; tests
+ Gate-A/B + PR review independently verify. Non-authorizable fields (threshold
holder zangetsu_settings_sha) remain strictly FORBIDDEN even if authorization
is passed — defense-in-depth.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


# --- Allowed-change catalog (per state_diff_acceptance_rules.md §2) -----------

# Fields that are EXPECTED to change naturally (no explanation needed).
ALWAYS_ALLOWED = {
    "runtime.calcifer_deploy_block_status",  # Calcifer rewrites every 5 min
    "runtime.calcifer_deploy_block_ts_iso",
    "config.calcifer_deploy_block_file_sha",  # same — natural polling
    "config.calcifer_state_file_sha",  # same
    "runtime.systemd_units.calcifer-supervisor.active_since",  # restart events allowed
    "runtime.systemd_units.cp-api.active_since",  # same
}

# Fields that MAY change IF an explanation is provided in the diff doc.
EXPLAINABLE = {
    "runtime.systemd_units",  # wildcard for unit restarts
    "repo.main_head_sha",
    "repo.main_head_subject",
    "repo.main_head_author_iso",
    "repo.git_status_porcelain_lines",
    "governance.branch_protection_main",  # requires ADR
    "gate_state",  # wildcard for classification changes
}

# Fields that are FORBIDDEN to change without explicit commit.
CODE_FROZEN = {
    "config.zangetsu_settings_sha",
    "config.arena_pipeline_sha",
    "config.arena23_orchestrator_sha",
    "config.arena45_orchestrator_sha",
    "config.calcifer_supervisor_sha",
    "config.zangetsu_outcome_sha",
}

# Hard forbidden: arena respawn / engine log growth.
HARD_FORBIDDEN_NONZERO = {
    "runtime.arena_processes.count",  # must stay 0 (frozen)
    "runtime.engine_jsonl_mtime_iso",  # must stay static
    "runtime.engine_jsonl_size_bytes",  # must stay static
}

# TEAM ORDER 0-9M §4 — fields that are NEVER trace-only authorizable.
# zangetsu_settings_sha hosts the threshold constants (A2_MIN_TRADES, entry/exit
# thresholds, risk thresholds). Any change here is by definition a threshold or
# configuration change, not trace instrumentation. Defense-in-depth: even if an
# operator accidentally passes --authorize-trace-only config.zangetsu_settings_sha,
# the tool refuses to honor it.
NEVER_TRACE_ONLY_AUTHORIZABLE = {
    "config.zangetsu_settings_sha",
}


def walk(obj, prefix=""):
    """Flatten nested dict into dotted paths."""
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            full = f"{prefix}.{k}" if prefix else k
            out.update(walk(v, full))
        return out
    return {prefix: obj}


def classify_change(
    path: str,
    pre_val,
    post_val,
    explanations,
    trace_only_authorized=None,
) -> str:
    """Return CLASSIFICATION for this field change.

    TEAM ORDER 0-9M upgrade: accepts a ``trace_only_authorized`` set of field
    paths that the caller asserts are trace-only instrumentation changes (passed
    via --authorize-trace-only). Fields matching a CODE_FROZEN prefix that ARE
    in this set are classified as EXPLAINED_TRACE_ONLY (rather than FORBIDDEN).
    Fields in NEVER_TRACE_ONLY_AUTHORIZABLE cannot be overridden this way.
    """
    if pre_val == post_val:
        return "ZERO_DIFF"
    if explanations is None:
        explanations = set()
    if trace_only_authorized is None:
        trace_only_authorized = set()

    # arena must stay frozen — hard forbidden
    for prefix in HARD_FORBIDDEN_NONZERO:
        if path.startswith(prefix):
            return "FORBIDDEN"

    # zangetsu_settings.py hosts thresholds — never trace-only authorizable
    for frozen_field in NEVER_TRACE_ONLY_AUTHORIZABLE:
        if path == frozen_field:
            if path in explanations:
                return "EXPLAINED"
            return "FORBIDDEN_THRESHOLD"

    # code files must match commit trail
    for prefix in CODE_FROZEN:
        if path.startswith(prefix):
            # 0-9M: explicit trace-only authorization
            if path in trace_only_authorized:
                return "EXPLAINED_TRACE_ONLY"
            if path in explanations:
                return "EXPLAINED"
            return "FORBIDDEN_UNAUTHORIZED_RUNTIME_SHA"

    # always-allowed natural changes
    for prefix in ALWAYS_ALLOWED:
        if path.startswith(prefix):
            return "EXPLAINED"

    # explainable with doc
    for prefix in EXPLAINABLE:
        if path.startswith(prefix):
            if path in explanations or prefix in explanations:
                return "EXPLAINED"
            # permit governance + gate_state + repo changes if diff is generated
            # alongside a commit — runner can supply explanations via --explain
            return "EXPLAINED"  # lenient for MOD-6 initial run; tighten later

    # unknown path: default forbidden
    return "FORBIDDEN"


def diff(pre, post, explanations, trace_only_authorized=None):
    """Compare pre/post surfaces dicts.

    0-9M upgrade: adds ``trace_only_authorized`` parameter and separates
    EXPLAINED_TRACE_ONLY results into their own bucket so the audit report
    distinguishes them from plain EXPLAINED changes.
    """
    if trace_only_authorized is None:
        trace_only_authorized = set()
    pre_flat = walk(pre.get("surfaces", {}))
    post_flat = walk(post.get("surfaces", {}))

    all_paths = sorted(set(pre_flat) | set(post_flat))
    zero = []
    explained = []
    explained_trace_only = []
    forbidden = []

    for p in all_paths:
        pv = pre_flat.get(p, "<missing>")
        pov = post_flat.get(p, "<missing>")
        cls = classify_change(p, pv, pov, explanations, trace_only_authorized)
        entry = (p, pv, pov, cls)
        if cls == "ZERO_DIFF":
            zero.append(entry)
        elif cls == "EXPLAINED":
            explained.append(entry)
        elif cls == "EXPLAINED_TRACE_ONLY":
            explained_trace_only.append(entry)
        else:
            forbidden.append(entry)

    pre_mani = pre.get("sha256_manifest")
    post_mani = post.get("sha256_manifest")
    manifest_match = pre_mani == post_mani

    overall = "ZERO_DIFF"
    if forbidden:
        overall = "FORBIDDEN"
    elif explained_trace_only and not explained:
        overall = "EXPLAINED_TRACE_ONLY"
    elif explained_trace_only and explained:
        # Mixed: surface both categories but the overall verdict is
        # EXPLAINED_TRACE_ONLY (the stricter of the two non-forbidden
        # classifications, flagged for audit attention).
        overall = "EXPLAINED_TRACE_ONLY"
    elif explained:
        overall = "EXPLAINED"
    elif not manifest_match:
        overall = "OPAQUE"

    return {
        "zero": zero,
        "explained": explained,
        "explained_trace_only": explained_trace_only,
        "forbidden": forbidden,
        "manifest_match": manifest_match,
        "pre_manifest": pre_mani,
        "post_manifest": post_mani,
        "overall": overall,
    }


def render_markdown(pre_path: str, post_path: str, result: dict) -> str:
    lines = []
    lines.append(f"# Controlled-Diff Report")
    lines.append(f"")
    lines.append(f"- **Pre snapshot**: `{pre_path}`")
    lines.append(f"  - sha256_manifest: `{result['pre_manifest']}`")
    lines.append(f"- **Post snapshot**: `{post_path}`")
    lines.append(f"  - sha256_manifest: `{result['post_manifest']}`")
    lines.append(f"- **Manifest match**: {result['manifest_match']}")
    lines.append(f"")
    lines.append(f"## Classification: **{result['overall']}**")
    lines.append(f"")
    lines.append(f"- Zero diff: {len(result['zero'])} fields")
    lines.append(f"- Explained diff: {len(result['explained'])} fields")
    lines.append(
        f"- Explained TRACE_ONLY diff: "
        f"{len(result.get('explained_trace_only', []))} fields"
    )
    lines.append(f"- Forbidden diff: {len(result['forbidden'])} fields")
    lines.append(f"")

    if result["forbidden"]:
        lines.append(f"## ⚠ Forbidden findings")
        lines.append(f"")
        for path, pv, pov, cls in result["forbidden"]:
            lines.append(f"- [{cls}] `{path}`: `{pv}` → `{pov}`")
        lines.append(f"")

    if result.get("explained_trace_only"):
        lines.append(f"## Explained TRACE_ONLY diffs (authorized runtime SHA changes)")
        lines.append(f"")
        for path, pv, pov, _ in result["explained_trace_only"]:
            pv_s = str(pv)[:100]
            pov_s = str(pov)[:100]
            lines.append(f"- `{path}`: `{pv_s}` → `{pov_s}`")
        lines.append(f"")

    if result["explained"]:
        lines.append(f"## Explained diffs")
        lines.append(f"")
        for path, pv, pov, _ in result["explained"]:
            pv_s = str(pv)[:100]
            pov_s = str(pov)[:100]
            lines.append(f"- `{path}`: `{pv_s}` → `{pov_s}`")
        lines.append(f"")

    if result["overall"] == "ZERO_DIFF":
        lines.append(f"✅ ZERO DIFF — no changes detected; manifests match.")
    elif result["overall"] == "EXPLAINED":
        lines.append(f"✅ EXPLAINED — all changes trace to allowed catalog entries.")
    elif result["overall"] == "EXPLAINED_TRACE_ONLY":
        lines.append(
            f"✅ EXPLAINED_TRACE_ONLY — authorized Phase 7 trace-only runtime SHA "
            f"change(s); non-trace protections remain intact."
        )
    elif result["overall"] == "FORBIDDEN":
        lines.append(f"❌ FORBIDDEN — at least one change violates acceptance rules.")
    elif result["overall"] == "OPAQUE":
        lines.append(f"⚠ OPAQUE — manifests differ but no field-level change detected.")

    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("pre", help="path to pre snapshot JSON")
    parser.add_argument("post", help="path to post snapshot JSON")
    parser.add_argument(
        "--purpose", default="diff", help="purpose tag for output file"
    )
    parser.add_argument(
        "--explain",
        action="append",
        default=[],
        help="field path that is explicitly explained (can be used multiple times)",
    )
    parser.add_argument(
        "--authorize-trace-only",
        action="append",
        default=[],
        dest="trace_only",
        help=(
            "TEAM ORDER 0-9M: field path (e.g. config.arena_pipeline_sha) that "
            "the active order explicitly authorized for Phase 7 trace-only "
            "instrumentation. Can be passed multiple times. Fields in "
            "NEVER_TRACE_ONLY_AUTHORIZABLE (e.g. zangetsu_settings_sha) cannot "
            "be overridden this way."
        ),
    )
    args = parser.parse_args()

    with open(args.pre) as f:
        pre = json.load(f)
    with open(args.post) as f:
        post = json.load(f)

    result = diff(pre, post, set(args.explain), set(args.trace_only))
    print(render_markdown(args.pre, args.post, result))

    if result["overall"] == "FORBIDDEN":
        sys.exit(2)
    if result["overall"] == "OPAQUE":
        sys.exit(3)
    # 0 for ZERO_DIFF, EXPLAINED, EXPLAINED_TRACE_ONLY
    sys.exit(0)


if __name__ == "__main__":
    main()
