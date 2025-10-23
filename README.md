# fec-example

Example fetching and aggregating FEC data.

## Setup

### Install uv (once)

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

Example of 
```bash
uv run api-demo.py
```
