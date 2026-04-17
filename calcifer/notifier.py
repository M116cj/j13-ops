"""AKASHA write-back + Telegram notification for agent findings.

V9 Final (2026-04-17): confidence + source + memory_relations + auto-link
+ accurate return semantics + optional LLM confidence classifier
+ contradicts detection (semantic opposition heuristic).

Shared by Calcifer (Alaya gemma4:e4b) and Markl (Mac gemma3:12b).
"""
import json, urllib.request, os, threading, re

AKASHA_URL = "http://100.123.49.102:8769"
TELEGRAM_TOKEN = os.environ.get("TG_BOT_TOKEN", "8237499581:AAFfSngYTSmsmVHPCMMFw0g7kkXpOj5kDFU")
TELEGRAM_CHAT = os.environ.get("TG_CHAT_ID", "5252897787")
TELEGRAM_THREAD = os.environ.get("TG_THREAD_ID", "")

# Per-agent default Ollama (auto-detected at runtime)
OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
LLM_CONFIDENCE_MODEL = os.environ.get("LLM_CONFIDENCE_MODEL", "")  # empty = disabled
LLM_CONFIDENCE_TIMEOUT = int(os.environ.get("LLM_CONFIDENCE_TIMEOUT", "5"))

CONFIDENCE_MAP = {
    "high": "EXTRACTED", "critical": "EXTRACTED",
    "medium": "INFERRED", "warning": "INFERRED",
    "low": "AMBIGUOUS", "info": "AMBIGUOUS",
}

# In-memory cache: (project, agent, indicator) → most recent (chunk_id, content_summary)
_recent_findings = {}
_cache_lock = threading.Lock()


def _akasha_confidence(severity):
    return CONFIDENCE_MAP.get((severity or "").lower(), "INFERRED")


def llm_classify_confidence(content: str, severity_fallback: str = "info") -> str:
    """V9: LLM-based confidence override. Returns EXTRACTED/INFERRED/AMBIGUOUS.
    Uses local Ollama if LLM_CONFIDENCE_MODEL env is set, else falls back to severity map."""
    if not LLM_CONFIDENCE_MODEL:
        return _akasha_confidence(severity_fallback)
    prompt = (
        "Classify this finding's confidence in ONE word: EXTRACTED (factual, observed), "
        "INFERRED (reasonable hypothesis from data), or AMBIGUOUS (speculative, weak evidence).\n\n"
        f"FINDING: {content[:500]}\n\nANSWER (one word only):"
    )
    body = json.dumps({
        "model": LLM_CONFIDENCE_MODEL, "prompt": prompt, "stream": False,
        "options": {"num_predict": 5, "temperature": 0.1},
    }).encode()
    try:
        req = urllib.request.Request(
            f"{OLLAMA_HOST}/api/generate", data=body,
            headers={"Content-Type": "application/json"},
        )
        resp = urllib.request.urlopen(req, timeout=LLM_CONFIDENCE_TIMEOUT)
        text = json.loads(resp.read()).get("response", "").strip().upper()
        # Match first valid keyword
        for label in ("EXTRACTED", "INFERRED", "AMBIGUOUS"):
            if label in text:
                return label
    except Exception:
        pass
    return _akasha_confidence(severity_fallback)


def _detect_contradicts(new_content: str, old_content: str) -> bool:
    """Heuristic: lexical opposition + resolution keywords. True if new content contradicts old.

    Triggers if:
    1. New content has resolution keyword (resolved/recovered/stabilized/no longer)
    2. Antonym pair appears across new/old content
    """
    n = (new_content or "").lower()
    o = (old_content or "").lower()
    # Resolution keywords always indicate contradicts past concern
    resolution_kw = ("resolved", "recovered", "stabilized", "back to normal", "no longer")
    if any(k in n for k in resolution_kw):
        return True
    contrast_pairs = [
        ("resolved", "broken"), ("fixed", "broken"),
        ("active", "inactive"), ("running", "stopped"),
        ("success", "fail"), ("succeeded", "failed"),
        ("positive", "negative"),
        ("healthy", "unhealthy"), ("ok", "error"),
        ("connected", "disconnected"),
        ("increased", "decreased"), ("rising", "falling"),
        ("rising", "decreased"), ("falling", "increased"),
        ("growth", "decreased"), ("growth", "shrunk"),
        ("approved", "rejected"), ("accepted", "denied"),
        ("up", "down"),
    ]
    for a, b in contrast_pairs:
        if (a in n and b in o) or (b in n and a in o):
            return True
    return False


def write_to_akasha_sync(project, agent_name, finding):
    """Sync write returning {chunk_ids, confidence_used}."""
    severity = finding.get("severity", finding.get("confidence", "info"))
    content = (
        f"[{agent_name} finding {finding.get('ts', '?')}] "
        f"{finding.get('insight', 'no insight')} | "
        f"severity={severity} | "
        f"recommendation={finding.get('recommendation', 'none')}"
    )
    # V9: LLM-classified confidence (if model set), else severity map
    confidence_used = (
        llm_classify_confidence(content, severity) if LLM_CONFIDENCE_MODEL
        else _akasha_confidence(severity)
    )
    body = json.dumps({
        "project": project, "segment": "agent_findings",
        "content": content,
        "tags": [agent_name, "finding", str(severity)],
        "confidence": confidence_used,
        "source": f"{agent_name}.notifier:{finding.get('ts', 'unknown')}",
    }).encode()
    req = urllib.request.Request(
        f"{AKASHA_URL}/memory/sync", data=body,
        headers={"Content-Type": "application/json"},
    )
    try:
        resp = urllib.request.urlopen(req, timeout=15)
        result = json.loads(resp.read())
        if result.get("status") == "inserted":
            return {"chunk_ids": result.get("chunk_ids", []),
                    "confidence_used": confidence_used,
                    "content": content}
    except Exception:
        pass
    return None


