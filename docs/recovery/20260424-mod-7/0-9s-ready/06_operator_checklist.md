# 06 — 0-9S-CANARY Operator Pre-Activation Checklist

## 0. Scope

This is the **runbook**. `05_evidence_template.md` is the **shape**.
Together they form the 0-9S-READY gate.

The checklist below is a sequential set of **commands** the operator
runs to populate the evidence package and verify CR1–CR15. Every box
ticked here corresponds to a specific block in `05_evidence_template.md`.

This file ships under PR-D / 0-9S-READY (documentation-only). It does
**not** activate CANARY. CANARY activation is a separate j13 order
(`0-9S-CANARY`) executed against this checklist after evidence is
filed.

### Conventions used below

- `{{N}}` = the cohort attempt number (1, 2, 3, ...)
- `{{operator}}` = unix login of the operator on Alaya
- All SSH targets: `j13@100.123.49.102` (Tailscale)
- Repo: `M116cj/j13-ops`, branch: `main` (signed-PR-only)
- Evidence directory:
  `docs/governance/canary-evidence/{{YYYYMMDD}}-canary-{{N}}/`
- All timestamps UTC unless noted

### Hard rules in force throughout

- CLAUDE.md §17.1: only the `zangetsu_status` VIEW is "deployable"
- CLAUDE.md §17.6: stale-service check before declaring `done`
- CLAUDE.md §17.5: `feat(zangetsu/vN)` is bot-only
- CLAUDE.md §17.3 / §17.4: Calcifer outcome watch + auto-revert
- 0-9R § 7 F1–F8: any failure criterion → STOP + rollback (no override)

---

## Phase 0 — Pre-flight (T-1 day)

Goal: confirm baseline state. Nothing destructive. ~30 min.

### 0.1 Sync local main with origin

- [ ] Fetch + compare:

```bash
git fetch origin
LOCAL=$(git rev-parse main)
REMOTE=$(git rev-parse origin/main)
[ "$LOCAL" = "$REMOTE" ] || { echo "DRIFT: local=$LOCAL remote=$REMOTE"; exit 1; }
echo "OK: main aligned at $LOCAL"
```

If drift: rebase or pull. Do not proceed with stale main.

### 0.2 Pull most recent attribution audit verdict

- [ ] Run audit on a fresh ≥ 7-day window:

```bash
python3 - <<'PY'
from datetime import datetime, timedelta, timezone
from zangetsu.tools.profile_attribution_audit import audit
end = datetime.now(timezone.utc)
start = end - timedelta(days=7)
result = audit(window_start=start, window_end=end)
print(f"verdict={result.verdict}")
print(f"window={start.isoformat()} -> {end.isoformat()}")
print(f"total_events={result.total_events}")
print(f"passport_identity_rate={result.passport_identity_rate:.4f}")
print(f"orchestrator_fallback_rate={result.orchestrator_fallback_rate:.4f}")
print(f"unknown_profile_rate={result.unknown_profile_rate:.4f}")
print(f"profile_mismatch_rate={result.profile_mismatch_rate:.4f}")
print(f"fingerprint_unavailable_rate={result.fingerprint_unavailable_rate:.4f}")
PY
```

- [ ] Capture JSON to evidence dir:

```bash
mkdir -p docs/governance/canary-evidence/$(date -u +%Y%m%d)-canary-{{N}}/
python3 -m zangetsu.tools.profile_attribution_audit \
  --window-days 7 \
  --output docs/governance/canary-evidence/$(date -u +%Y%m%d)-canary-{{N}}/audit.json
```

### 0.3 Confirm verdict GREEN or documented YELLOW

- [ ] Check verdict:

```bash
VERDICT=$(jq -r '.verdict' docs/governance/canary-evidence/$(date -u +%Y%m%d)-canary-{{N}}/audit.json)
case "$VERDICT" in
  GREEN)  echo "OK: GREEN — proceed";;
  YELLOW) echo "YELLOW — operator MUST document offending rate + cause in evidence § 3";;
  RED)    echo "RED — STOP. Do not proceed. File evidence-aborted.md."; exit 1;;
  *)      echo "Unknown verdict: $VERDICT"; exit 1;;
esac
```

