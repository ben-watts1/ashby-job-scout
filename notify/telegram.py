"""Telegram notification helper."""

from __future__ import annotations

import requests


TELEGRAM_API_BASE = "https://api.telegram.org"


def send_message(bot_token: str, chat_id: str, text: str, timeout_seconds: int = 20) -> None:
    endpoint = f"{TELEGRAM_API_BASE}/bot{bot_token}/sendMessage"
    chat_id = str(chat_id).strip()

    response = requests.post(
        endpoint,
        data={
            "chat_id": chat_id,
            "text": text,
            "disable_web_page_preview": "true",
        },
        timeout=timeout_seconds,
    )

    if not response.ok:
        # This will show: "chat not found" / "message is too long" / etc.
        print("Telegram error response:", response.status_code, response.text)

    response.raise_for_status()
