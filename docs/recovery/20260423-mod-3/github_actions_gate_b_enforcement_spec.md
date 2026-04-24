# GitHub Actions Gate-B Enforcement Spec

**Order**: `/home/j13/claude-inbox/0-4` Phase 1 deliverable
**Produced**: 2026-04-23T07:25Z
**Purpose**: Full workflow specification that cannot be bypassed by label omission or `--no-verify`.

---

## 1. File location

`/home/j13/j13-ops/.github/workflows/module-migration-gate.yml`

To be created during MOD-3 commit (documentation only; workflow itself is a spec deliverable, not a runtime file until j13 authorizes activation).

## 2. Full workflow YAML (design spec)

```yaml
name: Module Migration Gate (Gate-B)

on:
  pull_request:
    paths:
      - 'zangetsu/src/modules/**'
      - 'zangetsu/src/l[0-9]*/**'
      - 'zangetsu/module_contracts/*.yaml'
      - 'zangetsu/module_contracts/*.yml'
  push:
    branches: [main]
    paths:
      - 'zangetsu/src/modules/**'
      - 'zangetsu/src/l[0-9]*/**'
      - 'zangetsu/module_contracts/*.yaml'
      - 'zangetsu/module_contracts/*.yml'

permissions:
  contents: read
  pull-requests: write
  actions: read

concurrency:
  group: gate-b-${{ github.ref }}
  cancel-in-progress: false  # DO NOT cancel running gate checks on force-push

jobs:
  identify_affected_modules:
    runs-on: ubuntu-latest
    outputs:
      module_ids: ${{ steps.extract.outputs.module_ids }}
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
      - name: Extract affected module IDs from changed paths
        id: extract
        run: |
          # For PR: compare against base; for push: compare against main^
          CHANGED=$(git diff --name-only ${{ github.event.pull_request.base.sha || 'HEAD^' }} HEAD)
          # Extract unique module_ids from patterns:
          #   zangetsu/src/modules/<id>/...
          #   zangetsu/src/l<N>_<name>/<id>/...
          #   zangetsu/module_contracts/<id>.yaml
          MODULE_IDS=$(echo "$CHANGED" | awk -F/ '
            /zangetsu\/src\/modules\// {print $4}
            /zangetsu\/src\/l[0-9]/ {print $4}
            /zangetsu\/module_contracts\/.*\.yaml$/ {gsub(/\.yaml$/, "", $3); print $3}
          ' | sort -u | tr '\n' ' ')
          echo "module_ids=$MODULE_IDS" >> $GITHUB_OUTPUT
      - name: Fail fast if no modules affected (noop exit)
        if: steps.extract.outputs.module_ids == ''
        run: exit 0

  gate_b_per_module:
    needs: identify_affected_modules
    if: needs.identify_affected_modules.outputs.module_ids != ''
    runs-on: ubuntu-latest
    strategy:
      fail-fast: false
      matrix:
        module_id: ${{ fromJSON(needs.identify_affected_modules.outputs.module_ids_json) }}
    steps:
      - uses: actions/checkout@v4

      - name: B.1 — contract exists + schema-valid
        run: |
          YAML="zangetsu/module_contracts/${{ matrix.module_id }}.yaml"
          test -f "$YAML" || { echo "::error::contract missing: $YAML"; exit 1; }
          python3 scripts/ci/validate_module_contract.py "$YAML" \
            --template zangetsu/docs/recovery/20260423-mod-3/amended_module_contract_template.md
          # validates all 15 MANDATORY fields (14 original + Field 15 execution_environment)

      - name: B.1 — CP registry entry present
        env:
          CP_API_URL: ${{ secrets.CP_API_URL }}
          CP_API_TOKEN: ${{ secrets.CP_API_TOKEN }}
        run: |
          STATUS=$(curl -sf -o /dev/null -w "%{http_code}" \
            -H "Authorization: Bearer $CP_API_TOKEN" \
            "$CP_API_URL/api/control/modules/${{ matrix.module_id }}")
          [ "$STATUS" = "200" ] || { echo "::error::module ${{ matrix.module_id }} not registered in CP"; exit 1; }

      - name: B.1 — Gemini adversarial sign-off ADR exists
        run: |
          ADR_PATTERN="docs/decisions/*-module-${{ matrix.module_id }}.md"
          ls $ADR_PATTERN 1> /dev/null 2>&1 || {
            echo "::error::Gemini sign-off ADR missing: $ADR_PATTERN"; exit 1;
          }
          grep -q "Gemini verdict: ACCEPT" $ADR_PATTERN || {
            echo "::error::ADR exists but Gemini ACCEPT verdict not recorded"; exit 1;
          }

      - name: B.2 — rollout tier SHADOW + CANARY ≥ 72h each
        env:
          CP_API_URL: ${{ secrets.CP_API_URL }}
          CP_API_TOKEN: ${{ secrets.CP_API_TOKEN }}
        run: |
          # Query control_plane.rollout_audit for this module
          RESP=$(curl -sf -H "Authorization: Bearer $CP_API_TOKEN" \
            "$CP_API_URL/api/control/rollout/${{ matrix.module_id }}/history")
          python3 scripts/ci/verify_rollout_sla.py "$RESP" \
            --require-shadow-hours 72 --require-canary-hours 72

      - name: B.2 — no alerts fired during shadow/canary
        run: |
          python3 scripts/ci/verify_no_alerts_during_rollout.py \
            --module-id ${{ matrix.module_id }}

      - name: B.2 — rollback_surface.rollback_path rehearsal executed
        run: |
          python3 scripts/ci/verify_rollback_rehearsal.py \
            --module-id ${{ matrix.module_id }}

      - name: B.3 — rollback runbook exists
        run: |
          RUNBOOK="docs/rollback/${{ matrix.module_id }}.md"
          test -f "$RUNBOOK" || { echo "::error::rollback runbook missing: $RUNBOOK"; exit 1; }

      - name: B.3 — empirical rollback p95 within SLA
        run: |
          python3 scripts/ci/verify_rollback_p95.py \
            --module-id ${{ matrix.module_id }} \
            --max-p95-seconds 600

      - name: B.3 — consumer modules contract_version_max compatible
        env:
          CP_API_URL: ${{ secrets.CP_API_URL }}
          CP_API_TOKEN: ${{ secrets.CP_API_TOKEN }}
        run: |
          python3 scripts/ci/verify_consumer_compat.py \
            --module-id ${{ matrix.module_id }} \
            --cp-api-url "$CP_API_URL" \
            --cp-api-token "$CP_API_TOKEN"

  gate_b_summary:
    needs: gate_b_per_module
    if: always()
    runs-on: ubuntu-latest
    steps:
      - name: Summarize
        run: |
          if [ "${{ needs.gate_b_per_module.result }}" = "success" ]; then
            echo "✅ Gate-B PASS for all affected modules"
          else
            echo "::error::Gate-B FAIL — see per-module job logs"
            exit 1
          fi
```

