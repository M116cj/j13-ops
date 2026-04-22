#!/usr/bin/env python3
"""CD-05 Step A validator — parse all hand + zoo formulas under lean pset.

Usage: ZANGETSU_PSET_MODE=lean .venv/bin/python scripts/validate_lean_pset.py

Exits 0 if all parse, 1 otherwise.
"""
from __future__ import annotations

import os
import sys
import traceback

sys.path.insert(0, "/home/j13/j13-ops")
sys.path.insert(0, "/home/j13/j13-ops/zangetsu/scripts")


def _fake_fitness(*_a, **_kw):
    return (0.0,)


def main() -> int:
    mode = os.environ.get("ZANGETSU_PSET_MODE", "full")
    print(f"[VALIDATE] ZANGETSU_PSET_MODE={mode}")

    from deap import gp
    from zangetsu.engine.components.alpha_engine import AlphaEngine

    eng = AlphaEngine(fitness_fn=_fake_fitness)
    pset = eng.pset
    ind_terms = eng._indicator_terminal_names
    ops = eng._operator_names

    total_terms = 5 + len(ind_terms)  # OHLCV + indicators
    print(
        f"[VALIDATE] pset built: indicator_terminals={len(ind_terms)} "
        f"operators={len(ops)} total_terminals_with_ohlcv={total_terms}"
    )

    # Load formulas via AST parse (avoids executing scripts that need DB env)
    import ast

    def _extract_list_of_tuples(path: str, var_name: str):
        """Extract a module-level list of string/tuple literals by name."""
        src = open(path).read()
        tree = ast.parse(src)
        for node in tree.body:
            if isinstance(node, ast.Assign):
                for tgt in node.targets:
                    if isinstance(tgt, ast.Name) and tgt.id == var_name:
                        return ast.literal_eval(node.value)
        raise KeyError(f"{var_name} not found in {path}")

    zoo_raw = _extract_list_of_tuples(
        "/home/j13/j13-ops/zangetsu/scripts/alpha_zoo_injection.py", "ZOO",
    )
    zoo_formulas = [(f, tag, "zoo") for f, tag in zoo_raw]

    cs_raw = _extract_list_of_tuples(
        "/home/j13/j13-ops/zangetsu/scripts/cold_start_hand_alphas.py",
        "SEED_FORMULAS",
    )
    cs_formulas = [(f, f"cs_{i}", "cold_start") for i, f in enumerate(cs_raw)]

    import yaml
    with open("/home/j13/j13-ops/zangetsu/scripts/seed_hand_alphas.yaml") as fp:
        yaml_entries = yaml.safe_load(fp) or []
    yaml_formulas = [
        (e["formula"], e["name"], "yaml") for e in yaml_entries if "formula" in e
    ]

    all_forms = zoo_formulas + cs_formulas + yaml_formulas
    print(f"[VALIDATE] formulas loaded: zoo={len(zoo_formulas)} "
          f"cold_start={len(cs_formulas)} yaml={len(yaml_formulas)} "
          f"total={len(all_forms)}")

    # Parse each formula
    ok, fail = 0, 0
    failures = []
    for formula, name, source in all_forms:
        try:
            tree = gp.PrimitiveTree.from_string(formula, pset)
            _ = str(tree)
            ok += 1
        except Exception as e:
            fail += 1
            failures.append((name, source, formula, f"{type(e).__name__}: {e}"))

    # Report
    print(f"\n[RESULT] parsed_ok={ok} failed={fail} total={len(all_forms)}")
    if failures:
        print("\n[FAILURES]")
        for name, src, formula, err in failures:
            print(f"  [{src}] {name}: {err}")
            print(f"           formula: {formula[:110]}")

    if failures and mode == "lean":
        print("\n[DIAG] lean pset terminal set:")
        inds = sorted({t.rsplit("_", 1)[0] for t in ind_terms})
        periods = sorted({int(t.rsplit("_", 1)[1]) for t in ind_terms if t.rsplit("_", 1)[1].isdigit()})
        print(f"  indicators registered: {inds}")
        print(f"  periods registered:    {periods}")

    return 0 if fail == 0 else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        traceback.print_exc()
        sys.exit(2)
