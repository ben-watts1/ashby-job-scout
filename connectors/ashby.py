"""Ashby job board connector using Ashby's public posting API."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any
from urllib.parse import urlparse

import requests

ASHBY_POSTING_API_BASE = "https://api.ashbyhq.com/posting-api/job-board"


@dataclass(frozen=True)
class Job:
    company: str
    job_id: str
    title: str
    team: str
    location: str
    url: str


class AshbyFetchError(RuntimeError):
    """Raised when an Ashby board can't be fetched or parsed."""


def fetch_jobs(company: str, ashby_url: str, timeout_seconds: int = 20) -> list[Job]:
    """Fetch and normalize jobs from a single Ashby board via public API."""
    slug = _extract_board_slug(ashby_url)
    endpoint = f"{ASHBY_POSTING_API_BASE}/{slug}"

    response = requests.get(endpoint, timeout=timeout_seconds)
    try:
        response.raise_for_status()
    except requests.HTTPError as exc:
        raise AshbyFetchError(f"API request failed ({response.status_code}): {response.text[:300]}") from exc

    payload = response.json()
    postings = payload.get("jobs")
    if not isinstance(postings, list):
        raise AshbyFetchError("API response did not include a valid 'jobs' list")

    jobs: list[Job] = []
    for posting in postings:
        if not isinstance(posting, dict):
            continue
        job = _normalize_job(company=company, posting=posting)
        if job:
            jobs.append(job)

    if not jobs:
        raise AshbyFetchError("API returned no parseable jobs")

    return jobs


def _extract_board_slug(ashby_url: str) -> str:
    parsed = urlparse(ashby_url)
    parts = [part for part in parsed.path.split("/") if part]
    if not parts:
        raise AshbyFetchError(f"Could not parse Ashby board slug from URL: {ashby_url}")
    return parts[-1]


def _normalize_job(company: str, posting: dict[str, Any]) -> Job | None:
    title = str(posting.get("title") or "").strip()
    if not title:
        return None

    job_url = str(posting.get("jobUrl") or "").strip()
    apply_url = str(posting.get("applyUrl") or "").strip()
    if not job_url:
        return None

    job_id = apply_url or job_url
    location = _coerce_location(posting.get("location"))

    team = str(posting.get("team") or "").strip()
    if not team:
        team = _coerce_department(posting.get("department"))

    return Job(
        company=company,
        job_id=job_id,
        title=title,
        team=team,
        location=location,
        url=job_url,
    )


def _coerce_location(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, dict):
        for key in ("location", "name", "label", "value", "text"):
            candidate = value.get(key)
            if isinstance(candidate, str) and candidate.strip():
                return candidate.strip()
        return ""
    return str(value).strip()


def _coerce_department(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, dict):
        for key in ("name", "label", "value", "text"):
            candidate = value.get(key)
            if isinstance(candidate, str) and candidate.strip():
                return candidate.strip()
        return ""
    return str(value).strip()


def job_to_dict(job: Job) -> dict[str, str]:
    """Convert a `Job` dataclass to dict for presentation and filtering."""
    return asdict(job)
