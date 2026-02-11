"""Ashby job board connector."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import re
from typing import Any, Iterable
from urllib.parse import urljoin, urlparse

import requests

NEXT_DATA_PATTERN = re.compile(
    r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', re.DOTALL
)

KNOWN_POSTING_PATHS: tuple[tuple[str, ...], ...] = (
    ("props", "pageProps", "jobPostings"),
    ("props", "pageProps", "jobs"),
    ("props", "pageProps", "board", "jobPostings"),
    ("props", "pageProps", "board", "jobs"),
    ("props", "pageProps", "organization", "jobPostings"),
    ("props", "pageProps", "organization", "jobs"),
)


@dataclass(frozen=True)
class Job:
    company: str
    job_id: str
    title: str
    team: str
    location: str
    url: str


class AshbyFetchError(RuntimeError):
    """Raised when an Ashby board can't be parsed or fetched."""


def fetch_jobs(company: str, ashby_url: str, timeout_seconds: int = 20) -> list[Job]:
    """Fetch and normalize jobs from a single Ashby board."""
    response = requests.get(ashby_url, timeout=timeout_seconds)
    response.raise_for_status()

    match = NEXT_DATA_PATTERN.search(response.text)
    if not match:
        raise AshbyFetchError("__NEXT_DATA__ JSON script was not found")

    next_data = json.loads(match.group(1))
    postings = _find_job_postings(next_data)
    if not postings:
        raise AshbyFetchError("No job postings were found in __NEXT_DATA__")

    jobs: list[Job] = []
    for posting in postings:
        job = _normalize_job(company=company, board_url=ashby_url, posting=posting)
        if job:
            jobs.append(job)

    if not jobs:
        raise AshbyFetchError("Job posting payload was found, but no valid jobs were parsed")

    return jobs


def _find_job_postings(payload: Any) -> list[dict[str, Any]]:
    for path in KNOWN_POSTING_PATHS:
        candidate = _get_path(payload, path)
        if _is_posting_list(candidate):
            return candidate

    candidates: list[list[dict[str, Any]]] = []

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            for value in node.values():
                walk(value)
            return
        if isinstance(node, list):
            if _is_posting_list(node):
                candidates.append(node)
            for value in node:
                walk(value)

    walk(payload)
    if not candidates:
        return []

    return max(candidates, key=lambda items: sum(_looks_like_job(item) for item in items))


def _get_path(payload: Any, path: tuple[str, ...]) -> Any:
    node = payload
    for key in path:
        if not isinstance(node, dict) or key not in node:
            return None
        node = node[key]
    return node


def _is_posting_list(node: Any) -> bool:
    if not isinstance(node, list) or not node or not all(isinstance(item, dict) for item in node):
        return False
    valid_count = sum(_looks_like_job(item) for item in node)
    return valid_count >= max(1, len(node) // 2)


def _looks_like_job(item: dict[str, Any]) -> bool:
    keys = {key.lower() for key in item.keys()}
    has_title = any(key in keys for key in ("title", "jobtitle"))
    has_identifier = any(key in keys for key in ("id", "jobid", "jobpostingid"))
    raw_url = _first_text(item, ["jobUrl", "absoluteUrl", "applyUrl", "url", "jobPostingUrl", "jobPath", "path"])
    has_job_url = _looks_like_job_url(raw_url)
    return has_title and (has_identifier or has_job_url)


def _looks_like_job_url(raw_url: str) -> bool:
    if not raw_url:
        return False
    parsed = urlparse(raw_url)
    path = parsed.path.lower()
    return "/" in path and any(token in path for token in ("job", "jobs", "position", "role"))


def _normalize_job(company: str, board_url: str, posting: dict[str, Any]) -> Job | None:
    title = _first_text(posting, ["title", "jobTitle", "name"]) or "Untitled role"
    title = " ".join(title.split())
    if len(title) > 200:
        return None

    team = _first_text(posting, ["team", "department", "departmentName", "jobDepartment"]) or ""
    location = _extract_location(posting)
    raw_url = _first_text(
        posting,
        [
            "jobUrl",
            "absoluteUrl",
            "applyUrl",
            "url",
            "jobPostingUrl",
            "jobPath",
            "path",
        ],
    )
    url = urljoin(board_url.rstrip("/") + "/", raw_url) if raw_url else board_url
    if not _looks_like_job_url(url):
        return None

    raw_id = _first_text(posting, ["id", "jobId", "jobPostingId", "slug"])
    job_id = (raw_id or url).strip()
    if not job_id:
        return None

    return Job(
        company=company,
        job_id=job_id,
        title=title,
        team=team.strip(),
        location=location.strip(),
        url=url.strip(),
    )


def _extract_location(posting: dict[str, Any]) -> str:
    direct = _first_text(posting, ["location", "locationName", "jobLocation", "city"])
    if direct:
        return direct

    location_parts = _first_collection_text(posting, ["locations", "locationNames"])
    if location_parts:
        return ", ".join(location_parts)

    return ""


def _first_text(payload: dict[str, Any], keys: Iterable[str]) -> str:
    lowered = {key.lower(): value for key, value in payload.items()}
    for key in keys:
        value = lowered.get(key.lower())
        parsed = _coerce_text(value)
        if parsed:
            return parsed
    return ""


def _first_collection_text(payload: dict[str, Any], keys: Iterable[str]) -> list[str]:
    lowered = {key.lower(): value for key, value in payload.items()}
    for key in keys:
        value = lowered.get(key.lower())
        if isinstance(value, list):
            items = [_coerce_text(item) for item in value]
            clean = [item for item in items if item]
            if clean:
                return clean
    return []


def _coerce_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, dict):
        for candidate in ("name", "label", "value", "text", "title"):
            nested = value.get(candidate)
            if isinstance(nested, str) and nested.strip():
                return nested
    return ""


def job_to_dict(job: Job) -> dict[str, str]:
    """Convert a `Job` dataclass to dict for presentation and filtering."""
    return asdict(job)
