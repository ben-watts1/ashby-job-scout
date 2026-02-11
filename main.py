"""Fetch Ashby jobs, match filters, and notify via Telegram."""

from __future__ import annotations

import argparse
import csv
from datetime import datetime
import os
from pathlib import Path
from typing import Any

import yaml

from connectors.ashby import AshbyFetchError, fetch_jobs, job_to_dict
from matcher import filter_jobs
from notify.telegram import send_message
from storage import load_seen, save_seen, split_new_jobs


BASE_DIR = Path(__file__).resolve().parent
COMPANIES_PATH = BASE_DIR / "companies.csv"
CONFIG_PATH = BASE_DIR / "config.yml"
SEEN_PATH = BASE_DIR / "seen_jobs.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check Ashby boards and send Telegram digest.")
    parser.add_argument("--dry-run", action="store_true", help="Print digest only; do not send Telegram or save seen jobs.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config = load_config(CONFIG_PATH)
    companies = load_companies(COMPANIES_PATH)
    seen_state = load_seen(SEEN_PATH)

    grouped_new_jobs: dict[str, list[dict[str, str]]] = {}
    next_seen_state = {company: list(ids) for company, ids in seen_state.items()}
    errors: list[str] = []

    for company, url in companies:
        try:
            raw_jobs = [job_to_dict(job) for job in fetch_jobs(company=company, ashby_url=url)]
            matched_jobs = filter_jobs(raw_jobs, config)
            new_jobs, merged_seen = split_new_jobs(matched_jobs, next_seen_state.get(company, []))
            next_seen_state[company] = merged_seen
            if new_jobs:
                grouped_new_jobs[company] = new_jobs
        except (AshbyFetchError, ValueError, KeyError, OSError) as exc:
            errors.append(f"- {company}: {exc}")
        except Exception as exc:  # noqa: BLE001
            errors.append(f"- {company}: Unexpected error ({exc})")

    digest = render_message(grouped_new_jobs=grouped_new_jobs, errors=errors)

    if args.dry_run:
        print(digest)
        print("\nDry-run mode: Telegram send skipped; seen_jobs.json not updated.")
        return 0

    bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()
    if not bot_token or not chat_id:
        raise RuntimeError("TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID environment variables are required")

    send_message(bot_token=bot_token, chat_id=chat_id, text=digest)
    save_seen(SEEN_PATH, next_seen_state)
    return 0


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


def load_config(path: Path) -> dict[str, Any]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        raise ValueError("config.yml must contain a top-level mapping")
    return raw


def render_message(grouped_new_jobs: dict[str, list[dict[str, str]]], errors: list[str]) -> str:
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    lines = [f"Ashby job scout update ({now})"]

    if grouped_new_jobs:
        lines.append("")
        lines.append("New matching jobs:")
        for company in sorted(grouped_new_jobs):
            lines.append(f"\n{company}:")
            for job in grouped_new_jobs[company]:
                title = job.get("title", "Untitled")
                location = job.get("location") or "N/A"
                team = job.get("team") or "N/A"
                url = job.get("url", "")
                lines.append(f"- {title} | {location} | {team} | {url}")
    else:
        lines.append("")
        lines.append("No new matches today.")

    if errors:
        lines.append("")
        lines.append("Errors:")
        lines.extend(errors)

    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
