# FEC data tools
# Requires: just (https://github.com/casey/just)

# Default fetch parameters — override with: just --set EMPLOYER "WALMART" fetch
EMPLOYER := "TRACTOR SUPPLY"
MIN_DATE  := "2019-01-01"
MAX_DATE  := "2020-12-31"
PAGES     := "2"

default:
    @just --list

# Install dependencies
install:
    uv sync

# Full pipeline: prewarm-cache → analyze → notebooks + HTML → site
build:
    just prewarm-cache
    just analyze
    just notebook
    just pages

# Build the GitHub Pages static site from current outputs
pages:
    python build-site.py

# Fetch Schedule A contributions (cached by default)
# Pass --no-cache to force a fresh API request: just fetch --no-cache
fetch *flags:
    uv run api-demo.py --employer "{{EMPLOYER}}" --min-date "{{MIN_DATE}}" --max-date "{{MAX_DATE}}" --pages {{PAGES}} {{flags}}

# Fetch without cache (force fresh API request)
fetch-fresh:
    just fetch --no-cache

# Cache every endpoint the cross-company notebook uses (Schedule A + B + /committee/). Idempotent.
prewarm-cache:
    uv run python tools/prewarm_cache.py

# Analyze a company's contribution CSV
analyze csv="./csv/TractorSupplyFECr.csv":
    uv run main.py "{{csv}}"

# Execute all notebooks and render each to HTML (executed .ipynb + .html committed to git)
notebook:
    #!/usr/bin/env bash
    set -euo pipefail
    for nb in notebooks/*.ipynb; do
        echo "▶ $nb"
        uv run jupyter nbconvert --to notebook --execute --inplace "$nb"
        uv run jupyter nbconvert --to html "$nb" --output-dir notebooks/
    done

# Open the specified notebook for interactive editing (default: basic-example.ipynb)
notebook-edit nb="notebooks/basic-example.ipynb":
    uv run jupyter notebook "{{nb}}"

# Regenerate the cross-company notebook from its builder script
notebook-build-cross-company:
    uv run python tools/build_cross_company_nb.py

# Re-import small data files from the sibling sas-fork repo (Fortune 500, agencies, BODs).
# Run after `git lfs pull` in ../sas-fork. Idempotent — overwrites existing csv/ entries.
import-sas-data:
    uv run python tools/import_sas_data.py

# Serve the built site locally — mirrors what GitHub Pages serves from docs/
serve port="8000":
    @echo "http://localhost:{{port}}  (Ctrl-C to stop)"
    uv run python -m http.server {{port}} --directory docs

# HMR-style dev server — watch sources, rebuild incrementally, auto-reload browser.
dev port="8000":
    uv run python tools/dev_watch.py {{port}}
