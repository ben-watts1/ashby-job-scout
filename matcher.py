"""Keyword and location matching for jobs."""

from __future__ import annotations

from typing import Any


def filter_jobs(jobs: list[dict[str, str]], config: dict[str, Any]) -> list[dict[str, str]]:
    include = _lowered(config.get("include", []))
    exclude = _lowered(config.get("exclude", []))
    locations_include = _lowered(config.get("locations_include", []))

    matched: list[dict[str, str]] = []
    for job in jobs:
        searchable = " | ".join([job.get("title", ""), job.get("team", ""), job.get("location", "")]).lower()
        location_value = job.get("location", "").lower()

        if include and not any(keyword in searchable for keyword in include):
            continue

        if exclude and any(keyword in searchable for keyword in exclude):
            continue

        if locations_include and not any(loc in location_value for loc in locations_include):
            continue

        matched.append(job)

    return matched


def _lowered(values: Any) -> list[str]:
    if not isinstance(values, list):
        return []
    return [str(value).strip().lower() for value in values if str(value).strip()]