- [ ] If YELLOW: write justification to evidence § 3 (rate + cause).
  Reference `0-9r-impl-dry/04_attribution_audit_dependency.md` § 3
  step 4.
- [ ] If RED: full STOP. Do not proceed to phase 1.

### 0.4 Confirm dry-run consumer ≥ 7 days stable

- [ ] Query AKASHA events for `sparse_candidate_dry_run_plan`:

```bash
ssh j13@100.123.49.102 \
  "psql -d zangetsu -c \"\
    SELECT
      COUNT(*) AS total,
      COUNT(*) FILTER (WHERE plan_status = 'ACTIONABLE_DRY_RUN') AS actionable,
      COUNT(*) FILTER (WHERE plan_status = 'NON_ACTIONABLE')    AS non_actionable,
      COUNT(*) FILTER (WHERE plan_status = 'BLOCKED')           AS blocked,
      MIN(emitted_at) AS earliest,
      MAX(emitted_at) AS latest
    FROM events
    WHERE event_type = 'sparse_candidate_dry_run_plan'
      AND emitted_at >= NOW() - INTERVAL '7 days';\""
```

- [ ] All plans have `plan_applied = false` (dry-run invariant):

```bash
ssh j13@100.123.49.102 \
  "psql -d zangetsu -t -c \"\
    SELECT COUNT(*) FROM events
     WHERE event_type='sparse_candidate_dry_run_plan'
       AND emitted_at >= NOW() - INTERVAL '7 days'
       AND (payload->>'plan_applied')::boolean = true;\"" \
  | tr -d ' '
```

Expected output: `0`. Any other value = consumer broke dry-run
invariant → STOP, file incident.

- [ ] No `BLOCKED` with `ATTRIBUTION_VERDICT_RED` in trailing 7 days:

```bash
ssh j13@100.123.49.102 \
  "psql -d zangetsu -t -c \"\
    SELECT COUNT(*) FROM events
     WHERE event_type='sparse_candidate_dry_run_plan'
       AND emitted_at >= NOW() - INTERVAL '7 days'
       AND payload->'block_reasons' ? 'ATTRIBUTION_VERDICT_RED';\"" \
  | tr -d ' '
```

Expected: `0`. Any other value = audit verdict regressed mid-window
→ STOP, restart phase 0.

- [ ] Consecutive sign-stable runs ≥ 5 on most recent actionable
  profile:

```bash
ssh j13@100.123.49.102 \
  "psql -d zangetsu -c \"\
    SELECT profile_id, consecutive_sign_stable_runs
      FROM dry_run_profile_stability
     WHERE consecutive_sign_stable_runs >= 5
     ORDER BY last_run_at DESC LIMIT 10;\""
```

If no rows: § 03 multi-window condition not met → STOP, wait for
stability.

### 0.5 Confirm Calcifer responding

- [ ] Service status:

```bash
ssh j13@100.123.49.102 "systemctl status calcifer-supervisor --no-pager"
```

Expect `active (running)`.

- [ ] Heartbeat fresh:

```bash
ssh j13@100.123.49.102 "stat -c '%Y' /var/run/calcifer/heartbeat.txt"
NOW=$(date +%s)
HB=$(ssh j13@100.123.49.102 "stat -c '%Y' /var/run/calcifer/heartbeat.txt")
AGE=$(( NOW - HB ))
[ "$AGE" -lt 600 ] || { echo "Calcifer heartbeat stale: ${AGE}s"; exit 1; }
echo "OK: Calcifer heartbeat ${AGE}s"
```

- [ ] No active deploy block:

```bash
ssh j13@100.123.49.102 'ls /tmp/calcifer_deploy_block.json 2>/dev/null && echo "BLOCK PRESENT — STOP" && exit 1; echo "OK: no block"'
```

### 0.6 Capture 14-day baseline metrics (live VIEW)

