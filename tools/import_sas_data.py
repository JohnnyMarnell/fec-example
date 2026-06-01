#!/usr/bin/env python3
"""Import small data files from the private sas-fork repo into ours.

Source: ../sas-fork/files-from-ftp-server/  (must be `git lfs pull`ed first)
Destination: csv/   (the existing convention: `.xlsx.csv` for converted Excel files)

Files brought over:

  Fortune 500 2021 List.xlsx          → csv/Fortune500_2021.xlsx.csv
                                        (single sheet, cleaned)

  GovernmentAgenciesSortedAssigned.xlsx → csv/GovernmentAgencies.xlsx
                                          (38 sheets, complex layout — kept raw)

  bod-xlsx/<Company>BOD.xlsx          → csv/bod/<Company>BOD.xlsx
                                        (multi-sheet: roster + per-member FEC)
  + a consolidated roster:            → csv/boards_roster.xlsx.csv
                                        (one row per board member across all companies)

Re-run anytime sas-fork is updated:
    just lfs-pull-needed && uv run python tools/import_sas_data.py
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

import pandas as pd

FEC_ROOT = Path(__file__).resolve().parent.parent
SAS_FORK = FEC_ROOT.parent / "sas-fork" / "files-from-ftp-server"

CSV_DIR   = FEC_ROOT / "csv"
BOD_DIR   = CSV_DIR / "bod"


def fortune_500() -> None:
    src = SAS_FORK / "Fortune 500 2021 List.xlsx"
    if src.stat().st_size < 1000:
        print(f"  ! {src.name} is still an LFS pointer — run `git lfs pull` in sas-fork first")
        return

    # The 'Fortune 500' sheet bundles a workbook-tracker (Mark/Matt/Mitchell
    # assignment columns + an alphabetic copy) into the same grid as the actual
    # data. Strip down to the three useful columns.
    raw = pd.read_excel(src, sheet_name="Fortune 500")
    raw.columns = [str(c).replace("\n", " ").strip() for c in raw.columns]
    keep = [c for c in raw.columns if c in {"Rank", "Company Name", "Number of Employees"}]
    df = (
        raw[keep]
        .dropna(subset=["Rank"])
        .copy()
    )
    df["Rank"] = pd.to_numeric(df["Rank"], errors="coerce").astype("Int64")
    df = df.dropna(subset=["Rank"]).sort_values("Rank").reset_index(drop=True)

    out = CSV_DIR / "Fortune500_2021.xlsx.csv"
    df.to_csv(out, index=False)
    print(f"  ✓ Fortune 500 → {out.relative_to(FEC_ROOT)}  ({len(df)} rows × {df.shape[1]} cols)")


def government_agencies() -> None:
    """Keep raw — 38 sheets, idiosyncratic layouts."""
    src = SAS_FORK / "GovernmentAgenciesSortedAssigned.xlsx"
    if src.stat().st_size < 1000:
        print(f"  ! {src.name} is still an LFS pointer — run `git lfs pull` in sas-fork first")
        return
    dst = CSV_DIR / "GovernmentAgencies.xlsx"
    shutil.copy(src, dst)
    print(f"  ✓ GovernmentAgencies → {dst.relative_to(FEC_ROOT)}  ({src.stat().st_size // 1024} KB raw)")

    # Also produce a flat "agency code → display name" CSV from the sheet names,
    # which encode the (code, owner) pairing used by the SAS analysts.
    sheets = pd.ExcelFile(src).sheet_names
    rows = []
    for s in sheets:
        # Sheet name format: "<AgencyCode>FECG <Owner>" or "<AgencyCode>FEC <Owner>"
        # e.g. "SBAFECG Mark", "DOInteriorFECG Mark"
        name = s
        for suffix in ["FECG ", "FEC "]:
            if suffix in name:
                code, _, owner = name.partition(suffix)
                rows.append({"agency_code": code.strip(), "sheet": s, "owner": owner.strip()})
                break
        else:
            rows.append({"agency_code": name.strip(), "sheet": s, "owner": ""})
    agencies = pd.DataFrame(rows)
    out = CSV_DIR / "GovernmentAgencies.xlsx.csv"
    agencies.to_csv(out, index=False)
    print(f"  ✓ Agencies index → {out.relative_to(FEC_ROOT)}  ({len(agencies)} agencies)")


def bod_files() -> None:
    src_dir = SAS_FORK / "bod-xlsx"
    BOD_DIR.mkdir(parents=True, exist_ok=True)

    # Files larger than this stay in sas-fork only — they contain per-member FEC
    # contribution sheets that bloat each workbook to multiple MB. The roster
    # extraction still walks them (so the consolidated roster has full coverage).
    SIZE_THRESHOLD_BYTES = 500_000

    rosters = []
    copied = 0
    skipped_lfs = 0
    skipped_big = 0
    for src in sorted(src_dir.glob("*.xlsx")):
        size = src.stat().st_size
        if size < 1000:
            print(f"  ! {src.name} still an LFS pointer; skipping")
            skipped_lfs += 1
            continue

        if size <= SIZE_THRESHOLD_BYTES:
            shutil.copy(src, BOD_DIR / src.name)
            copied += 1
        else:
            print(f"  • {src.name} ({size // 1024} KB) > {SIZE_THRESHOLD_BYTES // 1024} KB — roster only, raw stays in sas-fork")
            skipped_big += 1

        # Always extract the roster — every BOD file has a "Board & Executives"
        # (or "Board & Executives Summary" or "<Company>BOD") sheet with the same
        # column shape: Company, Board, Exec, Employer, Fname, MI, Lname, …
        try:
            xls = pd.ExcelFile(src)
            chosen = None
            for s in xls.sheet_names:
                cl = s.lower()
                if "board" in cl or cl.endswith("bod") or "summary" in cl or "roster" in cl:
                    chosen = s
                    break
            if chosen is None:
                chosen = xls.sheet_names[0]
            df = pd.read_excel(src, sheet_name=chosen)
            if "Lname" in df.columns:
                df["source_file"] = src.name
                df["source_sheet"] = chosen
                rosters.append(df)
            else:
                print(f"  ! {src.name}: '{chosen}' missing Lname; skipping roster")
        except Exception as e:
            print(f"  ! roster parse failed for {src.name}: {e}")

    print(f"  ✓ BOD raw → {BOD_DIR.relative_to(FEC_ROOT)}/  "
          f"({copied} copied, {skipped_big} stayed in sas-fork, {skipped_lfs} LFS-stub)")

    if rosters:
        # Union all rosters — columns won't be perfectly aligned but pandas handles it.
        combined = pd.concat(rosters, ignore_index=True)
        # Lowercase + normalize the most useful columns
        keep = [c for c in ["Company", "Board", "Exec", "Employer", "Fname", "MI",
                            "Lname", "Title", "Position", "source_file"]
                if c in combined.columns]
        roster = combined[keep].dropna(subset=["Lname"])
        out = CSV_DIR / "boards_roster.xlsx.csv"
        roster.to_csv(out, index=False)
        print(f"  ✓ Combined roster → {out.relative_to(FEC_ROOT)}  ({len(roster)} board members across {roster['source_file'].nunique()} files)")


def main() -> int:
    if not SAS_FORK.exists():
        print(f"sas-fork not found at {SAS_FORK}")
        return 1

    print(f"Importing from {SAS_FORK} → {CSV_DIR}\n")
    print("Fortune 500:")
    fortune_500()
    print("\nGovernment Agencies:")
    government_agencies()
    print("\nBoards of Directors:")
    bod_files()
    print("\nDone.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
