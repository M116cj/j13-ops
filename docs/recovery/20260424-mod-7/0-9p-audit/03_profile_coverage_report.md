# 03 — Profile Coverage Report (Template)

## 1. Purpose

Standard format for the periodic coverage report that operators emit
by running `audit(events)` over a recent log window. The fields
below are the **canonical** report shape — downstream dashboards
should consume these by name.

## 2. Header

```
Audit version:        0-9P-AUDIT
Window start (UTC):   {iso}
Window end (UTC):     {iso}
Source:               <log path / db query>
Total events:         <n>
A1 / A2 / A3 split:   <a1> / <a2> / <a3>
```

## 3. Source classification

| Class | Count | Rate |
| --- | --- | --- |
| `passport_identity_count` | n | rate |
| `orchestrator_fallback_count` | n | rate |
| `unknown_profile_count` | n | rate |
| `unavailable_fingerprint_count` | n | rate |

## 4. Cross-stage alignment

| Pair | Match count |
| --- | --- |
| A1 → A2 | n |
| A2 → A3 | n |

| Mismatch | Count | Rate |
| --- | --- | --- |
| Total | n | rate |

## 5. Per-profile breakdown

For each `profile_id` (sorted descending by total events):

| Profile id | A1 events | A2 events | A3 events | sparse_rate | oos_rate | deployable |
| --- | --- | --- | --- | --- | --- | --- |
| gp_xxxx... | n | n | n | rate | rate | n or - |

## 6. Verdict

```
Verdict:              GREEN / YELLOW / RED
Reasons:              <list>
Blocks PR-C consumer? True only when verdict == RED
```

## 7. Recommended action

| Verdict | Action |
| --- | --- |
| GREEN | Proceed to PR-C / 0-9R-IMPL-DRY |
| YELLOW | Document the offending rate; proceed only if a non-blocking explanation exists; revisit if rate climbs |
| RED | STOP. Investigate attribution gap (passport persistence, orchestrator fallback usage, taxonomy completeness). Re-run audit after fix. |