- [ ] Per CLAUDE.md §17.1, query the `zangetsu_status` VIEW:

```bash
ssh j13@100.123.49.102 \
  "psql -d zangetsu -A -F, -c \"\
    SELECT
      a2_pass_rate_14d,
      a3_pass_rate_14d,
      a2_signal_too_sparse_rate_14d,
      a3_oos_fail_rate_14d,
      deployable_count_7d_median,
      unknown_reject_rate_14d
    FROM zangetsu_status;\"" \
  | tee docs/governance/canary-evidence/$(date -u +%Y%m%d)-canary-{{N}}/baseline-metrics.csv
```

- [ ] Convert to JSON for evidence § 5:

```bash
python3 - <<'PY' > docs/governance/canary-evidence/$(date -u +%Y%m%d)-canary-{{N}}/baseline-metrics.json
import csv, json, sys, datetime
with open(f"docs/governance/canary-evidence/{datetime.datetime.utcnow():%Y%m%d}-canary-{{N}}/baseline-metrics.csv") as f:
    rows = list(csv.DictReader(f))
print(json.dumps({
    "queried_at": datetime.datetime.utcnow().isoformat() + "Z",
    "rows": rows,
}, indent=2))
PY
```

- [ ] Verify `unknown_reject_rate_14d < 0.05` (S6 invariant):

```bash
RATE=$(jq -r '.rows[0].unknown_reject_rate_14d' \
  docs/governance/canary-evidence/$(date -u +%Y%m%d)-canary-{{N}}/baseline-metrics.json)
python3 -c "import sys; sys.exit(0 if float('$RATE') < 0.05 else 1)" \
  || { echo "S6 violated: unknown_reject_rate=$RATE"; exit 1; }
```

---

## Phase 1 — Snapshot (T-1 hour)

Goal: freeze the universe before any state change. ~15 min.

### 1.1 Capture pre-CANARY snapshot

- [ ] Run snapshot script on Alaya:

```bash
ssh j13@100.123.49.102 \
  "scripts/governance/capture_snapshot.sh pre-canary-{{N}} {{operator}}"
```

- [ ] Verify snapshot file exists and is non-empty:

```bash
ssh j13@100.123.49.102 \
  "ls -lh ~/snapshots/pre-canary-{{N}}-*.tar.gz | tail -1"
```

- [ ] Pull snapshot to evidence dir:

```bash
scp j13@100.123.49.102:~/snapshots/pre-canary-{{N}}-*.tar.gz \
  docs/governance/canary-evidence/$(date -u +%Y%m%d)-canary-{{N}}/snapshot-pre-canary.tar.gz
sha256sum docs/governance/canary-evidence/$(date -u +%Y%m%d)-canary-{{N}}/snapshot-pre-canary.tar.gz
```

### 1.2 Verify branch protection

- [ ] Pull live snapshot:

```bash
gh api repos/M116cj/j13-ops/branches/main/protection \
  > docs/governance/canary-evidence/$(date -u +%Y%m%d)-canary-{{N}}/branch-protection.json
```

- [ ] Required values check:

```bash
gh api repos/M116cj/j13-ops/branches/main/protection \
  --jq '.enforce_admins.enabled, .required_signatures.enabled, .required_linear_history.enabled, .allow_force_pushes.enabled, .allow_deletions.enabled'
```

Expected output, exactly five lines:

```
true
true
true
false
false
```

Any deviation → STOP. Branch protection drift = abort.

### 1.3 Capture baseline weights

- [ ] Snapshot allocator weights:

```bash
ssh j13@100.123.49.102 \
  "cat /var/lib/zangetsu/feedback_budget_allocator/current_weights.json" \
  > docs/governance/canary-evidence/$(date -u +%Y%m%d)-canary-{{N}}/baseline-weights.json
sha256sum docs/governance/canary-evidence/$(date -u +%Y%m%d)-canary-{{N}}/baseline-weights.json
```

- [ ] Confirm weight count and floor invariants:

