#!/usr/bin/env python3
"""
FEC API Demo - Fetch Schedule A data from OpenFEC API
Fetches 2 pages of contribution data and saves to CSV
"""
import requests
import pandas as pd

# API Configuration
API_KEY = "Kgkivmpbsy1rehiCuTcd8gVHxzwQFRcSDsrVhQJm"
BASE_URL = "https://api.open.fec.gov/v1/schedules/schedule_a/"
OUTPUT_FILE = "tmp-API-FETCH-TracktorSupplyFEC.csv"

# Query parameters
PARAMS = {
    "contributor_employer": "TRACTOR SUPPLY",
    "min_date": "2019-01-01",
    "max_date": "2020-12-31",
    "per_page": 100,
    "sort": "-contribution_receipt_date"
}

HEADERS = {
    "X-Api-Key": API_KEY,
    "Accept": "application/json"
}


def fetch_page(page_number):
    """Fetch a single page of data from the FEC API."""
    print(f"Fetching page {page_number}...")

    params = PARAMS.copy()
    params["page"] = page_number

    try:
        params_str = '&'.join(f'{k}={v}' for k,v in params.items())
        print(f"Calling FEC API:\nGET {BASE_URL}?{params_str}")
        response = requests.get(BASE_URL, headers=HEADERS, params=params)
        response.raise_for_status()

        data = response.json()
        results = data.get("results", [])

        print(f"Page {page_number}: Retrieved {len(results)} records")
        print(f"Page {page_number}: Total available: {data.get('pagination', {}).get('count', 'unknown')}")

        return results

    except requests.exceptions.RequestException as e:
        print(f"ERROR: Error fetching page {page_number}: {e}")
        raise


def main():
    """Fetch 2 pages of FEC data, combine, and save to CSV."""
    print("Starting FEC API data fetch, will fetch first 2 pages")
    print(f"Employer: {PARAMS['contributor_employer']}")
    print(f"Date range: {PARAMS['min_date']} to {PARAMS['max_date']}")

    # Fetch 2 pages
    all_results = []
    for page in range(1, 3):
        page_results = fetch_page(page)
        all_results.extend(page_results)

    # Convert to DataFrame
    if not all_results:
        print("WARNING: No data retrieved from API")
        return

    df = pd.DataFrame(all_results)
    print(f"DataFrame shape: {df.shape}")
    print(f"Columns: {len(df.columns)}")

    # Write to CSV
    df.to_csv(OUTPUT_FILE, index=False)
    print(f"Data written to: {OUTPUT_FILE}")

    # Pretty print first 10 rows
    print("\n" + "=" * 100)
    print(f"FIRST 10 ROWS, SOME COLUMNS (see {OUTPUT_FILE})")
    print("=" * 100)

    # Show a few columns and rows - find columns containing these keywords
    cols = "contributor_name contribution_receipt_amount contributor_state contributor_zip".split(" ")
    print(df[cols].head(10).to_string(index=False))

    print("=" * 100)
    print(f"\nFull data saved to: {OUTPUT_FILE}")
    print(f"Total columns in dataset: {len(df.columns)}")


if __name__ == "__main__":
    main()
