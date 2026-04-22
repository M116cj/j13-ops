#!/usr/bin/env python3
"""Family-Aware Policy Integration Wrapper v0 — task 421-4.

Contract (per j13 2026-04-22 修正):
  A. DOES NOT accept ARM_* env as primary parameter source.
     Only control surface is: --family-id / --policy-mode / --dry-run / --proof-only.
  B. --dry-run resolves + prints + exits; does NOT enter shadow_control_suite.
  C. Smoke runs through the harness are expected to be 1 formula x 1 symbol only
     for this task's acceptance (policy correctness, not strategy performance).
  D. All resolved parameters come from registry + resolver. No mapping constant
     is embedded in this wrapper.

Three-layer runtime proof:
  1. startup banner  (§11.1)
  2. first-call proof on generate_alpha_signals (§11.2)
  3. JSONL proof fields attached via scs.evaluate_shadow hook (§11.3)

Fail-closed:
  Production mode + unvalidated family -> exit 3.
"""
from __future__ import annotations

import argparse
import os
import sys
from collections import Counter

import numpy as np

sys.path.insert(0, "/home/j13/j13-ops")
sys.path.insert(0, "/home/j13/j13-ops/zangetsu/scripts")

from zangetsu.engine.policy.family_strategy_policy_v0 import (  # noqa: E402
    DEFAULT_REGISTRY_PATH,
    PolicyBlockedError,
    PolicyRegistryError,
    format_banner,
    load_registry,
    load_with_overlay,
    resolve_family_strategy_policy,
    resolve_with_allow_list,
)


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Family-Aware Policy Integration Wrapper v0 (task 421-4).",
    )
    p.add_argument("--family-id", required=True,
                   help="Family identifier (volume / breakout / mean_reversion / ...).")
    p.add_argument("--policy-mode", choices=["research", "production"], default="research",
                   help="Policy mode. Default 'research' (fallback on unvalidated). "
                        "Use 'production' to fail-closed on unvalidated.")
    p.add_argument("--registry-path", default=str(DEFAULT_REGISTRY_PATH),
                   help="Main registry yaml path.")
    p.add_argument("--overlay-registry", default=None,
                   help="Task-local overlay registry yaml path. Overlay families "
                        "must not redefine main-registry families. Used for "
                        "candidate_test experiments (e.g. 421-5 MR generalization).")
    p.add_argument("--exception-overlay", default=None,
                   help="Exception overlay yaml with candidate_exception family "
                        "defining an (symbol, formula) allow_list. When provided, "
                        "cells matching the allow_list that would be rejected at "
                        "a1_val_low_wr have survived_a1 overridden to True with "
                        "full exception_* JSONL metadata. Cells outside allow_list "
                        "fall through to main-registry route unchanged.")
    p.add_argument("--dry-run", action="store_true",
                   help="Resolve policy, print banner, exit. No execution.")
    p.add_argument("--proof-only", action="store_true",
                   help="Force first-call proof printing on every shadow call (diagnostic).")
    # Pass-through to shadow_control_suite.main (not policy controls).
    p.add_argument("--input", help="DOE yaml path (forwarded to shadow_control_suite).")
    p.add_argument("--output", help="JSONL output path (forwarded).")
    p.add_argument("--symbols", help="Symbol list (forwarded).")
    p.add_argument("--strategy", default="j01", choices=["j01", "j02"])
    p.add_argument("--bar-size", type=int, default=15)
    p.add_argument("--run-id", help="Run id (forwarded).")
    return p.parse_args()


def _assert_no_direct_arm_env() -> None:
    """Hard rule A: wrapper must not read ARM_* envs as primary param source.
    We detect and warn (not hard-abort, since shell may have leftover vars) but
    the wrapper will NOT use them for routing — registry is the only source.
    """
    leaked = [k for k in ("ARM_RANK_WINDOW", "ARM_ENTRY_THR", "ARM_MIN_HOLD", "ARM_EXIT_THR")
              if k in os.environ]
    if leaked:
        sys.stderr.write(
            f"[policy-integration-v0] WARNING: ARM_* env leaked into shell ({leaked}) — "
            "ignored. Registry is the only source of truth for v0.\n"
        )