```bash
python3 - <<'PY'
import json, sys, datetime
p = f"docs/governance/canary-evidence/{datetime.datetime.utcnow():%Y%m%d}-canary-{{N}}/baseline-weights.json"
data = json.load(open(p))
weights = data["weights"]
assert all(w >= 0.05 for w in weights.values()), f"F7: floor violated in {weights}"
assert sum(weights.values()) == 1.0 or abs(sum(weights.values()) - 1.0) < 1e-6, "weights do not sum to 1.0"
print(f"OK: {len(weights)} profiles, all >= 0.05, sum=1.0")
PY
```

---

## Phase 2 — Tag (T-30 min)

Goal: signed annotated tag pointing at the SHA we will activate from.

### 2.1 Create signed tag

- [ ] Tag origin/main exactly:

```bash
git fetch origin
SHA=$(git rev-parse origin/main)
git tag -s 0-9s-canary-{{N}}-pre "$SHA" \
  -m "pre-CANARY tag for evidence trail; cohort {{N}}; operator {{operator}}"
```

### 2.2 Push tag

- [ ] Push and verify:

```bash
git push origin 0-9s-canary-{{N}}-pre
git fetch origin --tags
git rev-parse 0-9s-canary-{{N}}-pre
```

### 2.3 Verify signature

- [ ] Verify GPG/SSH signature:

```bash
git tag -v 0-9s-canary-{{N}}-pre 2>&1 | tee \
  docs/governance/canary-evidence/$(date -u +%Y%m%d)-canary-{{N}}/git-tag-verify.txt
```

Expect `Good signature`. Anything else → STOP, regenerate the tag with
the correct signing key.

---

## Phase 3 — Calcifer + AKASHA preflight (T-15 min)

Goal: prove the alert path is wired before activation.

### 3.1 Calcifer GREEN (no deploy block)

- [ ] One-line check:

```bash
ssh j13@100.123.49.102 \
  'ls /tmp/calcifer_deploy_block.json 2>/dev/null && exit 1; echo OK'
```

If `/tmp/calcifer_deploy_block.json` exists → STOP. Read the file,
resolve the underlying outcome regression, then restart phase 0.

### 3.2 AKASHA witness preflight

- [ ] Reserve a witness slot:

```bash
curl -sS -X POST http://100.123.49.102:8769/witness/preflight \
  -H 'content-type: application/json' \
  -d '{
        "order": "0-9S-CANARY",
        "cohort": "{{N}}",
        "operator": "{{operator}}",
        "git_tag": "0-9s-canary-{{N}}-pre"
      }' \
  | tee docs/governance/canary-evidence/$(date -u +%Y%m%d)-canary-{{N}}/akasha-witness-receipt.json
```

- [ ] Verify a `slot_id` was issued:

```bash
SLOT=$(jq -r '.slot_id' \
  docs/governance/canary-evidence/$(date -u +%Y%m%d)-canary-{{N}}/akasha-witness-receipt.json)
[ -n "$SLOT" ] && [ "$SLOT" != "null" ] || { echo "AKASHA preflight failed"; exit 1; }
echo "AKASHA slot reserved: $SLOT"
```

### 3.3 Telegram bot reachable

- [ ] `getMe` smoke:

```bash
source ~/.env.global  # ALAYA13_TG_TOKEN
curl -sS "https://api.telegram.org/bot${ALAYA13_TG_TOKEN}/getMe" \
  | tee docs/governance/canary-evidence/$(date -u +%Y%m%d)-canary-{{N}}/telegram-getme.json
```

Expect `{"ok":true,...}`.

### 3.4 Alert routes (INFO / WARN / BLOCKING / FATAL)

- [ ] Send one preflight test per route:

```bash
for LEVEL in INFO WARN BLOCKING FATAL; do
  curl -sS -X POST \
    "https://api.telegram.org/bot${ALAYA13_TG_TOKEN}/sendMessage" \
    -d "chat_id=-1003601437444" \
    -d "message_thread_id=362" \
    -d "text=[0-9S-CANARY-{{N}} preflight] route=${LEVEL} ts=$(date -u +%FT%TZ)" \
    | jq -c '{level: "'"$LEVEL"'", message_id: .result.message_id, ok: .ok}'
done > docs/governance/canary-evidence/$(date -u +%Y%m%d)-canary-{{N}}/telegram-preflight.json
```

