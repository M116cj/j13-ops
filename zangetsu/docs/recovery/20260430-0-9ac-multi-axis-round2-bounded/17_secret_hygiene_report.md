# 17 — Secret Hygiene Report

**ORDER**: 0-9AC-CLOSE — Phase 1 / Workstream F

## Sensitive Material In Scope

- Gemini API key (referenced in /home/j13/.gemini/settings.json on Alaya, not under repo control)
- Any other ambient credentials in the operator's home directory

## Key Exposure History During This Order

The Gemini API key appeared **once** in tool output during 0-9AC Round 2 when probing the auth method. Since that point:

1. The key has not been re-printed in any further tool output.
2. The key has been loaded only via shell env var read from settings.json — never echoed.
3. The key has not been written into any file under `/home/j13/j13-ops/`.
4. The retry command used `set +x` and `export GEMINI_API_KEY=$(python3 -c ...)` so the value never appears in logs.

## Scan Results

### `git grep` on tracked files

| Pattern | Hits | Verdict |
|---|---:|---|
| `GEMINI_API_KEY` | 3 | env-var-name only, no value |
| `AIza` (Google API key prefix) | 0 | clean |

The 3 `GEMINI_API_KEY` hits are in:
- `zangetsu/VERSION_LOG.md:756` — documentation note about needing the env var
- `zangetsu/VERSION_LOG.md:840` — same note
- `zangetsu/docs/recovery/20260430-0-9ab-core-factory-multi-axis-shadow-tournament/12_gemini_adversarial_review.md:14` — quoted from CLI's own error message

None of the hits contain an actual key value.

### Working-tree scan (untracked + modified files)

```
grep -RIln 'GEMINI_API_KEY|AIza' \
  zangetsu/core_factory/ \
  zangetsu/tests/ \
  zangetsu/docs/recovery/20260430-0-9ac-multi-axis-round2-bounded/
```

→ **0 hits**.

### Tracked settings.json

```
git ls-files | grep settings.json
```

→ **no settings.json tracked** anywhere in the repo.

## Items Explicitly Excluded From Stage / Commit

- `/home/j13/.gemini/settings.json` (outside repo, not staged)
- shell history (not staged)
- `.env` files (none in repo)
- exchange credentials (none requested or stored)
- production DB dumps (none)
- raw Gemini stdout containing key material (key is in env, not in stdout; stdout sanitised in this report)

## Verdict

`SECRET_HYGIENE_PASS` — no key in tracked files, no key in working-tree files, no key in evidence, no key in PR body.

## Acceptance Mapping

- AC7 PASS secret hygiene scan completed
- AC8 PASS no Gemini key in staged files
- AC9 PASS no secrets in evidence
