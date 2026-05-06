# get-ons-vis-screenshots

**[View the screenshots](https://onsdigital.github.io/get-ons-vis-screenshots/)**

This repository automatically captures screenshots of interactive data visualisations published on the [ONS website](https://www.ons.gov.uk). It crawls recent ONS releases, finds embedded visualisations, takes screenshots of each one, and commits them to this repo.

## How it works

`get_pages.py` does the following:

1. Queries the ONS releases API to get a list of recent publications, in reverse chronological order.
2. For each release, fetches the release page and finds links to related articles, bulletins, and methodologies.
3. For each linked document, extracts any embedded visualisation URLs (`/visualisations/...`).
4. Takes a screenshot of each new visualisation using [shot-scraper](https://github.com/simonw/shot-scraper) (with a Playwright fallback).
5. Saves results to `articles-and-dvcs.json` and screenshot filename mappings to `screenshot-filenames.json`.

Screenshots are stored in the `screenshots/` directory and the index page at `index.html` provides a browsable view.

## Automated runs

The `shots.yml` GitHub Actions workflow runs daily at 03:05 UTC, and also triggers on every push. It scrapes releases back to the most recent release date already recorded in `articles-and-dvcs.json`, so only new content is fetched each run.

## Manual / backfill runs

To scrape further back in time, pass `--since` to the script:

```bash
# Relative: go back 6 months
python get_pages.py --since 6months

# Relative: go back 30 days
python get_pages.py --since 30days

# Absolute: go back to a specific date
python get_pages.py --since 2024-01-01
```

By default the script fetches up to 15 pages of results (150 releases per page). For longer backfills, increase this with `--max-pages`:

```bash
python get_pages.py --since 2years --max-pages 200
```

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
shot-scraper install   # installs Playwright browser
```