All four lines must show `"ok":true`.

---

## Phase 4 — Rollback drill (T-10 min)

Goal: confirm we can roll back, **before** we activate.

### 4.1 Run rollback dry-run

- [ ] Dry-run the rollback script:

```bash
bash scripts/canary/rollback.sh --dry-run \
  --baseline-weights docs/governance/canary-evidence/$(date -u +%Y%m%d)-canary-{{N}}/baseline-weights.json \
  | tee docs/governance/canary-evidence/$(date -u +%Y%m%d)-canary-{{N}}/rollback-drill-1.log
echo "exit=$?"
```

Exit 0 + log shows hot-swap plan + no actual writes.

### 4.2 Verify hot-swap path

- [ ] Confirm no service restart required:

```bash
grep -c 'systemctl restart' docs/governance/canary-evidence/$(date -u +%Y%m%d)-canary-{{N}}/rollback-drill-1.log
```

Expected: `0`. Rollback must be hot-swap only (0-9R § 8 step 1).

### 4.3 Confirm baseline weights restorable

- [ ] Diff the dry-run plan against current allocator weights:

```bash
ssh j13@100.123.49.102 \
  "diff <(cat /var/lib/zangetsu/feedback_budget_allocator/current_weights.json) \
        <(cat /var/lib/zangetsu/feedback_budget_allocator/baseline_weights.json) \
   | head -50"
```

If treatment weights are not yet applied (we are pre-activation), the
two files should be identical → diff exit 0, no output. After
activation, this diff will be the live signal that rollback is needed.

### 4.4 Repeat drill 2 and drill 3

- [ ] Run drill 2 (use a slightly different cohort tag in --plan-id to
  exercise the script):

```bash
bash scripts/canary/rollback.sh --dry-run --plan-id "drill-2" \
  --baseline-weights docs/governance/canary-evidence/$(date -u +%Y%m%d)-canary-{{N}}/baseline-weights.json \
  | tee docs/governance/canary-evidence/$(date -u +%Y%m%d)-canary-{{N}}/rollback-drill-2.log
```

- [ ] Run drill 3:

```bash
bash scripts/canary/rollback.sh --dry-run --plan-id "drill-3" \
  --baseline-weights docs/governance/canary-evidence/$(date -u +%Y%m%d)-canary-{{N}}/baseline-weights.json \
  | tee docs/governance/canary-evidence/$(date -u +%Y%m%d)-canary-{{N}}/rollback-drill-3.log
```

CR5 requires **≥ 3 successful drills**. All three exit 0.

### 4.5 Stale-service check (CLAUDE.md §17.6)

- [ ] Each long-running service: ActiveEnterTimestamp ≥ source mtime:

```bash
ssh j13@100.123.49.102 'bash -s' <<'EOF' \
  | tee docs/governance/canary-evidence/$(date -u +%Y%m%d)-canary-{{N}}/stale-service-check.json
set -e
declare -A SERVICES=(
  [feedback_budget_consumer]="/srv/zangetsu/zangetsu/services/feedback_budget_consumer.py"
  [feedback_budget_allocator]="/srv/zangetsu/zangetsu/services/feedback_budget_allocator.py"
  [calcifer-supervisor]="/srv/calcifer/supervisor.py"
)
echo "{"
first=true
for SVC in "${!SERVICES[@]}"; do
  SRC="${SERVICES[$SVC]}"
  PROC=$(systemctl show "$SVC" -p ActiveEnterTimestamp --value | xargs -I{} date -d {} +%s)
  MTIME=$(stat -c %Y "$SRC")
  STATUS="FRESH"
  [ "$PROC" -gt "$MTIME" ] || STATUS="STALE"
  $first || echo ","
  first=false
  echo "  \"$SVC\": {\"proc_start\": $PROC, \"source_mtime\": $MTIME, \"status\": \"$STATUS\"}"
done
echo
echo "}"
EOF
```

