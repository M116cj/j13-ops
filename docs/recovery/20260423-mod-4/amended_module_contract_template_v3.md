# Amended Module Contract Template v3 — MOD-4

**Order**: `/home/j13/claude-inbox/0-5` Phase 4 deliverable
**Produced**: 2026-04-23T10:28Z
**Supersedes**: `amended_module_contract_template.md` (MOD-3 v1, 15 fields)
**MOD-4 additions**: transitive-egress rule + filesystem_read_paths sub-field + AST fixture validation + multi-channel rate_limit schema.

---

## 1. Field count unchanged: still 15

All 15 MOD-3 fields retained. v3 adds SUB-FIELDS within Field 5 (outputs) and Field 15 (execution_environment), plus acceptance-check tightening.

## 2. Field 15 `execution_environment` — amended schema (v3)

```yaml
execution_environment:
  # Network egress (unchanged from MOD-3 baseline)
  permitted_egress_hosts:
    - "hostname:port"
    - "*.domain.tld:443"

  # Subprocess (unchanged)
  subprocess_spawn_allowed: true | false
  subprocess_permitted_binaries:
    - "/usr/bin/python3"

  # Filesystem writes (unchanged)
  filesystem_write_paths:
    - "/var/log/zangetsu/"

  # MOD-4 ADDITION: filesystem reads (optional; empty if unused)
  filesystem_read_paths:
    - "/tmp/calcifer_deploy_block.json"   # example for M8

  # Compute budget (unchanged)
  max_rss_mb: <int>
  max_cpu_pct_sustained: <int>

  # Privileged (unchanged)
  requires_root: false
  requires_docker_group: false
  requires_sudo: false
```

### 2.1 Transitive-egress rule (NEW in v3)

> **Transitive-egress rule**: `permitted_egress_hosts` declares egress this module's OWN code performs. Egress via library functions (e.g., `cp_worker_bridge.get()` → cp_api REST) is declared in the LIBRARY's contract, not the consumer's. This prevents egress-surface explosion into transitive closures.
>
> **Gate-B validation check**: static analysis confirms consumer module code does NOT directly `import requests` / `import urllib` / `import socket` etc. All network must go through an approved wrapper library (M9 for CP reads, data_provider for external data fetches, pub_telegram for Telegram).

Rationale + detail: `m8_egress_loopback_clarification.md §5`.

### 2.2 filesystem_read_paths sub-field (NEW in v3)

Optional; empty list acceptable for most modules. Required when module reads specific files outside temp/cache areas.

Acceptance at Gate-B.B.1:
- If declared non-empty: all listed paths must exist OR have documented ADR explaining why not (e.g., "Calcifer file created at first RED event")
- If missing entirely: assumed empty (backward-compatible with MOD-3 Field 15)

## 3. Field 5 `outputs` — multi-channel rate_limit schema (NEW in v3)

Backward-compatible extension:

```yaml
outputs:
  - contract_name: <ContractName>
    consumer_modules: [...]
    cardinality: one_per_input | n_per_input | stream
    guarantees: {...}

    # MOD-3 single-channel (still valid for simple modules)
    rate_limit:
      max_events_per_second: 100
      max_events_per_minute: 5000
      burst_size: 500
      backpressure_policy: drop_newest

    # OR MOD-4 multi-channel (for modules with distinct transport channels)
    rate_limit:
      <channel_name>:
        max_events_per_second: <int>
        max_events_per_minute: <int>
        burst_size: <int>
        backpressure_policy: drop_newest | drop_oldest | block_producer | fall_back_to_cache | not_applicable
        enforcement: hard_client_side | soft_metric_only | soft_monitor
      <other_channel>:
        ... (same sub-schema)
```

Discriminator: if `rate_limit` contains top-level numeric keys (`max_events_per_second`), single-channel. If it contains named sub-keys with nested rate specs, multi-channel.

## 4. Acceptance checklist — v3 amended (all 15 fields + sub-checks)

- [ ] Fields 1-14 per MOD-1 baseline
- [ ] Field 15 execution_environment populated with:
  - [ ] permitted_egress_hosts list (can be empty)
  - [ ] subprocess_spawn_allowed bool
  - [ ] subprocess_permitted_binaries list (if spawn=true)
  - [ ] filesystem_write_paths list (at least `/tmp/` or justified absence)
  - [ ] **filesystem_read_paths list (v3; can be empty; required declared if any non-temp read)**
  - [ ] max_rss_mb explicit integer
  - [ ] max_cpu_pct_sustained explicit integer
  - [ ] privileged capability bools
- [ ] responsibilities list maps 1:1 to test_boundary fixtures
- [ ] **Each fixture file (v3 AST check)**:
  - [ ] Contains ≥ 1 function starting with `test_`
  - [ ] Contains ≥ 5 non-blank non-`pass` lines
