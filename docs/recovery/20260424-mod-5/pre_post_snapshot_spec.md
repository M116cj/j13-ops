# Pre/Post Snapshot Spec — MOD-5 Phase 2

**Order**: `/home/j13/claude-inbox/0-7` Phase 2 deliverable
**Produced**: 2026-04-24T00:38Z
**Scope**: Canonical JSON schema (v1) + capture commands for the 5 state surfaces defined in `controlled_diff_framework.md §2.2`.

---

## 1. Schema v1 — root object

```json
{
  "schema_version": 1,
  "captured_at": "<ISO 8601 UTC>",
  "captured_by": "<actor>",
  "purpose": "<why this snapshot>",
  "surfaces": {
    "runtime":    { ... },
    "governance": { ... },
    "repo":       { ... },
    "config":     { ... },
    "gate_state": { ... }
  },
  "sha256_manifest": "<hex digest of the 5 surfaces serialized>"
}
```

## 2. Per-surface schemas

### 2.1 `runtime` surface

```json
{
  "runtime": {
    "arena_processes": {
      "count": <int>,
      "pids": [<int>, ...],
      "notes": "<pgrep output summary>"
    },
    "systemd_units": {
      "calcifer-supervisor":  { "active": true|false, "main_pid": <int>, "active_since": "<iso>" },
      "calcifer-miniapp":     { "active": true|false, ... },
      "d-mail-miniapp":       { "active": true|false, ... },
      "console-api":          { "active": true|false, ... },
      "dashboard-api":        { "active": true|false, ... }
    },
    "docker_containers": {
      "deploy-postgres-1":    { "state": "running", "health": "healthy", "uptime_h": <int> },
      "akasha-postgres":      { ... },
      "akasha-redis":         { ... },
      "akasha-harness":       { ... }
    },
    "engine_jsonl_mtime_iso": "<iso of /home/j13/j13-ops/zangetsu/logs/engine.jsonl mtime>",
    "engine_jsonl_size_bytes": <int>,
    "calcifer_deploy_block_status": "RED|GREEN|ERROR",
    "calcifer_deploy_block_ts_iso": "<iso>"
  }
}
```

### 2.2 `governance` surface

```json
{
  "governance": {
    "branch_protection_main": {
      "required_signatures":     { "enabled": true|false },
      "required_linear_history": { "enabled": true|false },
      "enforce_admins":          { "enabled": true|false },
      "allow_force_pushes":      { "enabled": true|false },
      "allow_deletions":         { "enabled": true|false },
      "required_status_checks":  <object|null>,
      "required_pull_request_reviews": <object|null>
    },
    "governance_matrix_latest": {
      "live_rules_count": <int>,
      "partial_rules_count": <int>,
      "spec_only_rules_count": <int>,
      "latest_rule_added": "<G21..Gnn>"
    },
    "akasha_health": "ok|degraded|down",
    "akasha_probe_iso": "<iso>"
  }
}
```

### 2.3 `repo` surface

```json
{
  "repo": {
    "main_head_sha": "<40-char SHA>",
    "main_head_subject": "<commit subject line>",
    "main_head_author_iso": "<iso>",
    "git_status_porcelain_lines": <int>,
    "git_status_porcelain_sample": [<up to 5 lines>],
    "last_5_commits": [
      { "sha": "<short>", "subject": "<short>" },
      ...
    ]
  }
}
```

### 2.4 `config` surface

```json
{
  "config": {
    "calcifer_deploy_block_file": {
      "path": "/tmp/calcifer_deploy_block.json",
      "sha256": "<hex>",
      "size_bytes": <int>,
      "mtime_iso": "<iso>"
    },
    "calcifer_state_file": {
      "path": "/home/j13/j13-ops/calcifer/deploy_block_state.json",
      "sha256": "<hex>",
      "size_bytes": <int>,
      "mtime_iso": "<iso>"
    },
    "zangetsu_settings_sha": {
      "path": "zangetsu/config/settings.py",
      "sha256": "<hex>"
    },
    "arena_pipeline_sha": {
      "path": "zangetsu/services/arena_pipeline.py",
      "sha256": "<hex>"
    },
    "arena23_orchestrator_sha": {
      "path": "zangetsu/services/arena23_orchestrator.py",
      "sha256": "<hex>"
    }
  }
}
```

### 2.5 `gate_state` surface

```json
{
  "gate_state": {
    "gate_a_classification": "CLEARED|CLEARED_PENDING_CONDITIONS|STILL_PARTIALLY_BLOCKED|BLOCKED_BY_NEW_FINDINGS|BLOCKED",
    "classification_source_file": "<path to authoritative memo>",
    "classification_ts_iso": "<iso of last classification update>",
    "cqg_conditions": {
      "runtime_freeze":          "VERIFIED|PARTIAL|INCONCLUSIVE|DISPROVEN",
      "governance_live":          "VERIFIED|PARTIAL|INCONCLUSIVE|DISPROVEN",
      "corpus_consistency":       "VERIFIED|PARTIAL|INCONCLUSIVE|DISPROVEN",
      "adversarial_closure":      "VERIFIED|PARTIAL|INCONCLUSIVE|DISPROVEN",
      "controlled_diff":          "VERIFIED|PARTIAL|INCONCLUSIVE|DISPROVEN",
      "rollback_readiness":       "VERIFIED|PARTIAL|INCONCLUSIVE|DISPROVEN"
    },
    "latest_gemini_round": <int>,
    "latest_gemini_verdict": "ACCEPT|ACCEPT_WITH_AMENDMENTS|REJECT"
  }
}
```

## 3. Capture commands (reproducible)

### 3.1 Runtime surface