- [ ] Reject if any `STALE`:

```bash
jq -r 'to_entries[] | select(.value.status=="STALE") | .key' \
  docs/governance/canary-evidence/$(date -u +%Y%m%d)-canary-{{N}}/stale-service-check.json \
  | tee /tmp/stale-services.txt
[ ! -s /tmp/stale-services.txt ] || { echo "STALE: $(cat /tmp/stale-services.txt)"; exit 1; }
echo "OK: all services FRESH"
```

---

## Phase 5 — Sign-off (T-0)

Goal: human + AKASHA confirmation, immutable trail.

### 5.1 Confirm j13 authorization sentence

- [ ] Paste verbatim into evidence § 1 (do **not** paraphrase):
  Look for the literal token `0-9S-CANARY` plus `授權` / `authorize`
  plus a timestamp.

If sentence is ambiguous:

```bash
echo "Authorization sentence ambiguous. Re-requesting from j13. STOP."
exit 1
```

### 5.2 Confirm evidence package complete

- [ ] All files present in evidence dir:

```bash
EVID=docs/governance/canary-evidence/$(date -u +%Y%m%d)-canary-{{N}}
for f in evidence.md audit.json consumer-stability.json branch-protection.json \
         snapshot-pre-canary.tar.gz baseline-weights.json baseline-metrics.json \
         rollback-drill-1.log rollback-drill-2.log rollback-drill-3.log \
         stale-service-check.json telegram-preflight.json telegram-getme.json \
         akasha-witness-receipt.json git-tag-verify.txt; do
  [ -f "$EVID/$f" ] || { echo "MISSING: $f"; exit 1; }
done
echo "OK: evidence package complete"
```

- [ ] All `{{...}}` placeholders in `evidence.md` are replaced:

```bash
grep -nE '\{\{[^}]+\}\}' "$EVID/evidence.md" \
  && { echo "EVIDENCE INCOMPLETE: unfilled placeholders above"; exit 1; } \
  || echo "OK: no unfilled placeholders"
```

- [ ] Decision record + (if /team used) retro file present (CR15 / §17.7):

```bash
DATE=$(date -u +%Y%m%d)
[ -f "docs/decisions/${DATE}-canary-{{N}}.md" ] \
  || { echo "MISSING: docs/decisions/${DATE}-canary-{{N}}.md"; exit 1; }
# Retro is required only if /team was used during preparation:
if grep -q "team mode" "$EVID/evidence.md"; then
  [ -f "docs/retros/${DATE}-canary-{{N}}.md" ] \
    || { echo "MISSING: docs/retros/${DATE}-canary-{{N}}.md (required by §17.7 because /team used)"; exit 1; }
fi
echo "OK: decision record present"
```

### 5.3 Operator signature commit

- [ ] Stage and commit the evidence directory on a signed branch:

```bash
git checkout -b ops/0-9s-canary-{{N}}-evidence
git add docs/governance/canary-evidence/$(date -u +%Y%m%d)-canary-{{N}}/
git add docs/governance/canary-evidence/INDEX.md  # update the index
git add docs/decisions/$(date -u +%Y%m%d)-canary-{{N}}.md
git commit -S -m "ops(0-9s-ready): evidence package for canary-{{N}} pre-activation"
git push -u origin ops/0-9s-canary-{{N}}-evidence
gh pr create --base main --title "ops(0-9s-ready): canary-{{N}} evidence" \
  --body "Evidence package for 0-9S-CANARY canary-{{N}} pre-activation. Closes CR15."
```

PR must merge with signed-PR + decision-record CI gate green.

### 5.4 Push to AKASHA witness

- [ ] Confirm the slot reserved at § 3.2 was finalized:

