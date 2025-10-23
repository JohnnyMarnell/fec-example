# fec-example

Example fetching and aggregating FEC data.

## Setup

### Prerequisites (once)

Make sure `git` CLI is installed. In a terminal / Git Shell,
clone this repo and `cd` to it:
```bash
git clone 'https://github.com/johnnyMarnell/fec-example'
cd fec-example
```

This project uses uv + python, make sure uv is installed:
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### Install project dependencies (infrequent)

```bash
uv sync
```

### Run

Aggregate FEC data and print stats to console, plus render bar charts example
```bash
uv run main.py
```

Example of FEC API calls (from https://api.open.fec.gov/developers)
```bash
uv run api-demo.py
```
