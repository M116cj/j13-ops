Loaded cached credentials.
Registering notification handlers for server 'notebooklm-writer'. Capabilities: { tools: {} }
Server 'notebooklm-writer' has tools but did not declare 'listChanged' capability. Listening anyway for robustness...
Registering notification handlers for server 'notebooklm'. Capabilities: { logging: {}, completions: {}, prompts: {}, resources: {}, tools: {} }
Server 'notebooklm' has tools but did not declare 'listChanged' capability. Listening anyway for robustness...
Server 'notebooklm' has resources but did not declare 'listChanged' capability. Listening anyway for robustness...
Server 'notebooklm' has prompts but did not declare 'listChanged' capability. Listening anyway for robustness...
Scheduling MCP context refresh...
Executing MCP context refresh...
MCP context refresh complete.
### FINDING B1: Admin-Bypass Nullifies Security Root (HIGH)
- **Severity**: HIGH
- **Claim**: `enforce_admins=false` renders GPG enforcement "Security Theater" for the primary actor (j13 PAT). An attacker/rogue process using the admin PAT can still inject unsigned code, bypassing the very audit trail MOD-4 claims to establish.
- **Evidence**: `required_signatures_enforcement_spec.md §1` confirms `enforce_admins: {"enabled": false}` is live. §3.1 explicitly allows admin unsigned pushes.
- **Recommended Delta**: Specify a mandatory transition to `enforce_admins=true` at Phase 7 entry. Require all MOD-5+ commits to be PR-based with human GPG-signed merges.
- **Label**: **VERIFIED**

### FINDING B2: Cache Rate-Limit is Decorative (MEDIUM)
- **Severity**: MEDIUM
- **Claim**: The `cache_lookup` limit (10,000/s) is a "soft metric only," providing no protection against a consumer module entering a tight loop and consuming 100% CPU on the worker thread.
- **Evidence**: `cp_worker_bridge_rate_limit_split.md §2.1` states "enforcement: soft metric only (alert if sustained...)."
- **Recommended Delta**: Upgrade `cache_lookup` to a hard cap (e.g., 20,000/s) with a `circuit_breaker` policy to protect worker availability.
- **Label**: **VERIFIED**

### FINDING B3: Thundering Herd Mitigation is Spec-Only (MEDIUM)
- **Severity**: MEDIUM
- **Claim**: Mitigation for N-worker surge (jitter/single-flight) is relegated to "design intent" rather than a mandatory technical requirement for the bridge.
- **Evidence**: `cp_worker_bridge_rate_limit_split.md §6.3` states "These are implementation details (Phase 7); spec here mentions them as design intent."
- **Recommended Delta**: Move jitter/single-flight from "intent" to "mandatory functional requirement" in the M9 interface spec.
- **Label**: **PROBABLE**

---

### Round-3 HIGH Status

*   **R3a-F8 (required_signatures)**: **REOPENED_AT_DEEPER_LEVEL**. While "live" for non-admins, the admin-bypass for the primary automated actor (j13) reopens the finding as a governance loophole.
*   **R3b-F2 (rate_limit split)**: **CLOSED**. The three-channel semantic split successfully resolves the catastrophic "50k/s REST" math and provides necessary observability.

---

### Mandate Responses

1.  **Admin-Bypass**: `enforce_admins=false` is a **NEW HIGH finding**. It is tolerable for the narrow MOD-4 bootstrap window but becomes a critical vulnerability if it persists into Phase 7.
2.  **Thundering Herd**: The split prevents the "50k/s" scenario, but without mandatory jitter/single-flight, it remains a **paper-tiger** against local CPU spikes.
3.  **Consumer Violation**: A consumer can violate `cache_lookup` at will; the 10,000/s ceiling is **decorative**.
4.  **Governance Matrix**: The 35% LIVE / 65% OTHER distribution is **HONEST** but reveals that 2/3 of the security posture remains aspirational or partial. The missing 5% in the provided sum (95%) suggests minor accounting sloppiness.

**VERDICT_4B = ACCEPT_WITH_AMENDMENTS** (Requires B1-B3 addressed in MOD-5).
