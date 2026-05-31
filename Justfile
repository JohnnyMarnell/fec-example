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

# Run the full pipeline: fetch → analyze → notebook + HTML → site
# Pass --no-cache to bypass local API cache: just build --no-cache
build *flags:
    just fetch {{flags}}
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

# Analyze a company's contribution CSV
analyze csv="./csv/TractorSupplyFECr.csv":
    uv run main.py "{{csv}}"

# Execute notebook and render to HTML (both committed to git)
notebook:
    uv run jupyter nbconvert --to notebook --execute --inplace notebooks/analysis.ipynb
    uv run jupyter nbconvert --to html notebooks/analysis.ipynb --output-dir notebooks/

# Open notebook for interactive editing
notebook-edit:
    uv run jupyter notebook notebooks/analysis.ipynb

# Serve the built site locally — mirrors what GitHub Pages serves from docs/
serve port="8000":
    @echo "http://localhost:{{port}}  (Ctrl-C to stop)"
    uv run python -m http.server {{port}} --directory docs