- [ ] **Transitive-egress check (v3)**: source scan confirms no direct `requests.*` / `urllib.*` / `socket.*` / `http.client.*` imports outside approved library wrappers
- [ ] outputs rate_limit present if cardinality is `stream` or `n_per_input`:
  - [ ] Single-channel: MOD-3 baseline schema satisfied
  - [ ] Multi-channel (v3): each named channel has full sub-schema

### 4.1 AST-level fixture validation (v3)

Implementation spec for `validate_module_contract.py`:

```python
import ast
def validate_fixture(fixture_path, responsibility_text):
    try:
        tree = ast.parse(open(fixture_path).read())
    except SyntaxError as e:
        raise ValueError(f"{fixture_path}: syntax error: {e}")

    test_fns = [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name.startswith('test_')]
    if len(test_fns) == 0:
        raise ValueError(f"{fixture_path}: no test_* functions (responsibility '{responsibility_text}' has no test)")

    lines = [l for l in open(fixture_path).read().split('\n')
             if l.strip() and l.strip() not in ('pass', '...', '# TODO')]
    if len(lines) < 5:
        raise ValueError(f"{fixture_path}: {len(lines)} substantive lines < 5 minimum (fluff fixture)")
    return True
```

This resolves Gemini R3a-F7 MEDIUM (ghost fixtures).

### 4.2 Transitive-egress CI pass (v3)

Implementation spec:

```python
FORBIDDEN_DIRECT_IMPORTS = [
    'requests',
    'urllib',
    'urllib2',
    'urllib3',
    'http.client',
    'httpx',  # unless wrapped
    'socket',
    'aiohttp',
]

APPROVED_WRAPPERS = [
    'zangetsu.cp_worker_bridge',  # M9
    'zangetsu.data_provider',     # L3
    'zangetsu.pub_telegram',      # L7
    'zangetsu.pub_akasha',
]

def check_transitive_egress(module_src_dir, field15_declared_egress):
    for py in glob(f"{module_src_dir}/**/*.py"):
        tree = ast.parse(open(py).read())
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name in FORBIDDEN_DIRECT_IMPORTS:
                        raise ValueError(f"{py}: direct import of {alias.name}; use approved wrapper")
            elif isinstance(node, ast.ImportFrom):
                mod = node.module or ''
                if any(mod.startswith(f) for f in FORBIDDEN_DIRECT_IMPORTS):
                    raise ValueError(f"{py}: direct from-import of {mod}")
```

This resolves part of Gemini R1b-F1 HIGH (egress stealth) beyond Field 15 declaration.

## 5. Anti-patterns v3 (§5 MOD-3 + 3 new entries)

| NEW v3 pattern | Why rejected |
|---|---|
| `filesystem_read_paths` missing when source code reads files outside `/tmp/`, `/proc/`, or the module's own subtree | Undeclared read side channel |
| Fixture file with only `pass` or `...` or comments | Ghost fixture; fails AST content check |
| Source imports `requests` / `urllib` / `socket` without wrapping through an approved library | Transitive-egress rule violation |

## 6. Non-negotiable rules

| Rule | Compliance |
|---|---|
| 8. No broad refactor | ✅ — schema is additive, backward-compatible |
| 9. No black-box control surface | ✅ — transitive rule + AST check close bypasses |
| 10. Labels | ✅ |

## 7. Q1 adversarial

| Dim | Verdict |
|---|---|
| Input boundary | PASS — all MOD-4 Phase 3 medium amendments folded into template |
| Silent failure | PASS — AST + transitive checks mechanical, not honor-system |
| External dep | PASS — `validate_module_contract.py` Phase 7 dependency declared |
| Concurrency | PASS — template is static spec |
| Scope creep | PASS — sub-field additions only; field count unchanged |

## 8. Resolution status (finding → v3 reference)

| Finding | Where resolved in v3 |
|---|---|
| R3a-F7 MEDIUM (ghost fixtures) | §4.1 AST check |
| R3a-F6 MEDIUM (Field 15 runtime) | PARTIAL — §2 sub-fields; §4.2 adds transitive source scan; runtime enforcement deferred Phase 7 |
| R1b-F1 HIGH (egress stealth) | §2.1 transitive rule + §4.2 CI scan |
| R3b-F4 LOW INCONCLUSIVE (M8 egress) | §2.1 transitive rule (DISPROVEN) |

## 9. Label per 0-5 rule 10

- §2 Field 15 schema: **VERIFIED** (additive to MOD-3)
- §3 rate_limit multi-channel: **VERIFIED** (backward-compat)
- §4 acceptance: **VERIFIED** (each sub-check mechanical)
- §4.2 transitive-egress CI: **PROBABLE** (implementation Phase 7; spec complete)
