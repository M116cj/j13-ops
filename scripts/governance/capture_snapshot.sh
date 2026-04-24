#!/bin/bash
# capture_snapshot.sh — MOD-6 Phase 4 Phase 7 entry prerequisite 1.7
# Operationalizes the pre_post_snapshot_spec (v1) defined in MOD-5.
# Usage: capture_snapshot.sh <purpose> <actor>
# Output: docs/governance/snapshots/<ISO-ts>-<purpose>-<actor>.json

set -euo pipefail

PURPOSE="${1:-manual}"
ACTOR="${2:-$(whoami)@$(hostname -s)}"
TS="$(date -u +%Y-%m-%dT%H%M%SZ)"
OUTDIR="/home/j13/j13-ops/docs/governance/snapshots"
OUTFILE="${OUTDIR}/${TS}-${PURPOSE}-${ACTOR//[^a-zA-Z0-9_-]/_}.json"

mkdir -p "${OUTDIR}"

TMPDIR="$(mktemp -d)"
trap "rm -rf ${TMPDIR}" EXIT

cd /home/j13/j13-ops

# --- Runtime surface ---
ARENA_PIDS_RAW="$(pgrep -af 'arena_pipeline|arena23_orchestrator|arena45_orchestrator' 2>/dev/null | grep -v grep | awk '{print $1}' || true)"
ARENA_COUNT="$(echo -n "${ARENA_PIDS_RAW}" | grep -c '^' || true)"
ARENA_PIDS_JSON="$(echo "${ARENA_PIDS_RAW}" | tr '\n' ',' | sed 's/,$//' | awk '{print "["$0"]"}')"
[ "${ARENA_PIDS_JSON}" = "[]" ] || [ -z "${ARENA_PIDS_RAW}" ] && ARENA_PIDS_JSON="[]"

ENGINE_MTIME="$(stat -c %y /home/j13/j13-ops/zangetsu/logs/engine.jsonl 2>/dev/null || echo 'absent')"
ENGINE_SIZE="$(stat -c %s /home/j13/j13-ops/zangetsu/logs/engine.jsonl 2>/dev/null || echo 0)"

CALCIFER_STATUS="$(python3 -c 'import json; print(json.load(open("/tmp/calcifer_deploy_block.json")).get("status", "UNKNOWN"))' 2>/dev/null || echo 'UNKNOWN')"
CALCIFER_ISO="$(python3 -c 'import json; print(json.load(open("/tmp/calcifer_deploy_block.json")).get("iso", ""))' 2>/dev/null || echo '')"

# systemd units
for unit in calcifer-supervisor calcifer-miniapp d-mail-miniapp console-api dashboard-api cp-api; do
    STATE="$(systemctl is-active ${unit} 2>&1)"
    PID="$(systemctl show ${unit} -p MainPID --value 2>&1)"
    AET="$(systemctl show ${unit} -p ActiveEnterTimestamp --value 2>&1)"
    printf '  "%s": {"active": "%s", "main_pid": "%s", "active_since": "%s"}' \
        "${unit}" "${STATE}" "${PID}" "${AET}" >> "${TMPDIR}/units.jsonfrag"
    echo ',' >> "${TMPDIR}/units.jsonfrag"
done
UNITS="$(sed '$ s/,$//' "${TMPDIR}/units.jsonfrag" 2>/dev/null || echo '')"

# --- Governance surface ---
BP="$(gh api /repos/M116cj/j13-ops/branches/main/protection --jq '{req_sig: .required_signatures.enabled, linear: .required_linear_history.enabled, admin_enforce: .enforce_admins.enabled, force_push: .allow_force_pushes.enabled, deletions: .allow_deletions.enabled}' 2>/dev/null || echo '{}')"

AKASHA_HEALTH="$(curl -sf --connect-timeout 3 http://100.123.49.102:8769/health 2>/dev/null | python3 -c 'import json,sys; print(json.load(sys.stdin).get("status", "unknown"))' 2>/dev/null || echo 'down')"

# --- Repo surface ---
MAIN_SHA="$(git rev-parse HEAD)"
MAIN_SUBJECT="$(git log -1 --format=%s | head -c 200)"
MAIN_AUTHOR_ISO="$(git log -1 --format=%aI)"
PORCELAIN_LINES="$(git status --porcelain | wc -l)"