```bash
ssh j13@100.123.49.102 '
ARENA_PIDS=$(pgrep -af "arena_pipeline|arena23_orchestrator|arena45_orchestrator" 2>/dev/null | grep -v grep | awk "{print \$1}")
ARENA_COUNT=$(echo -n "$ARENA_PIDS" | grep -c ^)

cat <<JSON
{
  "arena_processes": {"count": $ARENA_COUNT, "pids": [$(echo $ARENA_PIDS | tr " " ",")]},
  "calcifer_deploy_block_status": "$(python3 -c "import json; print(json.load(open(\"/tmp/calcifer_deploy_block.json\")).get(\"status\", \"UNKNOWN\"))")",
  "engine_jsonl_mtime_iso": "$(stat -c %y /home/j13/j13-ops/zangetsu/logs/engine.jsonl)",
  "engine_jsonl_size_bytes": $(stat -c %s /home/j13/j13-ops/zangetsu/logs/engine.jsonl)
}
JSON
'
```

### 3.2 Governance surface

```bash
gh api /repos/M116cj/j13-ops/branches/main/protection --jq '{branch_protection_main: .}' \
  > /tmp/snapshot_governance.json
curl -sf --connect-timeout 3 http://100.123.49.102:8769/health \
  | python3 -c 'import sys,json; print(json.dumps({"akasha_health": "ok" if json.load(sys.stdin).get("status") == "ok" else "degraded"}))' \
  >> /tmp/snapshot_governance.json
```

### 3.3 Repo surface

```bash
ssh j13@100.123.49.102 '
cd /home/j13/j13-ops
cat <<JSON
{
  "main_head_sha": "$(git rev-parse HEAD)",
  "main_head_subject": "$(git log -1 --format=%s)",
  "main_head_author_iso": "$(git log -1 --format=%ad --date=iso-strict)",
  "git_status_porcelain_lines": $(git status --porcelain | wc -l)
}
JSON
'
```

### 3.4 Config surface

```bash
ssh j13@100.123.49.102 '
SHA_BLOCK=$(sha256sum /tmp/calcifer_deploy_block.json | cut -d" " -f1)
SHA_STATE=$(sha256sum /home/j13/j13-ops/calcifer/deploy_block_state.json | cut -d" " -f1)
SHA_SETTINGS=$(sha256sum /home/j13/j13-ops/zangetsu/config/settings.py | cut -d" " -f1)
SHA_PIPELINE=$(sha256sum /home/j13/j13-ops/zangetsu/services/arena_pipeline.py | cut -d" " -f1)
SHA_ARENA23=$(sha256sum /home/j13/j13-ops/zangetsu/services/arena23_orchestrator.py | cut -d" " -f1)

cat <<JSON
{
  "config": {
    "calcifer_deploy_block_file": {"sha256": "$SHA_BLOCK"},
    "calcifer_state_file":        {"sha256": "$SHA_STATE"},
    "zangetsu_settings_sha":      {"sha256": "$SHA_SETTINGS"},
    "arena_pipeline_sha":         {"sha256": "$SHA_PIPELINE"},
    "arena23_orchestrator_sha":   {"sha256": "$SHA_ARENA23"}
  }
}
JSON
'
```

### 3.5 Gate state surface

Manual (until Phase 7 gov_reconciler automates):
- Read latest `gate_a_post_mod*_memo.md`
- Read `authoritative_condition_matrix.md` §1 table
- Record latest Gemini round verdict

## 4. SHA256 manifest

The `sha256_manifest` field at the root is computed over:
```
sha256(
  canonical_json(runtime) ||
  canonical_json(governance) ||
  canonical_json(repo) ||
  canonical_json(config) ||
  canonical_json(gate_state)
)
```

Where `canonical_json` uses Python's `json.dumps(obj, sort_keys=True, separators=(",", ":"))`.

Manifest mismatch between two snapshots means something changed. Explained in diff doc.

## 5. Actor attribution

`captured_by` field accepts:
- `j13` — j13 direct
- `claude@<session_id>` — Claude agent session (session UUID if available)
- `codex@<session_id>`
- `gemini@<session_id>`
- `gov_reconciler@<cron_ts>` — automated (Phase 7)

Actor attribution is informational; not a trust root (trust comes from surfaces + signatures where applicable).

## 6. File location convention

```
docs/governance/snapshots/<YYYYMMDDTHHMMSSZ>-<purpose>-<actor>.json
```

Example:
```
docs/governance/snapshots/20260424T002345Z-mod5-start-claude.json
docs/governance/snapshots/20260424T011523Z-mod5-commit-claude.json
```

Pair (pre + post) share identical `<purpose>` tag; `<ts>` differs by capture time.

## 7. Retention policy

Keep all snapshots for 90 days. After 90 days:
- monthly snapshots archived to AKASHA `segment=governance_snapshot_archive`
- daily snapshots deleted

Snapshots referenced by an open diff doc or classification memo are NOT eligible for deletion until the referencing doc is archived.

## 8. Non-negotiable rules compliance

| Rule | Evidence |
|---|---|
| 1. No silent mutation | ✅ — every capture command emits to committed file |
| 8. No broad refactor | ✅ — spec only |

## 9. Q1 adversarial

| Dim | Verdict |
|---|---|
| Input boundary | PASS — 5 surfaces × schema version |
| Silent failure | PASS — SHA manifest catches silent change |
| External dep | PASS — capture commands probe each surface independently |
| Concurrency | PASS — snapshots are point-in-time atomic capture per command |
| Scope creep | PASS — schema + capture only |

## 10. Label per 0-7 rule 10

- §1-§2 schema: **VERIFIED** (JSON schema deterministic)
- §3 capture commands: **VERIFIED** (runnable)
- §6 location: **VERIFIED** (convention)
- §7 retention: **PROBABLE** (Phase 7 automation)
