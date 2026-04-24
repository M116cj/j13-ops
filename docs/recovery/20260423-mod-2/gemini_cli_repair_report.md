# Gemini CLI Repair Report — MOD-2 Phase 3a

**Order**: `/home/j13/claude-inbox/0-3` Phase 3 first deliverable
**Executed**: 2026-04-23T03:59Z → 04:02Z
**Author**: Claude
**Status**: **VERIFIED repaired** — Gemini CLI now executes successfully against real prompts.

---

## 1. Root cause analysis

### Symptom (from 0-1 Phase B failure)
```
Keychain initialization encountered an error: Cannot find module '../build/Release/keytar.node'
...
Error getting folder structure for /Users/a13: EPERM: scandir '/Users/a13/.Trash'
```

Gemini initialized the shell + MCP context, then exited silently without emitting any LLM response content.

### Discovered root causes (2 independent)

**Cause-1: keytar native binding missing**
- Path: `/opt/homebrew/Cellar/gemini-cli/0.35.3/libexec/lib/node_modules/@google/gemini-cli/node_modules/keytar/build/Release/`
- State: directory did NOT exist; `keytar.node` was never built
- Trigger: Homebrew's Node 25.8.2 installed on Mac after gemini-cli installation; keytar's C++ addon was not rebuilt against the new Node ABI
- Impact: Keychain init fails, degrades to FileKeychain fallback (non-fatal, emits warning)

**Cause-2: `.Trash` EPERM on home dir scan**
- Path: `/Users/a13/.Trash`
- State: macOS protects `.Trash` from non-privileged `readdir`
- Trigger: Gemini's `getFolderStructure` recursively walks CWD (`$PWD`) on init; if CWD is `/Users/a13/`, it attempts `readdir` on `.Trash` → EPERM
- Impact: Looked fatal in 0-1 attempt; caused silent exit after the failure propagated up async chain

## 2. Repair steps executed (VERIFIED)

### 2.1 Rebuild keytar native binding
```bash
cd /opt/homebrew/Cellar/gemini-cli/0.35.3/libexec/lib/node_modules/@google/gemini-cli/node_modules/keytar
/opt/homebrew/bin/npm rebuild
# Output: "rebuilt dependencies successfully"

ls -la build/Release/
# Output: keytar.node (99528 bytes, Feb 17 2022 — binding date)
```

### 2.2 Workaround for `.Trash` EPERM
Run Gemini from a CWD that doesn't contain `.Trash`:
```bash
cd /tmp && /opt/homebrew/bin/gemini -p "…"
```

No permanent fix needed — the `.Trash` scan is a cosmetic folder-context gather, not a functional dependency.

## 3. Validation

### 3.1 Smoke test
```bash
$ cd /tmp && /opt/homebrew/bin/gemini -p "Reply with exactly: GEMINI_OK"
Loaded cached credentials.
... (MCP init messages) ...
GEMINI_OK
```

VERDICT: Gemini CLI functional from non-home CWD.

### 3.2 Real-load test (MOD-2 Phase 3b Round-1 Gate)
Executed `gemini -p "$(head -99999 gate_combined.txt)"` (11.7 KB combined prompt).
- exit=0
- 3415 bytes of structured response
- 5 FINDING-N blocks
- Terminal `VERDICT = ACCEPT_WITH_AMENDMENTS`

VERDICT: Gemini functional for real adversarial review workloads.

## 4. Remaining workflow constraint

Gemini invocation must happen from a CWD that doesn't contain `.Trash` (i.e., NOT `/Users/a13/`). Standard practice going forward:
```bash
cd /tmp && gemini -p "..."
# or
cd <project-dir> && gemini -p "..."
```

## 5. Permanent fix options (not executed — optional for j13)

1. **Grant Terminal + Claude Code Full Disk Access** via System Settings → Privacy & Security → Full Disk Access → add Terminal.app and/or Claude Code binary. This would clear the `.Trash` EPERM.
2. **Modify `gemini-akasha` wrapper** at `/Users/a13/.local/bin/gemini-akasha` to `cd /tmp` before invoking `/opt/homebrew/bin/gemini`. Fire-and-forget fix.

Neither is necessary for current operation.

## 6. Non-negotiable rules compliance

| Rule | Evidence |
|---|---|
| 1. No silent production mutation | ✅ — Mac-side toolchain only, no Alaya change |
| 8. No broad refactor | ✅ — `npm rebuild` is targeted at 1 native binding |

## 7. Exit condition (for Phase 3a)

0-3 §Phase 3 Req 1-2 ("repair Mac Gemini CLI installation" + "verify command execution works") — **MET** per §3.

## 8. Q1 adversarial

| Dim | Verdict |
|---|---|
| Input boundary | PASS — small smoke prompt + real-load MOD-1 review both succeed |
| Silent failure | PASS — exit=0 returned + content written |
| External dep | PASS — Google auth reused cached credentials; no token refresh needed |
| Concurrency | PASS — single invocation |
| Scope creep | PASS — targeted at keytar + CWD; no unrelated changes |
