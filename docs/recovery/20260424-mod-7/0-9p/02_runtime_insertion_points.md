# 02 — Runtime Insertion Points

唯一 runtime SHA 變動：`zangetsu/services/arena_pipeline.py`，授權
為 EXPLAINED_TRACE_ONLY（metadata-only）。

## 1. arena_pipeline.py — passport literal

**File**：`zangetsu/services/arena_pipeline.py`
**Location**：A1 admit branch，緊鄰 V10 passport 構造處（既有
`passport = { "arena1": { ... } }` literal）。

Diff（concept）：

```diff
@@ V10 passport block @@
+            # ── 0-9P attribution closure ──
+            # Persist generation_profile_id / fingerprint into
+            # passport.arena1 so A2/A3 telemetry can attribute Arena
+            # outcomes to the original A1 generation profile.
+            try:
+                _passport_profile_id = (
+                    _gen_profile_identity.get("profile_id")
+                    or _UNKNOWN_PROFILE_ID
+                )
+                _passport_profile_fingerprint = (
+                    _gen_profile_identity.get("profile_fingerprint")
+                    or _UNAVAILABLE_FINGERPRINT
+                )
+            except Exception:
+                _passport_profile_id = _UNKNOWN_PROFILE_ID
+                _passport_profile_fingerprint = _UNAVAILABLE_FINGERPRINT
             passport = {
                 "arena1": {
                     "alpha_expression": alpha_result.to_dict(),
                     ...
                     "cooldown": COOLDOWN,
+                    # 0-9P attribution closure (additive, metadata-only).
+                    "generation_profile_id": _passport_profile_id,
+                    "generation_profile_fingerprint": _passport_profile_fingerprint,
                 },
                 ...
             }
```

額外修改：**0**（僅上述 metadata 寫入）。

## 2. generation_profile_identity.py — resolve_attribution_chain

**File**：`zangetsu/services/generation_profile_identity.py`
**Location**：模組末，`safe_resolve_profile_identity` 之後。

```diff
+def resolve_attribution_chain(
+    passport: Optional[Mapping[str, Any]] = None,
+    *,
+    orchestrator_profile_id: Optional[str] = None,
+    orchestrator_profile_fingerprint: Optional[str] = None,
+) -> dict:
+    """4-level precedence chain helper. Never raises."""
+    ...
```

純 Python 工具函數；不 IO；不引入 runtime 副作用。

## 3. arena23_orchestrator.py — 不變

P7-PR4B 既有 `_p7pr4b_resolve_passport_profile` 已先讀
`passport.arena1.generation_profile_id`（見既有 source）：

```python
def _p7pr4b_resolve_passport_profile(passport):
    a1 = passport.get("arena1") or {}
    pid = (
        a1.get("generation_profile_id")             # ← 0-9P 後實際命中
        or passport.get("generation_profile_id")
    )
    pfp = (
        a1.get("generation_profile_fingerprint")
        or passport.get("generation_profile_fingerprint")
    )
    ...
```

orchestrator main loop 接著補 orchestrator consumer profile fallback：

```python
if _pid_a3 == _P7PR4B_UNKNOWN_PROFILE_ID:
    _pid_a3 = _p7pr4b_consumer_profile.get("profile_id", _P7PR4B_UNKNOWN_PROFILE_ID)
```

整條精準對應 §3 attribution precedence。**0 行 orchestrator 變動。**

## 4. arena45_orchestrator.py — 不變

A4/A5 不在 sparse-candidate / SIGNAL_TOO_SPARSE 觀察鏈上；不需動。

## 5. Files NOT modified

- `zangetsu/services/arena_pass_rate_telemetry.py`
- `zangetsu/services/arena_gates.py`
- `zangetsu/services/arena_rejection_taxonomy.py`
- `zangetsu/services/feedback_decision_record.py`
- `zangetsu/services/feedback_budget_allocator.py`
- `zangetsu/services/generation_profile_metrics.py`
- `zangetsu/config/settings.py`
- `zangetsu/engine/components/*.py`
- `zangetsu/live/*.py`

## 6. Controlled-diff classification

- `config.arena_pipeline_sha` → **EXPLAINED_TRACE_ONLY**
  (`--authorize-trace-only config.arena_pipeline_sha`)，metadata-only
  passport 持久化。
- 其他 5 條 CODE_FROZEN runtime SHAs → **ZERO_DIFF**：
  `zangetsu_settings_sha`、`arena23_orchestrator_sha`、
  `arena45_orchestrator_sha`、`calcifer_supervisor_sha`、
  `zangetsu_outcome_sha`。
- helper / docs / tests → EXPLAINED。
- 0 forbidden。
