"""Process inbound Telegram commands for board management and run triggers."""

from __future__ import annotations

import csv
import json
import os
import re
from pathlib import Path
from typing import Any

import requests

from notify.telegram import send_message

BASE_DIR = Path(__file__).resolve().parent
COMPANIES_PATH = BASE_DIR / "companies.csv"
OFFSET_PATH = BASE_DIR / "telegram_offset.json"
TELEGRAM_API_BASE = "https://api.telegram.org"
ASHBY_URL_PATTERN = re.compile(r"^https://jobs\.ashbyhq\.com/([A-Za-z0-9-]+)/*$")

HELP_TEXT = """🤖 Ashby Scout commands

/list
Show tracked boards

/add <ashby_url>
Add board using slug as name
Example: /add https://jobs.ashbyhq.com/rogo

/add <name> <ashby_url>
Add board with custom name
Example: /add Rogo https://jobs.ashbyhq.com/rogo

/remove <slug-or-name>
Remove a board
Example: /remove rogo

/runall
Trigger an immediate full scan across all tracked boards (ignores seen history for that run)
"""


def main() -> int:
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    authorized_chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()
    if not bot_token or not authorized_chat_id:
        raise RuntimeError("TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID environment variables are required")

    offset = load_offset(OFFSET_PATH)
    updates = get_updates(bot_token, offset)
    next_offset = offset

    for update in updates:
        update_id = _coerce_int(update.get("update_id"))
        if update_id is not None:
            next_offset = max(next_offset, update_id + 1)

        message = update.get("message")
        if not isinstance(message, dict):
            continue

        text = (message.get("text") or "").strip()
        if not text:
            continue

        chat = message.get("chat") if isinstance(message.get("chat"), dict) else {}
        chat_id_value = chat.get("id")
        chat_id = str(chat_id_value).strip() if chat_id_value is not None else ""
        if chat_id != authorized_chat_id:
            continue

        reply = handle_command(text)
        send_message(bot_token=bot_token, chat_id=authorized_chat_id, text=reply)

    save_offset(OFFSET_PATH, next_offset)
    return 0


def handle_command(text: str) -> str:
    tokens = text.split()
    if not tokens:
        return "❌ Empty command. Use /help."

    command = tokens[0].lower()
    if command == "/help":
        return HELP_TEXT
    if command == "/list":
        return format_list_reply(load_companies(COMPANIES_PATH))
    if command == "/add":
        return handle_add(tokens[1:])
    if command == "/remove":
        return handle_remove(tokens[1:])
    if command == "/runall":
        return handle_runall()

    return "❌ Unknown command. Use /help."


def handle_add(args: list[str]) -> str:
    if not args:
        return "❌ Usage: /add <ashby_url> or /add <name> <ashby_url>"

    if len(args) == 1:
        url = args[0]
        slug = parse_slug(url)
        if not slug:
            return "❌ Invalid Ashby URL. Use https://jobs.ashbyhq.com/<slug>"
        company = slug
    else:
        url = args[-1]
        slug = parse_slug(url)
        if not slug:
            return "❌ Invalid Ashby URL. Use https://jobs.ashbyhq.com/<slug>"
        company = " ".join(args[:-1]).strip() or slug

    companies = load_companies(COMPANIES_PATH)
    for existing_company, existing_url in companies:
        existing_slug = parse_slug(existing_url)
        if existing_slug == slug:
            return f"ℹ️ Board already tracked:\n{existing_company} — {existing_url}"

    companies.append((company, f"https://jobs.ashbyhq.com/{slug}"))
    companies.sort(key=lambda row: row[0].lower())
    save_companies(COMPANIES_PATH, companies)

    return f"✅ Added board\nName: {company}\nURL: https://jobs.ashbyhq.com/{slug}\nSlug: {slug}"


def handle_remove(args: list[str]) -> str:
    if len(args) != 1:
        return "❌ Usage: /remove <slug-or-name>"

    needle = args[0].strip().lower()
    companies = load_companies(COMPANIES_PATH)
    kept: list[tuple[str, str]] = []
    removed: list[tuple[str, str]] = []

    for company, url in companies:
        slug = (parse_slug(url) or "").lower()
        if company.lower() == needle or slug == needle:
            removed.append((company, url))
        else:
            kept.append((company, url))

    if not removed:
        return f"❌ No tracked board matched: {args[0]}\nUse /list to see valid names/slugs."

    save_companies(COMPANIES_PATH, kept)
    removed_names = ", ".join(company for company, _ in removed)
    return f"✅ Removed board: {removed_names}"


def handle_runall() -> str:
    token = os.getenv("GH_WORKFLOW_TOKEN", "").strip()
    repository = os.getenv("GITHUB_REPOSITORY", "").strip()
    workflow_file = os.getenv("RUN_NOW_WORKFLOW_FILE", "run-now.yml").strip()
    run_ref = os.getenv("RUN_NOW_REF", "main").strip() or "main"

    if not token or not repository:
        return "❌ /runall is not configured. Missing GH_WORKFLOW_TOKEN or GITHUB_REPOSITORY."

    url = f"https://api.github.com/repos/{repository}/actions/workflows/{workflow_file}/dispatches"
    response = requests.post(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
        },
        json={"ref": run_ref, "inputs": {"ignore_seen": "true"}},
        timeout=20,
    )
    if not response.ok:
        body = (response.text or "")[:500]
        return f"❌ Failed to trigger run-now workflow ({response.status_code}): {body}"

    return (
        "🚀 Run requested.\n"
        "Starting an immediate full scan across all tracked boards.\n"
        "This run will ignore seen history and send all current matching jobs."
    )


def get_updates(bot_token: str, offset: int) -> list[dict[str, Any]]:
    endpoint = f"{TELEGRAM_API_BASE}/bot{bot_token}/getUpdates"
    response = requests.get(
        endpoint,
        params={"offset": offset, "timeout": 0, "allowed_updates": json.dumps(["message"])},
        timeout=20,
    )
    response.raise_for_status()
    payload = response.json()
    if not payload.get("ok"):
        raise RuntimeError(f"Telegram getUpdates returned non-ok response: {payload}")

    results = payload.get("result", [])
    if not isinstance(results, list):
        return []
    return [item for item in results if isinstance(item, dict)]


def load_companies(path: Path) -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    with path.open("r", encoding="utf-8", newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        for row in reader:
            company = (row.get("company") or "").strip()
            url = (row.get("ashby_url") or "").strip()
            if company and url:
                rows.append((company, url))
    return rows


def save_companies(path: Path, rows: list[tuple[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=["company", "ashby_url"])
        writer.writeheader()
        for company, url in rows:
            writer.writerow({"company": company, "ashby_url": url})


def format_list_reply(rows: list[tuple[str, str]]) -> str:
    if not rows:
        return "📋 Tracked boards (0)"
    lines = [f"📋 Tracked boards ({len(rows)})"]
    for company, url in rows:
        lines.append(f"- {company}: {url}")
    return "\n".join(lines)


def parse_slug(ashby_url: str) -> str | None:
    match = ASHBY_URL_PATTERN.match(ashby_url.strip())
    if not match:
        return None
    return match.group(1).lower()


def load_offset(path: Path) -> int:
    if not path.exists():
        return 0
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return 0
    if isinstance(data, dict):
        return _coerce_int(data.get("offset")) or 0
    return 0


def save_offset(path: Path, offset: int) -> None:
    payload = {"offset": int(offset)}
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _coerce_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


if __name__ == "__main__":
    raise SystemExit(main())