```bash
SLOT=$(jq -r '.slot_id' "$EVID/akasha-witness-receipt.json")
curl -sS -X POST http://100.123.49.102:8769/witness/finalize \
  -H 'content-type: application/json' \
  -d "{
        \"slot_id\": \"$SLOT\",
        \"evidence_pr\": \"$(gh pr view --json number --jq .number)\",
        \"evidence_dir\": \"$EVID\",
        \"git_tag\": \"0-9s-canary-{{N}}-pre\"
      }" \
  | tee "$EVID/akasha-witness-finalize.json"
jq -e '.status=="FINALIZED"' "$EVID/akasha-witness-finalize.json" \
  || { echo "AKASHA finalize failed"; exit 1; }
```

---

## Phase 6 — Post-activation watch (T+)

Goal: continuous outcome verification once CANARY is live. CANARY
activation itself is a separate j13 order; this section is what the
operator does **after** that order has been issued and applied.

### 6.1 Continuous Calcifer poll

- [ ] Watchdog runs at 5-min cadence (per CLAUDE.md §17.3). Operator
  monitors:

```bash
ssh j13@100.123.49.102 \
  'while true; do
     ls /tmp/calcifer_deploy_block.json 2>/dev/null && {
       echo "[$(date -u +%FT%TZ)] CALCIFER RED — INITIATE ROLLBACK"
       break
     }
     sleep 300
   done'
```

If the loop emits `CALCIFER RED` → run § 7 Hard STOP rollback.

### 6.2 Telegram digest cadence

- [ ] Confirm digests post at: `T+5min`, `T+30min`, `T+1h`, `T+24h`,
  `T+72h`, `T+7d`, `T+14d`. Operator records each in evidence § 13.

```bash
# Each digest contains: composite score, A2/A3 pass_rate delta vs baseline,
# deployable_count delta, F1-F8 status, audit verdict.
```

If a scheduled digest does not arrive within +5 min of its target →
investigate the digest job; do **not** silently skip.

### 6.3 Daily audit re-run

- [ ] Each calendar day during CANARY:

```bash
python3 -m zangetsu.tools.profile_attribution_audit \
  --window-days 7 \
  --output docs/governance/canary-evidence/$(date -u +%Y%m%d)-canary-{{N}}/audit-day-$((DAY_INDEX)).json
```

- [ ] If any daily verdict regresses to `RED`: § 7 Hard STOP.

### 6.4 Composite score tracking

- [ ] Track:

```
composite = 0.40 * a2_pass_rate
          + 0.40 * a3_pass_rate
          + 0.20 * deployable_density
```

- [ ] Treatment composite ≥ baseline composite + 1 sigma noise → S12
  trending pass.
- [ ] Treatment composite < baseline composite by > 1 sigma for ≥ 3
  consecutive days → escalate to j13 with rollback recommendation.

### 6.5 Outcome-metric watchdog (CLAUDE.md §17.4)

- [ ] If `deployable_count` 7-day median drops, OR
  `last_live_at_age_h > 12` while a `feat(zangetsu/vN)` is live →
  auto-revert trips. Operator confirms:

```bash
ssh j13@100.123.49.102 \
  "tail -n 200 /var/log/zangetsu/auto_revert_watchdog.log"
```

---

## 7. Hard STOP triggers (apply during any phase)

If **any** of the following fires, stop immediately and (if
post-activation) execute rollback:

| Trigger                                            | Action                                                                                                  |
| -------------------------------------------------- | ------------------------------------------------------------------------------------------------------- |
| Calcifer goes RED (`/tmp/calcifer_deploy_block.json` appears) | STOP. Pre-activation: abort phase 0–5. Post-activation: `bash scripts/canary/rollback.sh --execute`. |
| Branch protection drift detected                   | STOP. Reset protection via `gh api --method PUT`; restart phase 1.                                       |
| Audit verdict regresses to RED                     | STOP. Pre: phase 0 restart. Post: `rollback.sh --execute --reason audit_red`.                            |
| Any F1–F9 criterion observed (0-9R § 7)            | STOP + rollback. j13 cannot override (per 0-9R § 7).                                                     |
| j13 STOP message received                          | Immediate `rollback.sh --execute --reason j13_stop`. No further evidence work until j13 clears.          |
| Stale-service check fails (CLAUDE.md §17.6)        | STOP. Restart the stale service, restart phase 4.5.                                                      |
| AKASHA witness service unreachable                 | STOP. Pre: hold phase 3.2 until reachable. Post: emit FATAL alert; investigate before next digest.       |
| Telegram bot @Alaya13jbot down                     | STOP. We lose the alert path → cannot run CANARY safely.                                                 |
| `version-bump-gate` GitHub Action red              | STOP. Per CLAUDE.md §17.2, no manual override.                                                           |

