"""Telegram notification helper."""

from __future__ import annotations

import requests

TELEGRAM_API_BASE = "https://api.telegram.org"

# Telegram limit is 4096 chars; keep headroom to be safe.
MAX_LEN = 3800


def _chunk_text(text: str, limit: int = MAX_LEN) -> list[str]:
    """
    Split text into chunks <= limit, preferring to split on line boundaries.
    """
    lines = text.splitlines(keepends=True)
    chunks: list[str] = []
    buf: list[str] = []
    size = 0

    for line in lines:
        # If a single line is huge, hard-split it
        if len(line) > limit:
            if buf:
                chunks.append("".join(buf))
                buf, size = [], 0
            for i in range(0, len(line), limit):
                chunks.append(line[i : i + limit])
            continue

        if size + len(line) > limit and buf:
            chunks.append("".join(buf))
            buf, size = [], 0

        buf.append(line)
        size += len(line)

    if buf:
        chunks.append("".join(buf))

    # Never return empty list
    return chunks or [""]


def send_message(bot_token: str, chat_id: str, text: str, timeout_seconds: int = 20) -> None:
    endpoint = f"{TELEGRAM_API_BASE}/bot{bot_token}/sendMessage"
    chat_id = str(chat_id).strip()

    parts = _chunk_text(text)

    for idx, part in enumerate(parts, start=1):
        # Optional: add a small header if multiple parts
        if len(parts) > 1:
            part = f"(Part {idx}/{len(parts)})\n{part}"

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
            print("Telegram error response:", response.status_code, response.text)

        response.raise_for_status()
