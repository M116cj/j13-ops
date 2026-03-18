import os
import requests


def send(msg: str) -> None:
    """Send a message to Telegram via bot. Silently swallows errors to avoid
    crashing the monitoring loop if Telegram is unreachable."""
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    chat_id = os.environ["TELEGRAM_CHAT_ID"]
    try:
        requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": msg, "parse_mode": "HTML"},
            timeout=10,
        )
    except Exception as e:
        print(f"[telegram] send failed: {e}")
