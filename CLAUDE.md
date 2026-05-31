# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
uv sync                          # Install / update dependencies

# Fetch FEC data via API (cached by default)
uv run api-demo.py --employer "TRACTOR SUPPLY" --min-date 2019-01-01 --max-date 2020-12-31
uv run api-demo.py --help        # Full option reference

# Analyze a local contribution CSV
uv run main.py                   # Default: ./csv/TractorSupplyFECr.csv
uv run main.py csv/MyCompanyFECr.csv

# Via just
just fetch
just fetch-fresh "TRACTOR SUPPLY"
just analyze
```

There is no test suite and no linter configured.

## Architecture

Three Python files; no shared modules beyond `fec_client.py`.

### `fec_client.py` — API client

`FECClient(api_key, cache_dir="cache", no_cache=False)` wraps the OpenFEC REST API.

- **Caching**: each page request is cached as `cache/<sha256-20>.json`; `cache/index.json` is a human-readable map of canonical request URIs → filenames. Concrete `min_date`/`max_date` are required on every call — historical FEC data is immutable, so date-bounded requests cache safely forever.
- **`schedule_a(...)`** — single page.
- **`schedule_a_pages(...)`** — iterates pages, stops at `max_pages` or when pagination is exhausted.

### `api-demo.py` — fetch CLI

Click command. Uses `FECClient`. Writes combined results to:
- `output/schedule_a/<EMPLOYER_SLUG>_<min-date>_<max-date>.json`
- `output/schedule_a/<EMPLOYER_SLUG>_<min-date>_<max-date>.csv`

### `main.py` — analysis CLI

Click command. Reads three CSVs into DuckDB (in-memory). No API calls.

Data sources:
- CLI arg / `csv/TractorSupplyFECr.csv` — per-transaction FEC contributions for one company
- `csv/AllPacs.xslx.csv` — PAC party affiliation, joined on `committee_id`
- `csv/Aristotle1.xlsx.csv` — alternate party lookup, joined on `committee_id = Code`

Pipeline:
1. **Join + clean** — merge with party lookups (`COALESCE` prefers AllPacs over Aristotle), normalize zip to 5 digits, build person key `company - lastname - zip`.
2. **Transaction-level stats** — count, max, mean, total, D/R/Other split.
3. **60% rule** — group by person key; assign `pCode` if any single party ≥ 60% of that person's total, else `'N'`.
4. **Contributor-level stats** — headcount and dollars by `pCode`.
5. **Top 10 committees** — ranked by total dollars received.
6. **Charts** — `matplotlib` pie charts; `plt.show()` blocks until the window is closed.

Company name is derived from the CSV filename by stripping the trailing `FECr?` suffix.
