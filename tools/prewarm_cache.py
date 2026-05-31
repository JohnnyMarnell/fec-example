#!/usr/bin/env python3
"""Pre-warm the local FEC API cache for the cross-company notebook.

Hits every endpoint the notebook will need:

  1. /schedules/schedule_a/ — one per (employer, page)
  2. /schedules/schedule_b/ — one per (top-recipient committee_id, page)
  3. /committee/{id}/        — one per top-N "fell-through" committee
  4. /candidate/{id}/        — one per top-N Schedule B recipient candidate

Idempotent: anything already on disk is served from cache (free, no API call).
Tolerant: any one failure is logged and skipped; the script keeps going so the
notebook still has *most* of what it needs.

Run:
    uv run python tools/prewarm_cache.py
"""
from __future__ import annotations

import os
import sys
from collections import Counter
from pathlib import Path

import pandas as pd

# project root on the path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fec_client import FECClient


# Keep in sync with notebooks/cross-company.ipynb cell 2 (Configuration)
COMPANIES = [
    "TRACTOR SUPPLY",
    "MICROSOFT",
    "EXXON MOBIL",
    "WALMART",
    "LOCKHEED MARTIN",
]
MIN_DATE          = "2019-01-01"
MAX_DATE          = "2020-12-31"
PAGES_PER_COMPANY = 2
TOP_FELL_THROUGH  = 8
TOP_CANDIDATES    = 20

_DEFAULT_API_KEY = "Kgkivmpbsy1rehiCuTcd8gVHxzwQFRcSDsrVhQJm"


def section(title: str) -> None:
    print(f"\n── {title} {'─' * (74 - len(title))}")


def fetch_schedule_a(client: FECClient) -> pd.DataFrame:
    """Phase 1: pull Schedule A for every employer. Returns the combined DF."""
    frames: list[pd.DataFrame] = []
    for employer in COMPANIES:
        print(f"• {employer}")
        try:
            records = client.schedule_a_pages(
                employer, MIN_DATE, MAX_DATE, max_pages=PAGES_PER_COMPANY,
            )
        except Exception as e:
            print(f"   ! skip — {type(e).__name__}: {e}")
            continue
        if not records:
            print("   ! no rows")
            continue
        df = pd.DataFrame(records)
        df["company"] = employer
        # Flatten the embedded committee.party for the fell-through detection.
        cmte = df.get("committee").apply(lambda c: c if isinstance(c, dict) else {})
        df["committee_party_embedded"] = cmte.apply(lambda c: c.get("party"))
        frames.append(df)
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


def fetch_schedule_b_for_top_recipients(client: FECClient, raw: pd.DataFrame) -> list[dict]:
    """Phase 2: for each company, find its top recipient and fetch its Schedule B.

    Returns the combined Schedule B record list so phase 4 can walk candidates.
    """
    sb_records: list[dict] = []
    if raw.empty:
        return sb_records
    # Aggregate per (company, committee_id) and take the top.
    g = (
        raw.assign(
            amount=raw["contribution_receipt_amount"].fillna(0)
        )
        .groupby(["company", "committee_id", "committee_name"], dropna=False)
        ["amount"].sum()
        .reset_index()
        .sort_values("amount", ascending=False)
        .groupby("company", sort=False)
        .head(1)
    )
    for _, row in g.iterrows():
        cid     = row["committee_id"]
        if not isinstance(cid, str) or not cid:
            print(f"• {row['company']:>18s} — no committee_id, skipping")
            continue
        cname   = (row["committee_name"] or "")[:60] if isinstance(row["committee_name"], str) else ""
        print(f"• {row['company']:>18s} → {cid}  ({cname})")
        try:
            records = client.schedule_b_pages(
                cid, MIN_DATE, MAX_DATE, max_pages=PAGES_PER_COMPANY,
            )
            sb_records.extend(records)
            print(f"   ✓ {len(records):,} disbursements")
        except Exception as e:
            print(f"   ! {type(e).__name__}: {e}")
    return sb_records


def fetch_candidate_lookups(client: FECClient, sb_records: list[dict]) -> None:
    """Phase 4: top-N candidates by $ across all Schedule B records — look them up."""
    if not sb_records:
        print("(no Schedule B records — nothing to enrich)")
        return
    sb = pd.DataFrame(sb_records)
    if "candidate_id" not in sb.columns:
        print("(Schedule B sample has no candidate_id column)")
        return
    top = (
        sb[sb["candidate_id"].notna()]
        .groupby("candidate_id")["disbursement_amount"].sum()
        .nlargest(TOP_CANDIDATES)
    )
    if top.empty:
        print("(no candidate_id values to enrich)")
        return
    for cand_id, total in top.items():
        print(f"• /candidate/{cand_id}/   ${total:,.0f} received")
        try:
            data = client.candidate(cand_id)
            hits = data.get("results") or []
            if hits:
                h = hits[0]
                print(f"   ✓ {h.get('name','?'):<35.35s}  party={h.get('party') or '—'}  "
                      f"office={h.get('office_full','—'):<10.10s}  state={h.get('state','—')}")
            else:
                print("   ✓ (no metadata returned)")
        except Exception as e:
            print(f"   ! {type(e).__name__}: {e}")


def fetch_committee_lookups(client: FECClient, raw: pd.DataFrame) -> None:
    """Phase 3: top-N committees whose embedded party is null → look them up."""
    if raw.empty:
        return
    null_party = raw[raw["committee_party_embedded"].isna()]
    if null_party.empty:
        print("(no null-party rows — nothing to fill in)")
        return
    counts = Counter(null_party["committee_id"].dropna())
    top = [cid for cid, _ in counts.most_common(TOP_FELL_THROUGH) if isinstance(cid, str)]
    for cid in top:
        print(f"• /committee/{cid}/")
        try:
            data = client.committee(cid)
            hits = data.get("results") or []
            if hits:
                hit = hits[0]
                print(f"   ✓ {hit.get('name','?'):<50.50s}  party={hit.get('party') or '—'}")
            else:
                print("   ✓ (no metadata returned)")
        except Exception as e:
            print(f"   ! {type(e).__name__}: {e}")


def main() -> None:
    api_key = os.environ.get("FEC_API_KEY", _DEFAULT_API_KEY)
    client  = FECClient(api_key=api_key)

    print("Pre-warming FEC API cache for notebooks/cross-company.ipynb")
    print(f"  date range : {MIN_DATE} → {MAX_DATE}")
    print(f"  companies  : {', '.join(COMPANIES)}")
    print(f"  pages each : {PAGES_PER_COMPANY}")

    section("1/4  Schedule A — per-employer individual contributions")
    raw = fetch_schedule_a(client)
    if raw.empty:
        print("\nNo Schedule A data fetched — aborting.")
        return
    print(f"\n  combined : {len(raw):,} rows · "
          f"{raw['company'].nunique()} companies · "
          f"{raw['committee_id'].nunique():,} distinct committees")

    section("2/4  Schedule B — disbursements from each company's top recipient")
    sb_records = fetch_schedule_b_for_top_recipients(client, raw)

    section("3/4  /committee/{id}/ — fill in null-party committees")
    fetch_committee_lookups(client, raw)

    section("4/4  /candidate/{id}/ — enrich Schedule B recipients with party + office")
    fetch_candidate_lookups(client, sb_records)

    print("\n✓ Cache pre-warm complete. Run `just notebook` next.")


if __name__ == "__main__":
    main()
