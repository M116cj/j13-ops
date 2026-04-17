"""Hypothesis lifecycle manager for Calcifer/Markl supervisors.

States: GENERATED → TESTING → CONFIRMED / REJECTED / SHELVED → EXPIRED
- CONFIRMED findings persist in findings.jsonl
- REJECTED hypotheses are tracked to avoid re-testing
- SHELVED after 3 inconclusive tests
- EXPIRED after TTL (default 72h for findings, 24h for rejected)
- Auto-skill: 3+ similar confirmed findings → generate runbook
"""
import os, json, hashlib, time
from datetime import datetime, timezone

REJECTED_TTL_H = 24
FINDING_TTL_H = 72
SHELVE_AFTER = 3
SKILL_AFTER = 3

class HypothesisManager:
    def __init__(self, base_dir):
        self.base_dir = base_dir
        self.hyp_file = os.path.join(base_dir, "hypotheses.jsonl")
        self.findings_file = os.path.join(base_dir, "findings.jsonl")
        self.skills_dir = os.path.join(base_dir, "skills")
        os.makedirs(self.skills_dir, exist_ok=True)
        self._rejected_cache = self._load_rejected()

    def _hash(self, text):
        return hashlib.md5(text.encode()).hexdigest()[:12]

    def _now(self):
        return datetime.now(timezone.utc).isoformat()

    def _load_rejected(self):
        """Load recently rejected hypothesis hashes to avoid re-testing."""
        rejected = set()
        if not os.path.exists(self.hyp_file):
            return rejected
        cutoff = time.time() - REJECTED_TTL_H * 3600
        for line in open(self.hyp_file):
            try:
                h = json.loads(line)
                if h.get("status") == "REJECTED" and h.get("epoch", 0) > cutoff:
                    rejected.add(h.get("hash", ""))
            except (json.JSONDecodeError, KeyError):
                continue
        return rejected

    def is_already_tested(self, hypothesis_text):
        """Check if this hypothesis was recently rejected."""
        return self._hash(hypothesis_text) in self._rejected_cache

    def record(self, hypothesis_text, status, evaluation=None):
        """Record a hypothesis outcome."""
        h = {
            "hash": self._hash(hypothesis_text),
            "hypothesis": hypothesis_text[:200],
            "status": status,
            "ts": self._now(),
            "epoch": time.time(),
        }
        if evaluation:
            h["evaluation"] = evaluation
        with open(self.hyp_file, "a") as f:
            f.write(json.dumps(h) + "\n")
        if status == "REJECTED":
            self._rejected_cache.add(h["hash"])

    def record_finding(self, finding):
        """Persist a confirmed finding and check for auto-skill trigger."""
        with open(self.findings_file, "a") as f:
            f.write(json.dumps(finding) + "\n")
        self._check_auto_skill(finding)

    def _check_auto_skill(self, finding):
        """If 3+ similar findings exist, generate a skill/runbook."""
        if not os.path.exists(self.findings_file):
            return
        keyword = finding.get("insight", "")[:50]
        similar = 0
        for line in open(self.findings_file):
            try:
                f = json.loads(line)
                if keyword[:20] in f.get("insight", ""):
                    similar += 1
            except (json.JSONDecodeError, KeyError):
                continue
        if similar >= SKILL_AFTER:
            self._generate_skill(finding)

    def _generate_skill(self, finding):
        """Auto-generate a runbook skill from repeated findings."""
        name = self._hash(finding.get("insight", "unknown"))
        skill_path = os.path.join(self.skills_dir, f"skill_{name}.md")
        if os.path.exists(skill_path):
            return
        content = f"""# Auto-Generated Skill: {finding.get('insight', 'Unknown')[:80]}
## Generated: {self._now()}
## Source: {finding.get('cycle', '?')} cycles of confirmed findings

### What
{finding.get('insight', 'N/A')}

### Recommendation
{finding.get('recommendation', 'N/A')}

### Verification
Run the relevant tool and check for the pattern described above.
"""
        with open(skill_path, "w") as f:
            f.write(content)

    def expire_old(self):
        """Remove expired entries from hypothesis file."""
        if not os.path.exists(self.hyp_file):
            return 0
        cutoff = time.time() - max(REJECTED_TTL_H, FINDING_TTL_H) * 3600
        lines = open(self.hyp_file).readlines()
        kept = []
        removed = 0
        for line in lines:
            try:
                h = json.loads(line)
                if h.get("epoch", 0) > cutoff:
                    kept.append(line)
                else:
                    removed += 1
            except (json.JSONDecodeError, KeyError):
                kept.append(line)
        if removed > 0:
            with open(self.hyp_file, "w") as f:
                f.writelines(kept)
        return removed
