# Ashby Job Scout (Telegram)

A minimal Python job monitor that checks selected Ashby boards, filters by configurable keywords/locations, tracks seen jobs, and sends one Telegram digest message each weekday at **08:30 Europe/London** via GitHub Actions.

## What this does

- Reads company boards from `companies.csv`.
- Fetches jobs from Ashby's public posting API (`https://api.ashbyhq.com/posting-api/job-board/{slug}`).
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
- `process_telegram_commands.py` — inbound Telegram command processing.
- `connectors/ashby.py` — Ashby public API fetch + parse.
- `matcher.py` — filtering logic.
- `notify/telegram.py` — Telegram API integration.
- `storage.py` — seen-state read/write and new-job detection.
- `seen_jobs.json` — persisted state, committed to repo.
- `telegram_offset.json` — update offset for Telegram command polling.
- `.github/workflows/daily.yml` — scheduled runner and state commit.
- `.github/workflows/telegram-commands.yml` — process bot commands and commit updates.
- `.github/workflows/run-now.yml` — manually/externally trigger an immediate scan.

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

For command-triggered `/runall`, also set a GitHub token with workflow dispatch permissions:

```bash
export GH_WORKFLOW_TOKEN="<github_token_with_repo_and_actions_scope>"
export GITHUB_REPOSITORY="<owner>/<repo>"
```

(For GitHub Actions, use repo secrets.)

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

### Run all currently matched jobs, ignoring seen history

```bash
python main.py --ignore-seen
```

This sends all currently matched jobs regardless of whether they were seen before.
It does **not** update `seen_jobs.json`.

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

Edit `companies.csv` directly, or use Telegram commands (with `telegram-commands` workflow enabled).

CSV format:

```csv
company,ashby_url
exampleco,https://jobs.ashbyhq.com/exampleco
```

## Telegram bot commands

When `.github/workflows/telegram-commands.yml` is enabled, send these commands from the authorized chat (`TELEGRAM_CHAT_ID`):

- `/help` — show command usage.
- `/list` — show tracked boards.
- `/add https://jobs.ashbyhq.com/<slug>` — add board using slug as name.
- `/add <name> https://jobs.ashbyhq.com/<slug>` — add board with custom name.
- `/remove <slug-or-name>` — remove a tracked board.
- `/runall` — dispatch `.github/workflows/run-now.yml` with `ignore_seen=true`.

`/runall` requires `GH_WORKFLOW_TOKEN` secret in `telegram-commands` workflow.

## GitHub Actions schedule details

GitHub cron uses UTC only. To keep **08:30 Europe/London** through DST changes, workflow triggers at both:
- `07:30 UTC` weekdays
- `08:30 UTC` weekdays

Then it gates execution by checking local London time and runs only when it's exactly `08:30` in `Europe/London`.

Manual runs bypass the 08:30 gate.

After the daily run, if `seen_jobs.json` changed, the workflow commits and pushes it back to the branch.