def write_to_akasha(project, agent_name, finding):
    """Legacy async (returns bool)."""
    severity = finding.get("severity", finding.get("confidence", "info"))
    body = json.dumps({
        "project": project, "segment": "agent_findings",
        "content": (
            f"[{agent_name} finding {finding.get('ts', '?')}] "
            f"{finding.get('insight', 'no insight')} | "
            f"severity={severity} | "
            f"recommendation={finding.get('recommendation', 'none')}"
        ),
        "tags": [agent_name, "finding", str(severity)],
        "confidence": _akasha_confidence(severity),
        "source": f"{agent_name}.notifier:{finding.get('ts', 'unknown')}",
    }).encode()
    req = urllib.request.Request(
        f"{AKASHA_URL}/memory", data=body,
        headers={"Content-Type": "application/json"},
    )
    try:
        resp = urllib.request.urlopen(req, timeout=10)
        return json.loads(resp.read()).get("status") == "accepted"
    except Exception:
        return False


def create_memory_relation(from_id, to_id, relation, confidence="INFERRED"):
    if relation not in {"supersedes", "contradicts", "derived_from", "refines", "references"}:
        return False
    body = json.dumps({
        "from_memory_id": int(from_id), "to_memory_id": int(to_id),
        "relation": relation, "confidence": confidence,
    }).encode()
    req = urllib.request.Request(
        f"{AKASHA_URL}/relations", data=body,
        headers={"Content-Type": "application/json"},
    )
    try:
        resp = urllib.request.urlopen(req, timeout=10)
        return json.loads(resp.read()).get("status") == "created"
    except Exception:
        return False


def notify_telegram(agent_name, finding):
    if not TELEGRAM_TOKEN:
        return False
    severity = finding.get("severity", finding.get("confidence", "info"))
    if severity not in ("critical", "warning", "high", "medium"):
        return None  # not eligible (different from failure)
    text = (
        f"🔔 *{agent_name.upper()} FINDING*\n"
        f"Severity: {severity}\n"
        f"Insight: {finding.get('insight', 'N/A')}\n"
        f"Recommendation: {finding.get('recommendation', 'N/A')}"
    )
    body = json.dumps({
        "chat_id": TELEGRAM_CHAT, "text": text, "parse_mode": "Markdown",
        **({"message_thread_id": int(TELEGRAM_THREAD)} if TELEGRAM_THREAD else {}),
    }).encode()
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
        data=body, headers={"Content-Type": "application/json"},
    )
    try:
        urllib.request.urlopen(req, timeout=10)
        return True
    except Exception:
        return False


def process_finding(project, agent_name, finding):
    """V9 full flow: sync write + LLM confidence + auto-link (refines/contradicts) + Telegram.

    Returns dict with accurate per-stage status:
    - akasha:        True/False (chunk inserted)
    - chunk_ids:     [int] inserted IDs
    - confidence:    str (EXTRACTED/INFERRED/AMBIGUOUS)
    - telegram:      True (sent) / False (failed) / None (not eligible)
    - relation:      None or {type, from, to}
    - overall_ok:    True only if akasha AND (telegram in {True, None})
    """
    write_result = write_to_akasha_sync(project, agent_name, finding)
    akasha_ok = bool(write_result)
    chunk_ids = (write_result or {}).get("chunk_ids", [])
    confidence_used = (write_result or {}).get("confidence_used", "INFERRED")
    new_content = (write_result or {}).get("content", "")

    tg_status = notify_telegram(agent_name, finding)

    relation_info = None
    if akasha_ok and chunk_ids:
        new_id = chunk_ids[0]
        indicator = finding.get("indicator") or finding.get("topic")
        if indicator:
            cache_key = (project, agent_name, indicator)
            with _cache_lock:
                old_entry = _recent_findings.get(cache_key)
                _recent_findings[cache_key] = (new_id, new_content)
            if old_entry:
                old_id, old_content = old_entry
                if old_id != new_id:
                    # V9: choose relation type based on content opposition
                    rel_type = "contradicts" if _detect_contradicts(new_content, old_content) else "refines"
                    if create_memory_relation(new_id, old_id, rel_type, confidence=confidence_used):
                        relation_info = {"type": rel_type, "from": new_id, "to": old_id}

    overall_ok = akasha_ok and (tg_status in (True, None))

    return {
        "akasha": akasha_ok,
        "chunk_ids": chunk_ids,
        "confidence": confidence_used,
        "telegram": tg_status,
        "relation": relation_info,
        "overall_ok": overall_ok,
    }


def _cache_trim_if_large(max_size=500):
    with _cache_lock:
        if len(_recent_findings) > max_size:
            keys = list(_recent_findings.keys())
            for k in keys[:len(keys) // 2]:
                del _recent_findings[k]
