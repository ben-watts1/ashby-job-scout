"""Persistent storage for seen job identifiers."""

from __future__ import annotations

import json
from pathlib import Path


State = dict[str, list[str]]


def load_seen(path: Path) -> State:
    if not path.exists():
        return {}
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        return {}

    normalized: State = {}
    for company, identifiers in raw.items():
        if isinstance(company, str) and isinstance(identifiers, list):
            normalized[company] = [str(item) for item in identifiers]
    return normalized


def save_seen(path: Path, seen: State) -> None:
    path.write_text(json.dumps(seen, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def split_new_jobs(jobs: list[dict[str, str]], seen_identifiers: list[str]) -> tuple[list[dict[str, str]], list[str]]:
    seen_set = set(seen_identifiers)
    new_jobs: list[dict[str, str]] = []

    for job in jobs:
        identifier = job.get("job_id") or job.get("url", "")
        if identifier and identifier not in seen_set:
            new_jobs.append(job)
        if identifier:
            seen_set.add(identifier)

    return new_jobs, sorted(seen_set)