### Rollback shell (post-activation only)

```bash
bash scripts/canary/rollback.sh \
  --execute \
  --baseline-weights docs/governance/canary-evidence/$(date -u +%Y%m%d)-canary-{{N}}/baseline-weights.json \
  --reason "{{enum: calcifer_red | audit_red | f1..f9 | j13_stop | stale_service | other}}" \
  --evidence-dir docs/governance/canary-evidence/$(date -u +%Y%m%d)-canary-{{N}}/
```

After rollback:

- [ ] Telegram FATAL alert sent (`0-9R-IMPL rollback triggered: ...`)
- [ ] Calcifer writes incident log →
  `docs/governance/incidents/$(date -u +%Y%m%d)-canary-{{N}}-rollback.md`
- [ ] AKASHA witness receipt updated:
  `treatment ended, reason, snapshot SHA`
- [ ] j13 review within 24 hours; treatment does not restart until
  review concludes
- [ ] PR opened against `main` with the incident log + retro file
  `docs/retros/$(date -u +%Y%m%d)-canary-{{N}}.md`

---

## 8. Cross-references

| Source                                              | Relevance                                                |
| --------------------------------------------------- | -------------------------------------------------------- |
| `05_evidence_template.md` (this dir)                | shape of the evidence package; this checklist populates it |
| `0-9r/05_ab_evaluation_and_canary_readiness.md`     | CR1–CR9, S1–S12, F1–F8, rollback procedure               |
| `0-9r-impl-dry/04_attribution_audit_dependency.md`  | CR2 verdict-consumption rules                            |
| 0-9P-AUDIT (PR #22, SHA `3219b805`)                 | `audit()` API, GREEN/YELLOW/RED                          |
| 0-9R-IMPL-DRY (PR #23, SHA `fe3075f`)               | dry-run consumer, plan_status fields                     |
| 0-9P (PR #21, SHA `a8a8ba9`)                         | passport persistence, `resolve_attribution_chain`        |
| 0-9O-B                                               | feedback_budget_allocator                                |
| P7-PR4B                                              | A1/A2/A3 aggregate Arena telemetry                       |
| `scripts/governance/capture_snapshot.sh`            | phase 1 snapshot                                         |
| `scripts/canary/rollback.sh`                        | phase 4 drills, hard-STOP execution                      |
| CLAUDE.md §17.1                                     | `zangetsu_status` VIEW = single truth                    |
| CLAUDE.md §17.2                                     | mandatory AKASHA witness                                 |
| CLAUDE.md §17.3                                     | Calcifer outcome watch                                   |
| CLAUDE.md §17.4                                     | auto-regression revert                                   |
| CLAUDE.md §17.5                                     | bin/bump_version.py enforcement                          |
| CLAUDE.md §17.6                                     | stale-service check                                      |
| CLAUDE.md §17.7                                     | decision-record CI gate                                  |

---

## 9. Maintainer notes

- This checklist is **commands**, not narrative. If a step cannot be
  expressed as a verifiable command, it is a documentation gap —
  open a PR to fix it before the next CANARY attempt.
- All commands are idempotent (safe to re-run) **except** § 2.1 `git
  tag -s` (one tag per cohort) and § 5.3 commit/push. Wrap re-runnable
  steps in shell guards rather than asking the operator to remember.
- If a step requires Alaya SSH and Alaya is unreachable, the operator
  invokes `/alaya-health-check` skill before continuing. CANARY
  cannot activate while Alaya is degraded.
- The retention rule is the same as evidence: this file plus its
  history is non-deletable. Edits flow through signed PRs.
