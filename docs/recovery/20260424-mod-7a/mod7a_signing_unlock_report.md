# MOD-7A Signing Infrastructure Unlock Report

- **Order**: Team Order 0-9A — Option A only (Alaya-specific SSH signing key)
- **Executed**: 2026-04-24 03:02Z → 03:13Z
- **Outcome**: SUCCESS — Alaya can now produce GitHub-verified signed commits.

## 1. Public key fingerprint

| Field | Value |
|---|---|
| Type | ed25519 |
| Comment | `alaya-j13-signing-20260424` |
| SHA256 | `SHA256:jOIkKEJ3FntF2SIZyThPGVgZdd+sMxeii6Vjsj90+jk` |
| Private key path | `/home/j13/.ssh/id_ed25519_signing` (mode 0600) |
| Public key path | `/home/j13/.ssh/id_ed25519_signing.pub` (mode 0644) |
| Passphrase | none (agent-driven; key file permission is the access control) |
| Dedicated purpose | signing only — NOT reused from any deploy/login key |
| GitHub registration | Signing Key type, registered to user M116cj on 2026-04-24 |

## 2. Git signing config result

Global config (`~/.gitconfig`):
```
commit.gpgsign        = true
gpg.format            = ssh
gpg.ssh.allowedsignersfile = /home/j13/.config/git/allowed_signers
user.email            = 100402507+M116cj@users.noreply.github.com
user.name             = j13
user.signingkey       = /home/j13/.ssh/id_ed25519_signing.pub
```

Repo-local `.git/config` (j13-ops): pre-existing `user.email = j13@alaya` was **unset** so global noreply email takes effect. No other local override remains.

`allowed_signers` file:
```
100402507+M116cj@users.noreply.github.com ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIC9X0NmbhvSTWxTvaW6k/MLzUp3OalGlmWQTtflOZa8v alaya-j13-signing-20260424
```

## 3. Probe commit hash

| Stage | SHA | Note |
|---|---|---|
| Initial commit (before email fix) | `c470daad` | local sig GOOD but author/committer = `j13@alaya` (local override) |
| Amended commit (after `user.email` local unset + `--reset-author`) | **`a5ad24fa2065b61b15ccc79b24031b7a1e9db721`** | **final probe commit** |
| Branch | `phase-7/signing-probe` (created from `origin/main` @ fd7cc34e, now deleted) |
| File touched | `.signing-probe` (1 insertion, 1 file) — scope: repo root trivial marker, NOT touching alpha/arena/threshold/engine |

Local verification (`git log --show-signature -1`):
```
commit a5ad24fa2065b61b15ccc79b24031b7a1e9db721
Good "git" signature for 100402507+M116cj@users.noreply.github.com
   with ED25519 key SHA256:jOIkKEJ3FntF2SIZyThPGVgZdd+sMxeii6Vjsj90+jk
Author:    j13 <100402507+M116cj@users.noreply.github.com>
Committer: j13 <100402507+M116cj@users.noreply.github.com>
```

## 4. GitHub verification result

From `gh api /repos/M116cj/j13-ops/commits/a5ad24fa...`:

```json
{
  "verified": true,
  "verified_at": "2026-04-24T03:12:27Z",
  "reason": "valid",
  "signature": "-----BEGIN SSH SIGNATURE-----\nU1NIU0lHAAAAAQAAADMAAAALc3NoLWVkMjU1MTkAAAAgL1fQ2ZuG9JNbFO9pbqT8wvNSnc5qUaWZZBO1+U5lry8A...\n-----END SSH SIGNATURE-----",
  "payload": "tree d7d721bb...\nparent fd7cc34e...\nauthor j13 <100402507+M116cj@users.noreply.github.com> 1777000334 +0000\ncommitter j13 <100402507+M116cj@users.noreply.github.com> 1777000334 +0000\n\ntest: signing probe for MOD-7A (should be SSH-signed)\n"
}
```

**verified = true** + **reason = valid** → this commit would satisfy `required_signatures=true` on merge to main.

## 5. Probe branch cleanup status

| Check | Result |
|---|---|
| `git push origin --delete phase-7/signing-probe` | deleted (`[deleted] phase-7/signing-probe`) |
| `gh api /repos/M116cj/j13-ops/git/refs/heads/phase-7%2Fsigning-probe` | **404 Not Found** (confirmed deletion) |
| Local `git branch -D phase-7/signing-probe` | deleted (was a5ad24fa) |
| Local HEAD restored to main | `da66c296` (MOD-6 final, unchanged) |

## 6. Branch protection invariants (unchanged)

```json
{"enforce_admins": true, "linear": true, "req_sig": true}
```

MOD-6 governance is NOT weakened. No admin bypass, no signature requirement disable, no linear-history disable.

## 7. Final go/no-go for resuming MOD-7

```
Signing confirmation (0-9 §10):   PASS (verified=true, reason=valid)
PR flow available:                YES (pushing signed commit to feature branch succeeded)
Branch protection intact:         YES (enforce_admins=true, req_sig=true, linear=true preserved)
Main HEAD:                        da66c296 (MOD-6 final, untouched)
Scope compliance:                 PASS (only .signing-probe touched; no runtime file changed)
Probe cleanup:                    CLEAN (remote 404, local deleted, tracking branch gone)

RESUMING MOD-7:                   GO (signing blocker resolved)

Scope of this GO:                 Permits a future authorized order to resume MOD-7
                                  P7-PR1 execution under Phase 7 operating law.

NOT AUTHORIZED by this order:     - Starting P7-PR1
                                  - Declaring Phase 7 launched
                                  - Committing the MOD-7 kickoff docs to any branch
                                  - Any runtime mutation

Phase 7 status:                   STILL "LEGAL but NOT LAUNCHED".
                                  Phase 7 may be opened by separate authorized order.
```

## 8. Residual risks

- Private key `id_ed25519_signing` is passphrase-less (required for agent-driven signing). Compensating control: file mode 0600, key is dedicated (not reused), GitHub registration is revocable by j13 at any time.
- `user.email` global change propagates to all future commits on Alaya (including unrelated repos). Acceptable: noreply email is the correct identity for GitHub-facing commits; no private email leakage risk.
- `.signing-probe` file no longer exists (removed with probe branch deletion). No residue in main.

## 9. Verdict

MOD-7A SUCCESS. Alaya signing infrastructure is LIVE. STOP #1 from MOD-7 is RESOLVED. MOD-7 may be resumed by a separate authorized order.
