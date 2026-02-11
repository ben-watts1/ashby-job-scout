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

    try:
        response = requests.get(endpoint, timeout=timeout_seconds)
        response.raise_for_status()
    except requests.RequestException as exc:
        message = str(exc)
        if getattr(exc, "response", None) is not None:
            status_code = exc.response.status_code
            body = (exc.response.text or "")[:300]
            message = f"HTTP {status_code} from Ashby API for slug '{slug}': {body}"
        raise AshbyFetchError(message) from exc

    try:
        payload = response.json()
    except ValueError as exc:
        raise AshbyFetchError(f"Ashby API returned invalid JSON for slug '{slug}'") from exc

    postings = payload.get("jobs")
    if not isinstance(postings, list):
        raise AshbyFetchError(f"Ashby API response missing 'jobs' list for slug '{slug}'")

    jobs: list[Job] = []
    for posting in postings:
        if not isinstance(posting, dict):
            continue
        job = _normalize_job(company=company, board_url=ashby_url, posting=posting)
        if job is not None:
            jobs.append(job)

    return jobs


def _extract_board_slug(ashby_url: str) -> str:
    parsed = urlparse(ashby_url)
    parts = [part for part in parsed.path.split("/") if part]
    if not parts:
        raise AshbyFetchError(f"Could not parse Ashby board slug from URL: {ashby_url}")
    return parts[-1]


def _normalize_job(company: str, board_url: str, posting: dict[str, Any]) -> Job | None:
    title = str(posting.get("title") or "").strip()
    if not title:
        return None

    job_url = str(posting.get("jobUrl") or "").strip()
    apply_url = str(posting.get("applyUrl") or "").strip()
    url = job_url or apply_url or board_url

    raw_id = posting.get("id")
    job_id = str(raw_id).strip() if raw_id is not None and str(raw_id).strip() else url

    team = _coerce_team(posting.get("team"))
    if not team:
        team = _coerce_name(posting.get("department"))

    location = _coerce_location(posting.get("location"))

    return Job(
        company=company,
        job_id=job_id,
        title=title,
        team=team,
        location=location,
        url=url,
    )


def _coerce_team(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, dict):
        return _coerce_name(value)
    return ""


def _coerce_location(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, dict):
        return _coerce_name(value)
    return ""


def _coerce_name(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, dict):
        for key in ("name", "text", "label", "value"):
            candidate = value.get(key)
            if isinstance(candidate, str) and candidate.strip():
                return candidate.strip()
    return ""


def job_to_dict(job: Job) -> dict[str, str]:
    """Convert a `Job` dataclass to dict for presentation and filtering."""
    return asdict(job)
