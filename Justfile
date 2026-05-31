# FEC data tools
# Requires: just (https://github.com/casey/just)

default:
    @just --list

# Install dependencies
install:
    uv sync

# Run the full pipeline: fetch data → analyze CSV → execute notebook + render HTML
build: fetch analyze notebook

# Fetch Schedule A contributions (cached by default)
fetch employer="TRACTOR SUPPLY" min-date="2019-01-01" max-date="2020-12-31" pages="2":
    uv run api-demo.py --employer "{{employer}}" --min-date "{{min-date}}" --max-date "{{max-date}}" --pages {{pages}}

# Fetch without cache (force fresh API request)
fetch-fresh employer="TRACTOR SUPPLY" min-date="2019-01-01" max-date="2020-12-31" pages="2":
    uv run api-demo.py --employer "{{employer}}" --min-date "{{min-date}}" --max-date "{{max-date}}" --pages {{pages}} --no-cache

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
