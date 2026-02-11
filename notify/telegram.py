"""Telegram notification helper."""

from __future__ import annotations

from typing import List

import requests


TELEGRAM_API_BASE = "https://api.telegram.org"
TELEGRAM_MAX_MESSAGE_CHARS = 4096


def send_message(bot_token: str, chat_id: str, text: str, timeout_seconds: int = 20) -> None:
    """Send one or more Telegram messages.

    Telegram messages have a hard 4096-character limit, so large digests are split
    into multiple chunks on line boundaries where possible.
    """
    endpoint = f"{TELEGRAM_API_BASE}/bot{bot_token}/sendMessage"

    parts = _split_message(text, TELEGRAM_MAX_MESSAGE_CHARS)
    for part in parts:
        response = requests.post(
            endpoint,
            data={
                "chat_id": chat_id,
                "text": part,
                "disable_web_page_preview": "true",
            },
            timeout=timeout_seconds,
        )
        if not response.ok:
            body = (response.text or "")[:500]
            raise requests.HTTPError(
                f"Telegram sendMessage failed with HTTP {response.status_code}: {body}",
                response=response,
            )


def _split_message(text: str, max_chars: int) -> List[str]:
    if not text:
        return [""]

    if len(text) <= max_chars:
        return [text]

    chunks: List[str] = []
    current = ""

    for line in text.splitlines(keepends=True):
        if len(line) > max_chars:
            if current:
                chunks.append(current)
                current = ""
            for i in range(0, len(line), max_chars):
                chunks.append(line[i : i + max_chars])
            continue

        if len(current) + len(line) > max_chars:
            chunks.append(current)
            current = line
        else:
            current += line

    if current:
        chunks.append(current)

    return chunks