def main() -> int:
    args = _parse_args()
    _assert_no_direct_arm_env()

    # candidate_test overlay (per-family params) and exception overlay (per-cell)
    # are currently mutually exclusive for clarity. If both are supplied, bail.
    if args.overlay_registry and args.exception_overlay:
        sys.stderr.write(
            "[policy-integration-v0] ERROR: --overlay-registry and --exception-overlay "
            "cannot both be set in the same run. Pick one.\n"
        )
        return 2

    bundle = load_with_overlay(
        main_path=args.registry_path,
        overlay_path=args.overlay_registry,
    )
    policy = resolve_family_strategy_policy(
        args.family_id,
        mode=args.policy_mode,
        registry=bundle["main"],
        overlay_registry=bundle["overlay"],
        overlay_registry_path=bundle["overlay_path"],
    )

    # Load exception overlay separately (not merged with candidate_test overlays).
    exception_overlay = None
    exception_overlay_path = None
    if args.exception_overlay:
        exception_overlay_path = args.exception_overlay
        exception_overlay = load_registry(exception_overlay_path, overlay=True)
        # Reject direct-invocation of the overlay as a family_id (j13 hard rule B).
        for ov_fam_id, ov_fam in exception_overlay["families"].items():
            if ov_fam.get("route_status") == "candidate_exception" and args.family_id == ov_fam_id:
                raise PolicyRegistryError(
                    f"candidate_exception family {ov_fam_id!r} cannot be invoked "
                    f"directly via --family-id. Pass a main-registry family "
                    f"(e.g. 'volume') together with --exception-overlay."
                )
        # Sanity: family_id must exist in main registry (can't allow-list on top
        # of a non-existent base family).
        if args.family_id not in bundle["main"]["families"]:
            # Not fatal here — resolver will report; but we log.
            sys.stderr.write(
                f"[policy-integration-v0] NOTE: --family-id={args.family_id!r} is not a "
                f"main-registry family; exception overlay will still load but fallthrough "
                f"behavior depends on resolver.\n"
            )

    print(format_banner(policy), flush=True)

    if exception_overlay is not None:
        print("[policy-integration-v0] === EXCEPTION OVERLAY LOADED ===", flush=True)
        print(f"[policy-integration-v0] exception_overlay_path = {exception_overlay_path}", flush=True)
        total_allow = 0
        for ov_fam_id, ov_fam in exception_overlay["families"].items():
            if ov_fam.get("route_status") != "candidate_exception":
                continue
            al = ov_fam.get("allow_list", [])
            total_allow += len(al)
            print(f"[policy-integration-v0] overlay family = {ov_fam_id!r} "
                  f"(evidence_tag={ov_fam['evidence_tag']!r}, allow_list size={len(al)})", flush=True)
            for i, entry in enumerate(al):
                print(f"[policy-integration-v0]   allow[{i}] symbol={entry['symbol']!r} "
                      f"formula={entry['formula']!r} "
                      f"alpha_hash={entry.get('alpha_hash', '<none>')!r}", flush=True)
            expires_at = ov_fam.get("expires_at")
            if expires_at:
                print(f"[policy-integration-v0]   expires_at = {expires_at!r} (absolute; resolver will fail-close past this)", flush=True)
            if "expiry_after_event" in ov_fam:
                print(f"[policy-integration-v0]   expiry_after_event = {ov_fam['expiry_after_event']!r} (event-only; informational)", flush=True)
        print(f"[policy-integration-v0] total allow_list entries = {total_allow}", flush=True)

    if policy["route_status"] == "blocked":
        sys.stderr.write(
            f"[policy-integration-v0] FAIL-CLOSED: family_id={args.family_id!r} is unvalidated "
            f"and policy-mode=production. No execution will run.\n"
        )
        return 3

    if policy["route_status"] == "fallback":
        sys.stderr.write(
            f"[policy-integration-v0] WARNING: family_id={args.family_id!r} is unvalidated; "
            f"using safe fallback parameters (rank_window={policy['rank_window']}, "
            f"entry_threshold={policy['entry_threshold']}, min_hold={policy['min_hold']}, "
            f"exit_threshold={policy['exit_threshold']}).\n"
        )

    if policy["route_status"] == "candidate_test":
        sys.stderr.write(
            f"[policy-integration-v0] NOTICE: family_id={args.family_id!r} is an OVERLAY "
            f"candidate_test route (validated=false, source=overlay:{policy.get('overlay_path')!r}); "
            f"experimental parameters applied (rank_window={policy['rank_window']}, "
            f"entry_threshold={policy['entry_threshold']}, min_hold={policy['min_hold']}, "
            f"exit_threshold={policy['exit_threshold']}). NOT a production route.\n"
        )

    if args.dry_run:
        print("[policy-integration-v0] dry-run complete; exiting before harness.", flush=True)
        return 0

    # Full / smoke run requires the harness inputs.
    missing = [k for k in ("input", "output", "symbols", "run_id") if getattr(args, k) is None]
    if missing:
        sys.stderr.write(
            f"[policy-integration-v0] ERROR: missing required args for run mode: {missing}. "
            "Use --dry-run if you only want route resolution.\n"
        )
        return 2

    # Import AFTER dry-run short-circuit so pure resolution has minimal import cost.
    import cold_start_hand_alphas as css  # noqa: E402

    resolved_rank = policy["rank_window"]
    resolved_entry = policy["entry_threshold"]
    resolved_min_hold = policy["min_hold"]
    resolved_exit = policy["exit_threshold"]

    _first_call = {"done": False}
    _orig_generate = css.generate_alpha_signals

    def _patched_generate(alpha_values, *pargs, **kwargs):
        kwargs["rank_window"] = resolved_rank
        kwargs["entry_threshold"] = resolved_entry
        kwargs["min_hold"] = resolved_min_hold
        kwargs["exit_threshold"] = resolved_exit
        if not _first_call["done"] or args.proof_only:
            print(
                f"[policy-integration-v0] PROOF first generate_alpha_signals uses "
                f"rank_window={kwargs['rank_window']} "
                f"entry_threshold={kwargs['entry_threshold']} "
                f"min_hold={kwargs['min_hold']} "
                f"exit_threshold={kwargs['exit_threshold']} "
                f"(resolved via family={policy['resolved_family_id']!r} "
                f"status={policy['route_status']!r} reason={policy['route_reason']!r})",
                flush=True,
            )
            _first_call["done"] = True
        return _orig_generate(alpha_values, *pargs, **kwargs)

    css.generate_alpha_signals = _patched_generate

    from zangetsu.engine.components.alpha_signal import generate_alpha_signals as _direct_gen  # noqa: E402
    from zangetsu.engine.components.backtester import _vectorized_backtest  # noqa: E402

    _TEL: list = []
    _orig_eb = css.evaluate_and_backtest

    def _telemetry_eb(func, data_slice, indicator_cache_to_inject, engine,
                      backtester, symbol, max_hold_bars):
        bt, err = _orig_eb(func, data_slice, indicator_cache_to_inject, engine,
                           backtester, symbol, max_hold_bars)
        if bt is None:
            _TEL.append(None)
            return bt, err
        try:
            raw = func(
                data_slice["close"].astype(np.float64),
                data_slice["high"].astype(np.float64),
                data_slice["low"].astype(np.float64),
                data_slice["close"].astype(np.float64),
                data_slice["volume"].astype(np.float64),
            )
            alpha_values = np.nan_to_num(np.asarray(raw, dtype=np.float32),
                                         nan=0.0, posinf=0.0, neginf=0.0)
            n = data_slice["close"].size
            if alpha_values.size != n:
                if alpha_values.size == 1:
                    alpha_values = np.full(n, float(alpha_values.item()), dtype=np.float32)
                elif alpha_values.size < n:
                    padded = np.zeros(n, dtype=np.float32)
                    padded[-alpha_values.size:] = alpha_values
                    alpha_values = padded
                else:
                    alpha_values = alpha_values[-n:]

            signals, sizes, _ = _direct_gen(
                alpha_values,
                entry_threshold=resolved_entry,
                exit_threshold=resolved_exit,
                min_hold=resolved_min_hold,
                cooldown=css.COOLDOWN,
                rank_window=resolved_rank,
            )
            cost_bps = css._cost_model.get(symbol).total_round_trip_bps
            cl64 = data_slice["close"].astype(np.float64)
            hi64 = data_slice["high"].astype(np.float64)
            lo64 = data_slice["low"].astype(np.float64)
            pnl_arr, ent_arr, ext_arr, reason_arr = _vectorized_backtest(
                signals.astype(np.int8), cl64, hi64, lo64,
                cost_bps / 10000.0, max_hold_bars, 0.0,
                np.zeros_like(cl64), sizes.astype(np.float64),
            )
            holds = (ext_arr - ent_arr).tolist() if len(ext_arr) > 0 else []
            rcounts = Counter(reason_arr.tolist())
            def _pile(lo, hi):
                return sum(1 for h in holds if lo <= h <= hi)
            _TEL.append({
                "rank_window_used": int(resolved_rank),
                "entry_threshold_used": float(resolved_entry),
                "min_hold_used": int(resolved_min_hold),
                "exit_threshold_used": float(resolved_exit),
                "trade_count": len(holds),
                "avg_hold_bars": float(np.mean(holds)) if holds else None,
                "median_hold_bars": float(np.median(holds)) if holds else None,
                "p10": float(np.percentile(holds, 10)) if holds else None,
                "p25": float(np.percentile(holds, 25)) if holds else None,
                "p50": float(np.percentile(holds, 50)) if holds else None,
                "p75": float(np.percentile(holds, 75)) if holds else None,
                "p90": float(np.percentile(holds, 90)) if holds else None,
                "pile_15_20": _pile(15, 20),
                "pile_30_35": _pile(30, 35),
                "pile_60_65": _pile(60, 65),
                "pile_115_120": _pile(115, 120),
                "exit_signal": int(rcounts.get(0, 0)),
                "exit_atr": int(rcounts.get(1, 0)),
                "exit_max_hold": int(rcounts.get(2, 0)),
                "primary_invariance": {
                    "primary_trades": int(bt.total_trades),
                    "rerun_trades": int(len(holds)),
                    "match": int(bt.total_trades) == int(len(holds)),
                },
            })
        except Exception as _te:
            _TEL.append({"telemetry_error": f"{type(_te).__name__}:{_te}"})
        return bt, err

    css.evaluate_and_backtest = _telemetry_eb

    import hashlib  # noqa: E402
    import shadow_control_suite as scs  # noqa: E402
    _orig_es = scs.evaluate_shadow

    def _policy_es(formula, symbol, engine, backtester, max_hold_bars, bar_size=1):
        _TEL.clear()
        result = _orig_es(formula, symbol, engine, backtester, max_hold_bars, bar_size=bar_size)
        if len(_TEL) >= 1 and isinstance(result.get("train"), dict):
            result["train"]["telemetry"] = _TEL[0]
        if len(_TEL) >= 2 and isinstance(result.get("val"), dict):
            result["val"]["telemetry"] = _TEL[1]
        # §11.3 required proof fields (+ overlay audit surface)
        result["requested_family_id"] = policy["requested_family_id"]
        result["normalized_family_id"] = policy["normalized_family_id"]
        result["resolved_family_id"] = policy["resolved_family_id"]
        result["normalization_applied"] = policy["normalization_applied"]
        result["normalization_reason"] = policy["normalization_reason"]
        result["route_status"] = policy["route_status"]
        result["route_reason"] = policy["route_reason"]
        result["validated"] = policy["validated"]
        result["evidence_tag"] = policy["evidence_tag"]
        result["policy_version"] = policy["policy_version"]
        result["policy_mode"] = policy["mode"]
        result["registry_source"] = policy.get("registry_source", "main")
        result["overlay_path"] = policy.get("overlay_path")

        # ================================================================
        # Exception overlay handling (j13 2026-04-22 β path)
        # ================================================================
        # For each cell, consult the exception overlay (if loaded) to decide
        # whether (symbol, formula) is an approved exception. Always attach
        # exception_* metadata fields to the JSONL row so the full verify
        # table (j13 hard rule C) can be produced from JSONL alone.
        if exception_overlay is not None:
            alpha_hash_local = hashlib.md5(formula.encode("utf-8")).hexdigest()[:16]
            resolved = resolve_with_allow_list(
                family_id=args.family_id,
                mode=args.policy_mode,
                symbol=symbol,
                formula=formula,
                alpha_hash=alpha_hash_local,
                registry=bundle["main"],
                overlay_registry=exception_overlay,
                overlay_registry_path=exception_overlay_path,
            )
            hit = bool(resolved.get("exception_allow_list_hit"))
            # Always attach full exception metadata (hit and miss cases).
            result["exception_allow_list_hit"] = hit
            result["exception_overlay_name"] = resolved.get("exception_overlay_name")
            result["exception_pair_key"] = resolved.get("exception_pair_key")
            result["exception_evidence_tag"] = resolved.get("exception_evidence_tag")
            result["exception_matched_entry_index"] = resolved.get("exception_matched_entry_index")
            result["exception_expiry_meta"] = resolved.get("exception_expiry_meta")
            result["exception_overlay_path"] = exception_overlay_path
            result["fallthrough_to_main"] = not hit
            result["exception_overlay_warnings"] = resolved.get("overlay_warnings", [])

            # Override gate if:
            #   (a) cell was rejected by a1_val_low_wr,
            #   (b) cell is in the allow_list,
            #   (c) overlay hasn't expired (handled in resolve_with_allow_list)
            if hit and result.get("first_gate_reached") == "a1_val_low_wr":
                original_first_gate = result["first_gate_reached"]
                original_reason = result.get("reject_reason")
                result["survived_a1"] = True
                result["first_gate_reached"] = "A1_PASSED"  # scs convention
                result["exception_override_applied"] = True
                result["exception_override_reason"] = (
                    f"{original_first_gate} override=candidate_exception "
                    f"(original_reject={original_reason!r})"
                )
                result["exception_route_status"] = "candidate_exception"
                result["exception_route_reason"] = resolved["route_reason"]
                print(f"[policy-integration-v0] EXCEPTION APPLIED: symbol={symbol!r} "
                      f"formula={formula!r} original_first_gate={original_first_gate} "
                      f"-> survived_a1=True (overlay={resolved.get('exception_overlay_name')!r})",
                      flush=True)
            else:
                result["exception_override_applied"] = False
                result["exception_override_reason"] = None
                result["exception_route_status"] = None
                result["exception_route_reason"] = None

            # Warnings surfaced
            for w in resolved.get("overlay_warnings", []):
                sys.stderr.write(f"[policy-integration-v0] OVERLAY WARN: {w}\n")
        else:
            # No exception overlay loaded — still expose the fields so downstream
            # aggregators can rely on a stable JSONL schema.
            result["exception_allow_list_hit"] = False
            result["exception_overlay_name"] = None
            result["exception_pair_key"] = None
            result["exception_evidence_tag"] = None
            result["exception_matched_entry_index"] = -1
            result["exception_expiry_meta"] = None
            result["exception_overlay_path"] = None
            result["fallthrough_to_main"] = True
            result["exception_overlay_warnings"] = []
            result["exception_override_applied"] = False
            result["exception_override_reason"] = None
            result["exception_route_status"] = None
            result["exception_route_reason"] = None

        return result

    scs.evaluate_shadow = _policy_es

    # Rebuild sys.argv for shadow_control_suite's argparse.
    forwarded = [
        "shadow_control_suite",
        "--input", args.input,
        "--output", args.output,
        "--symbols", args.symbols,
        "--strategy", args.strategy,
        "--bar-size", str(args.bar_size),
        "--run-id", args.run_id,
    ]
    old_argv = sys.argv
    sys.argv = forwarded
    try:
        scs.main()
    finally:
        sys.argv = old_argv
    return 0


if __name__ == "__main__":
    sys.exit(main())
