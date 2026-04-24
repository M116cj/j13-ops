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
### ADVERSARIAL REVIEW: ZANGETSU MOD-3 AMENDMENTS

The MOD-3 amendments transition several "honor-system" controls to mechanical ones, but introduce significant implementation gaps and procedural "debt" that leave the system vulnerable to sophisticated bypasses.

---

- **FINDING-1: CLOSED (R1a-F1)**. Severity: **NONE**. Claim: Path-based triggers (§5.2) eliminate the label-omission bypass. Evidence: §5.2 explicitly lists module and layer paths as un-bypassable triggers. **VERIFIED**.
- **FINDING-2: CLOSED (R1a-F2)**. Severity: **NONE**. Claim: Server-side GHA (§5.1) prevents `--no-verify` local bypass. Evidence: §5.1 mandates GHA as authoritative. **VERIFIED**.
- **FINDING-3: UNCHANGED (R1a-F3)**. Severity: **MEDIUM**. Claim: Quiescence loophole remains; the refusal to reset the clock (§3 A.2) is a "velocity-first" delaying tactic. Evidence: §3 A.2 explicitly admits the loophole is preserved to avoid resetting the 7-day timer. **VERIFIED**.
- **FINDING-4: CLOSED (R1a-F4)**. Severity: **NONE**. Claim: Rollback p95 is now empirical. Evidence: §4 B.2. **VERIFIED**.
- **FINDING-5: CLOSED (R1a-F5)**. Severity: **NONE**. Claim: Override ADR requires GPG identity. Evidence: §6. **VERIFIED**.

---

- **FINDING-6: NEW (Subprocess/Egress Stealth 2.0)**. Severity: **HIGH**. Claim: Field 15 is bypassable via runtime reflection or native extensions. Evidence: `amended_module_contract_template.md §2`. Static CI scans cannot reliably detect network calls from C extensions or obfuscated reflection. Since runtime enforcement (iptables/seccomp) is "out of scope" for MOD-3, Field 15 remains a documentation-only "soft" control. **PROBABLE**.
- **FINDING-7: NEW (Ghost Fixtures)**. Severity: **MEDIUM**. Claim: The 1:1 responsibility-to-fixture check is trivial to spoof. Evidence: `amended_module_contract_template.md §4`. The check only validates filename presence. A contributor can pass by creating empty or `pass`-only files (e.g., `test_route_events.py`). **VERIFIED**.
- **FINDING-8: NEW (Enforcement Vacuum)**. Severity: **HIGH**. Claim: GPG requirements are stated but explicitly NOT enforced in MOD-3. Evidence: §5.4. Branch protection `required_signatures=true` is deferred to "Phase 7". This allows un-signed or improperly signed overrides during the critical Phase 6 transition. **VERIFIED**.
- **FINDING-9: NEW (Trigger Path Omission)**. Severity: **MEDIUM**. Claim: Gate-B triggers are not exhaustive. Evidence: §5.2. Paths like `zangetsu/src/utils/**` or `zangetsu/src/infra/**` are omitted. A contributor can migrate logic into these directories to avoid Gate-B triggers entirely. **VERIFIED**.

---

**VERDICT = ACCEPT_WITH_AMENDMENTS**

**MANDATORY AMENDMENTS:**
1. **Delta-1**: Tighten §5.2 triggers to include all of `zangetsu/src/**` or implement an "allow-list" for non-gate paths.
2. **Delta-2**: Activate `required_signatures=true` IMMEDIATELY upon MOD-3 acceptance.
3. **Delta-3**: Update §4 B.1 to require fixture content validation (e.g., minimum LOC or AST check for test logic).
4. **Delta-4**: Reset the Gate-A.2 clock if any non-documentation commit (including fix/refactor) is merged. Integrity > Velocity.