## 3. Required CI helper scripts (to be authored in Phase 7)

| Script | Purpose |
|---|---|
| `scripts/ci/validate_module_contract.py` | Validate YAML against 15-field template (§MOD-3 amended) |
| `scripts/ci/verify_rollout_sla.py` | Assert SHADOW + CANARY each ≥ 72h per audit |
| `scripts/ci/verify_no_alerts_during_rollout.py` | Query obs_metrics alert history for rollout window |
| `scripts/ci/verify_rollback_rehearsal.py` | Verify `rollback_surface.rollback_rehearsal` date within past 90 days |
| `scripts/ci/verify_rollback_p95.py` | Assert empirical p95 ≤ declared SLA (against recorded rehearsal logs) |
| `scripts/ci/verify_consumer_compat.py` | Resolve dependents via CP registry + assert contract_version ranges |

These scripts are out-of-scope for MOD-3 (which is doc-only); they are Phase 7 dependencies.

## 4. Secrets required

| Secret | Use | Setup |
|---|---|---|
| `CP_API_URL` | Internal CP service URL (e.g. `http://100.123.49.102:8773`) | `gh secret set CP_API_URL --body 'http://100.123.49.102:8773'` |
| `CP_API_TOKEN` | CI read-only token for CP queries | Generated post-Phase-7; service-account scope |

These secrets are NOT created in MOD-3 (CP doesn't exist yet). Workflow spec assumes they will be provisioned before Phase 7 starts.

## 5. Branch protection rules (repository settings, out-of-YAML)

Apply via `gh api` when Phase 7 nears:

```bash
gh api repos/M116cj/j13-ops/branches/main/protection -X PUT \
  -F required_status_checks[strict]=true \
  -F required_status_checks[contexts][]="Module Migration Gate (Gate-B) / gate_b_summary" \
  -F enforce_admins=true \
  -F required_linear_history=true \
  -F required_signatures=true
```

`enforce_admins=true` blocks even j13 from merging without passing Gate-B (j13 can disable via explicit override per execution_gate §6).

## 6. Label role (additive, non-gating)

Labels remain for human readability:
- `module-migration/<module_id>` — documentation
- `phase-7-kickoff` — marks the first Phase 7 PR
- `blocked-by-gate-a` — informational

**None of these labels are gating**. Path patterns are the only trigger. Per R1a-F1 resolution.

## 7. Q1 adversarial on the spec itself

| Dim | Assertion | Verdict |
|---|---|---|
| Input boundary | Workflow runs on PR + push events (both covered); paths cover module code + contract YAML | PASS |
| Silent failure | `strategy.fail-fast: false` ensures all per-module checks report independently; summary job fails loudly if any fail | PASS |
| External dep | CP_API_URL / CP_API_TOKEN secrets enumerated; graceful fail if unset (via curl -f) | PASS |
| Concurrency | `concurrency.cancel-in-progress: false` — running checks complete even on force-push | PASS |
| Scope creep | Workflow spec only; helper scripts flagged as Phase 7 deps | PASS |

## 8. Resolution status

| Finding | Status |
|---|---|
| R1a-F1 CRITICAL (label bypass) | **RESOLVED** — path-based trigger, label is additive |
| R1a-F2 HIGH (local hook bypass) | **RESOLVED** — server-side workflow is ground truth |

## 9. Label per 0-4 rule 10

- §2 full workflow: **PROBABLE** (design; VERIFIED when workflow lands)
- §3 helper scripts: **INCONCLUSIVE** (out-of-scope for MOD-3)
- §5 branch protection: **PROBABLE** (standard GitHub config)
- §7 Q1: **VERIFIED** (addressed 5 adversarial dims)
