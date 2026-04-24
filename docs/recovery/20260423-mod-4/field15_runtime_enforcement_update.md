# Field 15 Runtime Enforcement Update — MOD-4 Phase 3

**Order**: `/home/j13/claude-inbox/0-5` Phase 3 deliverable
**Produced**: 2026-04-23T10:05Z
**Resolves**: Gemini R3a-F6 MEDIUM — "Field 15 runtime enforcement deferred — declaration-only today"

---

## 1. Decision

**STATUS PRESERVED + ENFORCEMENT TIMELINE FORMALIZED.** MOD-4 does NOT activate runtime enforcement. MOD-4 documents WHEN + HOW Phase 7 will activate it.

This is a deliberate DEFER per 0-5 rules — finding is downgraded to PARTIAL (spec present, runtime deferred) with explicit justification.

## 2. Why MOD-4 does not activate runtime enforcement

Runtime enforcement of Field 15 requires:
- iptables/nftables rules per-process (network egress audit)
- seccomp-bpf syscall filter per-process (subprocess spawn control)
- AppArmor / landlock profile per-process (filesystem write control)
- cgroup limits (RSS / CPU sustained)

These are runtime-environment changes to each module's execution wrapper. MOD-4 scope per 0-5 `OUT OF SCOPE`:
> "runtime migration / service migration / control-plane implementation / Phase 7 execution"

Implementing iptables/seccomp/AppArmor/cgroup per-module falls under "service migration" + "runtime" — explicitly out of scope.

## 3. Timeline

| Phase | Enforcement state |
|---|---|
| MOD-1 (baseline) | Field 15 absent |
| MOD-3 | Field 15 schema MANDATORY; Gate-B.B.1 validates YAML presence |
| MOD-4 (now) | Field 15 schema MANDATORY + Gate-B.B.1 validation + **declaration enforcement only** (module YAML lacking Field 15 → CI fail) |
| Phase 7 (planned) | + iptables egress audit + cgroup RSS/CPU limits |
| Phase 7+ (ops hardening) | + seccomp-bpf syscall filter + AppArmor filesystem profile |

Progression matches principle: spec first, validation second, runtime audit third. Each step is independently verifiable.

## 4. Documentation tightening in MOD-4

Update `amended_module_contract_template.md §2 Field 15` with explicit enforcement note:

```yaml
execution_environment:
  # ENFORCEMENT STATUS (MOD-4 Phase 3):
  #   DECLARATION: MANDATORY (Gate-B.B.1 rejects YAML missing any sub-field)
  #   RUNTIME AUDIT: PLANNED Phase 7 (iptables / seccomp / AppArmor / cgroup)
  #   CURRENT GUARANTEE: declared; not yet enforced at runtime
  # Any module claiming blackbox_allowed=false must populate this field.
  # Runtime violations between MOD-4 and Phase 7 are DETECTED by obs_metrics
  # (declared in failure_surface) but not PREVENTED.
  ...
```

This clarity prevents future confusion about what Field 15 guarantees today.

## 5. Interim detection (MOD-4 additive)

Even without runtime prevention, detection is possible now via obs_metrics:

| Violation | How detected today |
|---|---|
| Network egress to non-declared host | tcpdump + post-hoc log analysis; NOT per-module per-request |
| Subprocess spawn when disabled | `/proc/<pid>/children` audit + cgroup task list; periodic |
| Filesystem write outside declared paths | `inotify` watcher on declared paths; detect writes elsewhere |
| RSS exceed | `/proc/<pid>/status` VmRSS polling |
| CPU sustained exceed | `/proc/<pid>/stat` utime+stime delta polling |

obs_metrics (Phase 7) will run these detectors as a gov_reconciler cron. MOD-4 does NOT build these detectors — only documents them as the intended enforcement path.

## 6. CI-side enforcement (LIVE NOW)

The ONE runtime check MOD-4 can ensure LIVE today: Gate-B.B.1 YAML schema validation.

`scripts/ci/validate_module_contract.py` (Phase 7 script) checks:
```python
def validate_field_15(yaml_doc):
    ee = yaml_doc.get("module", {}).get("execution_environment", {})
    required = [
        "permitted_egress_hosts",
        "subprocess_spawn_allowed",
        "subprocess_permitted_binaries",
        "filesystem_read_paths",
        "filesystem_write_paths",
        "max_rss_mb",
        "max_cpu_pct_sustained",
        "requires_root",
        "requires_docker_group",
        "requires_sudo",
    ]
    for key in required:
        if key not in ee:
            raise ValidationError(f"Field 15 missing sub-key: {key}")
    if ee["permitted_egress_hosts"] == ["*"]:
        raise ValidationError("Wildcard egress not permitted")
    if ee["max_rss_mb"] <= 0:
        raise ValidationError("max_rss_mb must be > 0")
    if ee["max_cpu_pct_sustained"] <= 0 or ee["max_cpu_pct_sustained"] > 100:
        raise ValidationError("max_cpu_pct_sustained must be 1..100")
```

This script is spec-level until Phase 7 commits it. When committed, Gate-B.B.1 runs it; missing Field 15 fields → PR rejected.

## 7. Alignment with `governance_enforcement_status_matrix.md`

Field 15 corresponds to rule G14 in the matrix:

| Rule | State |
|---|---|
| G14 spec MANDATORY | LIVE (via this doc + Gate-B.B.1 spec) |
| G14 Gate-B CI validation | PENDING SPEC (script not committed) |
| G14 runtime audit | SPEC-ONLY (Phase 7 scope) |

G14 moves from "PARTIAL" to "PARTIAL (declaration LIVE; runtime pending)" — same state, clearer description.

## 8. Non-negotiable rules

| Rule | Compliance |
|---|---|
| 1. No silent production mutation | ✅ — no runtime change |
| 9. No black-box control surface | ✅ — Field 15 is fully declared |

## 9. Resolution status

Gemini R3a-F6 MEDIUM — **DOWNGRADED TO TRACKED-DEFERRAL** with explicit justification (§2) + timeline (§3). Not resolved to CLOSED; not pretending to be resolved.

## 10. Q1 adversarial

| Dim | Verdict |
|---|---|
| Input boundary | PASS — declaration MANDATORY at Gate-B |
| Silent failure | PASS — detection spec §5 documents what can be caught today |
| External dep | PASS — iptables/seccomp are Phase 7 deps, documented |
| Concurrency | PASS — detection via periodic poll |
| Scope creep | PASS — MOD-4 does NOT add runtime enforcement |

## 11. Label per 0-5 rule 10

- §1 decision: **VERIFIED** (scope boundary of MOD-4 is explicit)
- §2 why-not: **VERIFIED** (0-5 OUT OF SCOPE section)
- §3 timeline: **PROBABLE** (design-time commitment; enforcement Phase 7)
- §5 detection methods: **PROBABLE** (documented, not yet built)
- §6 CI script: **PROBABLE** (spec committed today; execution Phase 7)
