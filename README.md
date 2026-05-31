# fec-example

Vibe coded for a friend.

Fetches FEC contribution data, runs a port of an old SAS analysis on top of it,
and publishes the whole thing as a GitHub Pages site.

Started as a single-employer demo (`api-demo.py` + `main.py` + a basic notebook).
Now ships a multi-company port of the original SAS pipeline (`sas-fork` →
DuckDB + pandas) plus a dev server with live reload.

**Published site**: <https://johnnymarnell.github.io/fec-example/>

---

## Setup

Tool versions (Python, uv, just) are pinned in `mise.toml`. Recommended bootstrap with [mise](https://mise.jdx.dev):

```bash
git clone 'https://github.com/johnnyMarnell/fec-example'
cd fec-example
mise install   # installs pinned Python / uv / just
uv sync        # creates .venv and installs Python deps
```

Install `mise` if needed: `curl https://mise.run | sh` (macOS/Linux) · `winget install jdx.mise` (Windows).

Without mise — install `uv` and `just` manually, then `uv sync`:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh   # uv
# just: https://github.com/casey/just#installation
uv sync
```

---

## One-shot build

The full pipeline — fetch (cached), analyze, execute notebooks, render HTML, build site:

```bash
just build
# → docs/   (the published GitHub Pages site, locally)
```

Cold-cache first run: ~30–60s (most of it FEC API). Subsequent runs: a few seconds, all cache-served.

Then either:

```bash
just serve     # static mirror of what GitHub Pages serves   (no auto-reload)
just dev       # HMR-style dev: watch source, rebuild, auto-reload   (port 8000)
```

---

## What's in here

```
fec-example/
├── api-demo.py              # CLI: fetch Schedule A for one employer
├── main.py                  # CLI: 60%-rule analysis of one CSV (Tractor Supply demo)
├── fec_client.py            # disk-cached OpenFEC client (schedule_a/b, /committee/, /candidate/)
├── build-site.py            # static GitHub Pages site generator (docs/)
├── csv/                     # bundled lookup tables (AllPacs, Aristotle, demo CSV)
├── notebooks/
│   ├── basic-example.ipynb  # single-employer demo + party pie charts
│   └── cross-company.ipynb  # multi-company SAS-port pipeline + Schedule B + candidate enrichment
├── tools/
│   ├── build_cross_company_nb.py  # builder for the cross-company notebook (single source of truth)
│   ├── prewarm_cache.py           # idempotent fetch of every endpoint the notebook needs
│   └── dev_watch.py               # `just dev` — HMR-style file-watch + browser auto-reload
├── docs-src/
│   └── sas-port.md          # design doc — how the SAS pipeline maps to DuckDB + pandas
├── output/
│   ├── schedule_a/          # raw API fetches per employer (JSON + CSV)
│   ├── tables/              # SAS-parity summaries (company_contributors.csv, …, summary.json)
│   └── charts/              # rendered chart PNGs
├── cache/                   # disk cache for FEC API responses (gitignored)
└── docs/                    # built site (gitignored; this is what GH Pages serves)
```

---

## The cross-company notebook

The headline analysis. 52 cells, ~5 employers, four FEC endpoints, all SAS logic preserved
(60% rule, gender inference, `compervar` person key) plus the things SAS couldn't do.

**Default employers** (override by editing the `COMPANIES` list in the notebook):

| Employer | Schedule A rows | Tilt |
|---|---|---|
| `TRACTOR SUPPLY` | 200 | R-leaning |
| `MICROSOFT` | 200 | D-leaning |
| `EXXON MOBIL` | 200 | strongly R |
| `WALMART` | 200 | mixed |
| `LOCKHEED MARTIN` | 200 | bipartisan |

**Latest run**: 5 companies · $96K inflow · $871K Schedule B outflow tracked · 334 unique contributors · 20 recipient candidates resolved by party.

**Regenerate / edit**:

```bash
just notebook-edit notebooks/cross-company.ipynb     # interactive Jupyter
just notebook-build-cross-company                    # regen .ipynb from the builder script
just notebook                                        # execute + render all notebooks to HTML
```

The notebook is committed pre-executed (with outputs); `just notebook` re-runs it.

---

## FEC API endpoints used

All go through `FECClient` (disk-cached, key = canonical request URI):

| Endpoint | Purpose | Where |
|---|---|---|
| `/schedules/schedule_a/` | Individual contributions by employer | every fetch path |
| `/schedules/schedule_b/` | Disbursements (where the PAC spent the money) | §12 of cross-company nb |
| `/committee/{id}/` | Authoritative committee party / type / designation | §13 of cross-company nb |
| `/candidate/{id}/` | Candidate party / office / state | §14 of cross-company nb |

Pre-warm the cache for *everything* the notebook needs in one go (idempotent):

```bash
just prewarm-cache
# 4-phase walk: schedule_a × employers · schedule_b × top recipients
#               /committee/ × fell-through · /candidate/ × top recipients
```

---

## Single-employer flow (the original demo)

Fetch Schedule A for one employer:

```bash
uv run api-demo.py --employer "TRACTOR SUPPLY" --min-date 2019-01-01 --max-date 2020-12-31
# → output/schedule_a/TRACTOR_SUPPLY_2019-01-01_2020-12-31.{json,csv}

uv run api-demo.py --employer "WALMART" --min-date 2021-01-01 --max-date 2022-12-31 --no-cache
uv run api-demo.py --employer "TRACTOR SUPPLY" --min-date 2019-01-01 --max-date 2020-12-31 --pages 0  # all pages
uv run api-demo.py --help
```

Analyze a company's CSV (joins AllPacs + Aristotle, applies the 60% rule, renders a pie chart):

```bash
uv run main.py                            # defaults to ./csv/TractorSupplyFECr.csv
uv run main.py csv/MyCompanyFECr.csv
```

---

## Justfile recipes

```bash
just build                          # prewarm → analyze → notebooks → site  (full pipeline)
just dev                            # HMR-style dev server — watches code, rebuilds, browser auto-reloads
just serve                          # static mirror of docs/ (no auto-reload — what GH Pages serves)

just install                        # uv sync
just fetch "EMPLOYER" min max pages # cached Schedule A fetch
just fetch-fresh                    # bypass cache
just prewarm-cache                  # cache every endpoint the cross-company notebook needs
just analyze [csv]                  # run main.py on a CSV
just pages                          # rebuild static site from current outputs
just notebook                       # execute + render every notebooks/*.ipynb
just notebook-edit [nb]             # open a notebook in interactive Jupyter
just notebook-build-cross-company   # regenerate cross-company.ipynb from its builder script
```

---

## Dev server (`just dev`)

Routes file changes to the cheapest correct rebuild, then the browser auto-reloads via injected JS:

| Changed | Action | Cost |
|---|---|---|
| `build-site.py`, `docs-src/*.md`, `output/**`, `main.py`, `api-demo.py` | rebuild site | ~0.3s |
| `notebooks/*.ipynb` | render that notebook → HTML, rebuild site | ~3s |
| `tools/build_cross_company_nb.py` | regen .ipynb → execute → render → rebuild | ~30s |
| `fec_client.py` | re-execute cross-company nb (it imports this) → render → rebuild | ~30s |

```bash
just dev           # http://127.0.0.1:8000
just dev 8081      # custom port
```

---

## Caching

API responses are stored in `cache/` (one JSON per request). `cache/index.json` maps the
canonical request URI to its on-disk filename for easy inspection. Concrete `min-date` /
`max-date` bounds keep cached responses valid — historical FEC data doesn't change.

```bash
ls cache/                  # one .json per request + index.json
cat cache/index.json       # URI → filename
```

Pass `--no-cache` (CLI) or `quiet=True` (in code) to bypass / silence the cache.

---

## Outputs

Everything publishable lands under `output/`:

| Path | Contents |
|---|---|
| `output/schedule_a/<EMPLOYER>_<min>_<max>.{json,csv}` | Raw API fetches |
| `output/tables/company_contributors.csv` | SAS-parity, one row per employer · contributor counts × party × gender |
| `output/tables/company_contributions.csv` | SAS-parity, same shape but transaction-level |
| `output/tables/stats5all_sample.csv` | 200-row sample of contributor-level table (`stats5`) |
| `output/tables/saspac3all_sample.csv` | 500-row sample of contribution-level table (`saspac3`) |
| `output/tables/schedule_b_sample.csv` | Disbursements pulled per top recipient committee |
| `output/tables/top_outflow_per_company.csv` | Top 5 outflow destinations per company |
| `output/tables/candidate_enrichment.csv` | Top 20 recipient candidates with party / office |
| `output/tables/company_summaries.xlsx` | Excel workbook with `contributors` + `contributions` sheets |
| `output/tables/summary.json` | Headline metrics for the landing page (single source of truth) |
| `output/charts/*.png` | All matplotlib output |

The static site (`docs/`) is auto-generated from these by `build-site.py`.

---

## Design / SAS context

The cross-company notebook is a port of an old SAS analysis prepared for
*Mitchell Langbert, Associate Professor, Brooklyn College*. See
[`docs-src/sas-port.md`](docs-src/sas-port.md) (rendered at `/design/sas-port/`
on the published site) for:

- The 11-step SAS pipeline as a Mermaid diagram, with row/var counts at each step
- A SAS-construct → DuckDB/pandas mapping table
- The 60% rule and `compervar` person-key explained
- What the port adds beyond SAS (Schedule B, API-direct party, candidate enrichment, multi-company side-by-side)
