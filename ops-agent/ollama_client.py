import requests
import json
import os

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://host.docker.internal:11434")
MODEL = os.environ.get("OPS_MODEL", "qwen2.5:7b")


def analyze(prompt: str) -> dict:
    """Ask Ollama to analyze an ops issue.

    Returns a dict with keys: action, reason, telegram_msg.
    Falls back gracefully when the LLM is unavailable so the monitoring loop
    can still execute rule-based repairs.
    """
    try:
        resp = requests.post(
            f"{OLLAMA_URL}/api/generate",
            json={
                "model": MODEL,
                "prompt": prompt,
                "stream": False,
                "format": "json",
            },
            timeout=60,
        )
        resp.raise_for_status()
        return json.loads(resp.json()["response"])
    except Exception as e:
        return {
            "action": "alert",
            "reason": f"LLM unavailable: {e}",
            "telegram_msg": "⚠️ LLM offline, manual check needed",
        }