# --- Config surface (SHA256 of critical files) ---
SHA_CALCIFER_FLAG="$(sha256sum /tmp/calcifer_deploy_block.json 2>/dev/null | awk '{print $1}' || echo 'absent')"
SHA_CALCIFER_STATE="$(sha256sum /home/j13/j13-ops/calcifer/deploy_block_state.json 2>/dev/null | awk '{print $1}' || echo 'absent')"
SHA_SETTINGS="$(sha256sum /home/j13/j13-ops/zangetsu/config/settings.py 2>/dev/null | awk '{print $1}' || echo 'absent')"
SHA_PIPELINE="$(sha256sum /home/j13/j13-ops/zangetsu/services/arena_pipeline.py 2>/dev/null | awk '{print $1}' || echo 'absent')"
SHA_ARENA23="$(sha256sum /home/j13/j13-ops/zangetsu/services/arena23_orchestrator.py 2>/dev/null | awk '{print $1}' || echo 'absent')"
SHA_ARENA45="$(sha256sum /home/j13/j13-ops/zangetsu/services/arena45_orchestrator.py 2>/dev/null | awk '{print $1}' || echo 'absent')"
SHA_SUPERVISOR="$(sha256sum /home/j13/j13-ops/calcifer/supervisor.py 2>/dev/null | awk '{print $1}' || echo 'absent')"
SHA_OUTCOME="$(sha256sum /home/j13/j13-ops/calcifer/zangetsu_outcome.py 2>/dev/null | awk '{print $1}' || echo 'absent')"

# --- Gate state (read from authoritative memo — manual until phase 7) ---
# We hard-code against the latest memo location; future phase 7 gov_reconciler
# will read the classification from a canonical API.
GATE_MEMO_PATH="docs/recovery/20260424-mod-5/gate_a_post_mod5_memo.md"
GATE_CLASS="$(grep -oE 'Gate-A state: `[A-Z_]+`' "${GATE_MEMO_PATH}" 2>/dev/null | head -1 | sed 's/.*`\([A-Z_]*\)`.*/\1/' || echo 'UNKNOWN')"

cat > "${OUTFILE}" <<JSON
{
  "schema_version": 1,
  "captured_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "captured_by": "${ACTOR}",
  "purpose": "${PURPOSE}",
  "surfaces": {
    "runtime": {
      "arena_processes": {
        "count": ${ARENA_COUNT},
        "pids": ${ARENA_PIDS_JSON}
      },
      "engine_jsonl_mtime_iso": "${ENGINE_MTIME}",
      "engine_jsonl_size_bytes": ${ENGINE_SIZE},
      "calcifer_deploy_block_status": "${CALCIFER_STATUS}",
      "calcifer_deploy_block_ts_iso": "${CALCIFER_ISO}",
      "systemd_units": {
        ${UNITS}
      }
    },
    "governance": {
      "branch_protection_main": ${BP},
      "akasha_health": "${AKASHA_HEALTH}"
    },
    "repo": {
      "main_head_sha": "${MAIN_SHA}",
      "main_head_subject": "${MAIN_SUBJECT//\"/\\\"}",
      "main_head_author_iso": "${MAIN_AUTHOR_ISO}",
      "git_status_porcelain_lines": ${PORCELAIN_LINES}
    },
    "config": {
      "calcifer_deploy_block_file_sha": "${SHA_CALCIFER_FLAG}",
      "calcifer_state_file_sha": "${SHA_CALCIFER_STATE}",
      "zangetsu_settings_sha": "${SHA_SETTINGS}",
      "arena_pipeline_sha": "${SHA_PIPELINE}",
      "arena23_orchestrator_sha": "${SHA_ARENA23}",
      "arena45_orchestrator_sha": "${SHA_ARENA45}",
      "calcifer_supervisor_sha": "${SHA_SUPERVISOR}",
      "zangetsu_outcome_sha": "${SHA_OUTCOME}"
    },
    "gate_state": {
      "gate_a_classification": "${GATE_CLASS}",
      "classification_source_file": "${GATE_MEMO_PATH}"
    }
  }
}
JSON

# sha256 manifest (over the 5 surfaces object, sorted keys)
python3 -c "
import json, hashlib
d = json.load(open('${OUTFILE}'))
surfaces_canonical = json.dumps(d['surfaces'], sort_keys=True, separators=(',', ':'))
d['sha256_manifest'] = hashlib.sha256(surfaces_canonical.encode()).hexdigest()
json.dump(d, open('${OUTFILE}', 'w'), indent=2, sort_keys=True)
"

echo "snapshot written: ${OUTFILE}"
python3 -c "
import json
d = json.load(open('${OUTFILE}'))
print(f'  sha256_manifest: {d[\"sha256_manifest\"]}')
print(f'  arena_count: {d[\"surfaces\"][\"runtime\"][\"arena_processes\"][\"count\"]}')
print(f'  main_head: {d[\"surfaces\"][\"repo\"][\"main_head_sha\"][:12]}')
print(f'  gate_a: {d[\"surfaces\"][\"gate_state\"][\"gate_a_classification\"]}')
"
