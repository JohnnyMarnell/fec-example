#!/usr/bin/env python3
"""Fetch FEC Schedule A contribution data and write results to disk."""
import json
import re
from pathlib import Path

import click
import pandas as pd

from fec_client import FECClient

_DEFAULT_API_KEY = "Kgkivmpbsy1rehiCuTcd8gVHxzwQFRcSDsrVhQJm"


@click.command()
@click.option("--employer", default="TRACTOR SUPPLY", show_default=True, help="Employer name to search.")
@click.option("--min-date", default="2019-01-01", show_default=True, help="Earliest contribution date (YYYY-MM-DD).")
@click.option("--max-date", default="2020-12-31", show_default=True, help="Latest contribution date (YYYY-MM-DD).")
@click.option("--pages", default=2, show_default=True, type=int, help="Max pages to fetch; 0 = all pages.")
@click.option("--per-page", default=100, show_default=True, type=int, help="Records per page (max 100).")
@click.option("--api-key", default=_DEFAULT_API_KEY, envvar="FEC_API_KEY", help="OpenFEC API key.")
@click.option("--no-cache", is_flag=True, help="Skip local cache and force a fresh API request.")
@click.option("--output-dir", default="output", show_default=True, type=click.Path(), help="Root output directory.")
def fetch(employer, min_date, max_date, pages, per_page, api_key, no_cache, output_dir):
    """Fetch FEC Schedule A contributions for EMPLOYER and write JSON + CSV to disk."""
    client = FECClient(api_key=api_key, no_cache=no_cache)
    max_pages = pages or None  # 0 → fetch all

    click.echo(f"Fetching Schedule A: employer={employer!r}  {min_date} → {max_date}  max_pages={max_pages or 'all'}")
    results = client.schedule_a_pages(employer, min_date, max_date, max_pages=max_pages, per_page=per_page)

    if not results:
        click.echo("No results returned.")
        return

    slug = re.sub(r"[^A-Za-z0-9]+", "_", employer).strip("_").upper()
    out_dir = Path(output_dir) / "schedule_a"
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = f"{slug}_{min_date}_{max_date}"

    json_path = out_dir / f"{stem}.json"
    csv_path = out_dir / f"{stem}.csv"

    json_path.write_text(json.dumps(results, indent=2))
    pd.DataFrame(results).to_csv(csv_path, index=False)

    click.echo(f"\nFetched {len(results):,} records.")
    click.echo(f"  JSON → {json_path}")
    click.echo(f"  CSV  → {csv_path}")

    df = pd.DataFrame(results)
    preview_cols = ["contributor_name", "contribution_receipt_amount", "contributor_state", "contributor_zip"]
    cols = [c for c in preview_cols if c in df.columns]
    if cols:
        click.echo(f"\nSample ({', '.join(cols)}):")
        click.echo(df[cols].head(5).to_string(index=False))


if __name__ == "__main__":
    fetch()
