# Ashby Job Scout (Telegram)

A minimal Python job monitor that checks selected Ashby boards, filters by configurable keywords/locations, tracks seen jobs, and sends one Telegram digest message each weekday at **08:30 Europe/London** via GitHub Actions.

## What this does

- Reads company boards from `companies.csv`.
- Fetches and parses Ashby jobs from `__NEXT_DATA__` JSON.
- Normalizes each job to:
  - `company`
  - `job_id` (or URL fallback)
  - `title`
  - `team`
  - `location`
  - `url`
- Applies filters from `config.yml`.
- Compares against `seen_jobs.json` and keeps only **new** matches.
- Sends a Telegram digest:
  - New jobs grouped by company, or
  - `No new matches today.`
  - Plus an `Errors` section if any board fails.
- Saves updated `seen_jobs.json` (normal mode).

## Repo structure

- `companies.csv` — company list and Ashby URLs.
- `config.yml` — include/exclude/location filters.
- `main.py` — orchestration.
- `connectors/ashby.py` — Ashby fetch + parse.
- `matcher.py` — filtering logic.
- `notify/telegram.py` — Telegram `sendMessage` integration.
- `storage.py` — seen-state read/write and new-job detection.
- `seen_jobs.json` — persisted state, committed to repo.
- `.github/workflows/daily.yml` — scheduled runner and state commit.

## Setup

### 1) Python dependencies

```bash
pip install -r requirements.txt
```

### 2) Environment variables

Set locally for manual runs:

```bash
export TELEGRAM_BOT_TOKEN="<your_token>"
export TELEGRAM_CHAT_ID="<your_chat_id>"
```

(For GitHub Actions, use repo secrets already configured.)

## Run locally

### Normal run

```bash
python main.py
```

This sends Telegram and updates `seen_jobs.json`.

### Dry run (safe test)

```bash
python main.py --dry-run
```

This performs fetch + filter + new-job calculation, then prints the digest to stdout.
It **does not** send Telegram and **does not** update `seen_jobs.json`.

## Configure matching rules

Edit `config.yml`:

```yaml
include:
  - machine learning
  - data engineer
exclude:
  - senior
locations_include:
  - london
  - remote uk
```

Rules:
- `include`: if non-empty, at least one term must match title/team/location.
- `exclude`: if any term matches title/team/location, job is dropped.
- `locations_include`: if non-empty, location must match at least one term.

Matching is case-insensitive and uses simple substring checks.

## Add or remove companies

Edit `companies.csv`:

```csv
company,ashby_url
exampleco,https://jobs.ashbyhq.com/exampleco
```

## GitHub Actions schedule details

GitHub cron uses UTC only. To keep **08:30 Europe/London** through DST changes, workflow triggers at both:
- `07:30 UTC` weekdays
- `08:30 UTC` weekdays

Then it gates execution by checking local London time and runs only when it's exactly `08:30` in `Europe/London`.

After the run, if `seen_jobs.json` changed, the workflow commits and pushes it back to the branch.
