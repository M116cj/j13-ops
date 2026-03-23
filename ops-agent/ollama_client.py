import requests
import json
import os

# Replaced Ollama → LiteLLM (OpenAI-compatible), model: local-qwen
LITELLM_URL = os.environ.get("OLLAMA_URL", "http://host.docker.internal:4000")
MODEL = os.environ.get("OPS_MODEL", "local-qwen")


def analyze(prompt: str) -> dict:
    """Ask LiteLLM/Qwen to analyze an ops issue.

    Returns a dict with keys: action, reason, telegram_msg.
    Falls back gracefully when the LLM is unavailable.
    """
    try:
        resp = requests.post(
            f"{LITELLM_URL}/v1/chat/completions",
            json={
                "model": MODEL,
                "messages": [
                    {"role": "system", "content": "You are an ops agent. Reply ONLY with valid JSON containing keys: action, reason, telegram_msg."},
                    {"role": "user", "content": prompt},
                ],
                "max_tokens": 512,
                "temperature": 0.1,
            },
            timeout=60,
        )
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"]
        return json.loads(content)
    except Exception as e:
        return {
            "action": "alert",
            "reason": f"LLM unavailable: {e}",
            "telegram_msg": "⚠️ LLM offline, manual check needed",
        }
