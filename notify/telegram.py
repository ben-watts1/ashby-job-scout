"""Telegram notification helper."""

from __future__ import annotations

import requests


TELEGRAM_API_BASE = "https://api.telegram.org"


def send_message(bot_token: str, chat_id: str, text: str, timeout_seconds: int = 20) -> None:
    endpoint = f"{TELEGRAM_API_BASE}/bot{bot_token}/sendMessage"
    response = requests.post(
        endpoint,
        data={
            "chat_id": chat_id,
            "text": text,
            "disable_web_page_preview": "true",
        },
        timeout=timeout_seconds,
    )
    response.raise_for_status()
