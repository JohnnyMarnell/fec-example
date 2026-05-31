# fec-example

Vibe coded for a friend.

Examples of fetching and aggregating FEC data from gov API.

## Setup

Tool versions (Python, uv, just) are pinned in `mise.toml`. The recommended bootstrap uses [mise](https://mise.jdx.dev):

```bash
git clone 'https://github.com/johnnyMarnell/fec-example'
cd fec-example
mise install   # installs pinned Python / uv / just
uv sync        # creates .venv and installs Python deps
```

Install `mise` if needed (macOS/Linux):
```bash
curl https://mise.run | sh
```

Windows: `winget install jdx.mise` or `scoop install mise`

**Without mise** — install `uv` and `just` manually, then `uv sync`:
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh   # uv
# just: https://github.com/casey/just#installation
uv sync
```

## Fetch contributions from the FEC API

Fetch Schedule A contributions for an employer (results cached locally by default):

```bash
uv run api-demo.py --employer "TRACTOR SUPPLY" --min-date 2019-01-01 --max-date 2020-12-31
# → output/schedule_a/TRACTOR_SUPPLY_2019-01-01_2020-12-31.{json,csv}
```

Force a fresh API request, skipping the cache:

```bash
uv run api-demo.py --employer "WALMART" --min-date 2021-01-01 --max-date 2022-12-31 --no-cache
```

Fetch all available pages (default is 2):

```bash
uv run api-demo.py --employer "TRACTOR SUPPLY" --min-date 2019-01-01 --max-date 2020-12-31 --pages 0
```

Full option reference:

```bash
uv run api-demo.py --help
```

## Analyze a company's contribution CSV

```bash
uv run main.py                           # defaults to ./csv/TractorSupplyFECr.csv
uv run main.py csv/TractorSupplyFECr.csv
```

## Using `just`

```bash
just install
just fetch                               # Tractor Supply, 2019-2020, 2 pages, cached
just fetch "WALMART" "2021-01-01" "2022-12-31"
just fetch-fresh "TRACTOR SUPPLY"        # bypass cache
just analyze
just analyze csv/MyCompanyFECr.csv
```

## Caching

API responses are stored in `cache/` (one JSON file per request). `cache/index.json`
maps canonical request URIs to their files for easy inspection. Supplying concrete
`--min-date` / `--max-date` bounds ensures cached responses stay valid — historical
FEC data does not change.

Pass `--no-cache` to bypass the cache and force a live API request.
