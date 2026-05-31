"""FEC API client with transparent disk caching.

Caching requires concrete date ranges on every request so that cached responses
remain valid — historical FEC data does not change, making date-bounded requests
safe to cache indefinitely.
"""
import hashlib
import json
from pathlib import Path
from urllib.parse import urlencode

import requests

BASE_URL = "https://api.open.fec.gov/v1"
DEFAULT_TIMEOUT = (10, 30)  # (connect, read) — FEC sometimes stalls on Schedule B


class FECClient:
    def __init__(
        self,
        api_key: str,
        cache_dir: str = "cache",
        no_cache: bool = False,
        timeout: tuple[float, float] = DEFAULT_TIMEOUT,
        quiet: bool = False,
    ):
        self.api_key = api_key
        self.no_cache = no_cache
        self.cache_dir = Path(cache_dir)
        self._index_path = self.cache_dir / "index.json"
        self.timeout = timeout
        self.quiet = quiet

    def _log(self, msg: str) -> None:
        if not self.quiet:
            print(msg)

    # -- cache internals -------------------------------------------------------

    def _canonical(self, endpoint: str, params: dict) -> str:
        """Stable, human-readable key from endpoint + sorted params."""
        return f"{endpoint}?{urlencode(sorted(params.items()))}"

    def _hash(self, canonical: str) -> str:
        return hashlib.sha256(canonical.encode()).hexdigest()[:20]

    def _load_index(self) -> dict:
        if self._index_path.exists():
            return json.loads(self._index_path.read_text())
        return {}

    def _save_index(self, index: dict) -> None:
        self._index_path.write_text(json.dumps(index, indent=2))

    def _cache_get(self, canonical: str) -> dict | None:
        index = self._load_index()
        if canonical not in index:
            return None
        cached_path = self.cache_dir / index[canonical]
        if not cached_path.exists():
            return None
        return json.loads(cached_path.read_text())

    def _cache_put(self, canonical: str, data: dict) -> None:
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        filename = f"{self._hash(canonical)}.json"
        (self.cache_dir / filename).write_text(json.dumps(data))
        index = self._load_index()
        index[canonical] = filename
        self._save_index(index)

    # -- HTTP ------------------------------------------------------------------

    def _get(self, endpoint: str, params: dict) -> dict:
        canonical = self._canonical(endpoint, params)

        if not self.no_cache:
            cached = self._cache_get(canonical)
            if cached is not None:
                self._log(f"  [cache] {canonical[:100]}")
                return cached

        url = f"{BASE_URL}{endpoint}"
        headers = {"X-Api-Key": self.api_key, "Accept": "application/json"}
        resp = requests.get(url, headers=headers, params=params, timeout=self.timeout)
        resp.raise_for_status()
        data = resp.json()

        if not self.no_cache:
            self._cache_put(canonical, data)

        return data

    # -- public API ------------------------------------------------------------

    def schedule_a(
        self,
        contributor_employer: str,
        min_date: str,
        max_date: str,
        page: int = 1,
        per_page: int = 100,
        sort: str = "-contribution_receipt_date",
    ) -> dict:
        """Single page of Schedule A contributions for an employer."""
        return self._get(
            "/schedules/schedule_a/",
            {
                "contributor_employer": contributor_employer,
                "min_date": min_date,
                "max_date": max_date,
                "per_page": per_page,
                "sort": sort,
                "page": page,
            },
        )

    def schedule_a_pages(
        self,
        contributor_employer: str,
        min_date: str,
        max_date: str,
        max_pages: int | None = None,
        per_page: int = 100,
    ) -> list[dict]:
        """All pages of Schedule A contributions, up to max_pages (None = all)."""
        all_results: list[dict] = []
        page = 1
        while True:
            data = self.schedule_a(
                contributor_employer, min_date, max_date, page=page, per_page=per_page
            )
            batch = data.get("results", [])
            all_results.extend(batch)
            total_pages = data.get("pagination", {}).get("pages", 1)
            self._log(f"  page {page}/{total_pages}: {len(batch)} records  (total: {len(all_results)})")
            if page >= total_pages or (max_pages is not None and page >= max_pages):
                break
            page += 1
        return all_results

    # -- Schedule B (committee disbursements — "where did the PAC spend?") ----

    def schedule_b(
        self,
        committee_id: str,
        min_date: str,
        max_date: str,
        page: int = 1,
        per_page: int = 100,
        sort: str = "-disbursement_date",
    ) -> dict:
        """Single page of Schedule B (itemized disbursements) for one committee."""
        return self._get(
            "/schedules/schedule_b/",
            {
                "committee_id": committee_id,
                "min_date": min_date,
                "max_date": max_date,
                "per_page": per_page,
                "sort": sort,
                "page": page,
            },
        )

    def schedule_b_pages(
        self,
        committee_id: str,
        min_date: str,
        max_date: str,
        max_pages: int | None = None,
        per_page: int = 100,
    ) -> list[dict]:
        """All pages of Schedule B disbursements, up to max_pages (None = all).

        Surfaces network timeouts as `requests.exceptions.RequestException`
        rather than hanging — callers can swallow and continue.
        """
        all_results: list[dict] = []
        page = 1
        while True:
            data = self.schedule_b(
                committee_id, min_date, max_date, page=page, per_page=per_page
            )
            batch = data.get("results", [])
            all_results.extend(batch)
            total_pages = data.get("pagination", {}).get("pages", 1)
            self._log(f"  schedule_b page {page}/{total_pages}: {len(batch)} records  (total: {len(all_results)})")
            if page >= total_pages or (max_pages is not None and page >= max_pages):
                break
            page += 1
        return all_results

    # -- Committees (authoritative committee metadata) ------------------------

    def committee(self, committee_id: str) -> dict:
        """Single committee — authoritative party/type/designation lookup."""
        return self._get(f"/committee/{committee_id}/", {})

    # -- Candidates (candidate metadata — includes party_full) ----------------

    def candidate(self, candidate_id: str) -> dict:
        """Single candidate — authoritative party / office / cycle lookup."""
        return self._get(f"/candidate/{candidate_id}/", {})
