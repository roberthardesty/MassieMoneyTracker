"""
FEC API Client for MassieMoney
Handles authentication, pagination, rate limiting, retry with exponential
backoff, and data retrieval from the OpenFEC API (https://api.open.fec.gov/v1/).
"""

import os
import time
import json
import logging
import requests
from typing import Optional, Iterator
from pathlib import Path

logger = logging.getLogger(__name__)

# Default to DEMO_KEY — register at https://api.data.gov/signup/ for 1000 req/hr
DEFAULT_API_KEY = os.environ.get("FEC_API_KEY", "DEMO_KEY")
BASE_URL = "https://api.open.fec.gov/v1"
MAX_PER_PAGE = 100

# Rate limiting: DEMO_KEY = 60/hr (~1/sec), registered key = 1000/hr (~0.28/sec)
# We use adaptive delays based on whether we're using DEMO_KEY or a real key.
DEMO_KEY_DELAY = 4.0       # 4s between requests for DEMO_KEY (safe for 60/hr)
REGISTERED_KEY_DELAY = 1.0  # 1s between requests for registered keys (safe for 1000/hr)

# Retry settings for 429 Too Many Requests
MAX_RETRIES = 5
INITIAL_BACKOFF = 10.0     # seconds to wait on first 429
BACKOFF_MULTIPLIER = 2.0   # double the wait each retry
MAX_BACKOFF = 120.0        # never wait more than 2 minutes


class FECClient:
    """Lightweight wrapper around the OpenFEC REST API with retry and backoff."""

    def __init__(self, api_key: str = DEFAULT_API_KEY):
        self.api_key = api_key
        self.session = requests.Session()
        self.session.params = {"api_key": self.api_key}
        self._last_request_time = 0.0
        self._request_count = 0

        # Startup diagnostic: show exactly what key we're using
        if api_key == "DEMO_KEY":
            self._delay = DEMO_KEY_DELAY
            logger.warning("╔══════════════════════════════════════════════════════════╗")
            logger.warning("║  Using DEMO_KEY — rate limited to 60 req/hr (4s delay)  ║")
            logger.warning("║  Get a free key at https://api.data.gov/signup/         ║")
            logger.warning("║  Then: export FEC_API_KEY='your-key-here'               ║")
            logger.warning("╚══════════════════════════════════════════════════════════╝")
        else:
            self._delay = REGISTERED_KEY_DELAY
            masked = f"{api_key[:6]}...{api_key[-4:]}" if len(api_key) > 10 else "***"
            logger.info(f"Using registered API key: {masked} (1000 req/hr, {REGISTERED_KEY_DELAY}s delay)")

    def _throttle(self):
        """Enforce minimum delay between requests to respect rate limits."""
        elapsed = time.time() - self._last_request_time
        if elapsed < self._delay:
            wait = self._delay - elapsed
            logger.debug(f"Throttling: waiting {wait:.1f}s")
            time.sleep(wait)
        self._last_request_time = time.time()

    def _get(self, endpoint: str, params: Optional[dict] = None) -> dict:
        """
        Make a single GET request to the FEC API with retry on 429.
        Uses exponential backoff when rate limited.
        """
        url = f"{BASE_URL}{endpoint}"
        last_error = None

        for attempt in range(MAX_RETRIES + 1):
            self._throttle()
            self._request_count += 1

            try:
                resp = self.session.get(url, params=params or {}, timeout=30)

                if resp.status_code == 429:
                    backoff = min(
                        INITIAL_BACKOFF * (BACKOFF_MULTIPLIER ** attempt),
                        MAX_BACKOFF
                    )
                    # Check for Retry-After header
                    retry_after = resp.headers.get("Retry-After")
                    if retry_after:
                        try:
                            backoff = max(float(retry_after), backoff)
                        except ValueError:
                            pass

                    logger.warning(
                        f"Rate limited (429) on attempt {attempt + 1}/{MAX_RETRIES + 1}. "
                        f"Waiting {backoff:.0f}s before retry... "
                        f"[{self._request_count} total requests]"
                    )
                    time.sleep(backoff)
                    last_error = requests.HTTPError(
                        f"429 Too Many Requests", response=resp
                    )
                    continue

                resp.raise_for_status()
                return resp.json()

            except requests.exceptions.ConnectionError as e:
                backoff = min(
                    INITIAL_BACKOFF * (BACKOFF_MULTIPLIER ** attempt),
                    MAX_BACKOFF
                )
                logger.warning(
                    f"Connection error on attempt {attempt + 1}/{MAX_RETRIES + 1}: {e}. "
                    f"Retrying in {backoff:.0f}s..."
                )
                time.sleep(backoff)
                last_error = e
                continue

            except requests.exceptions.Timeout as e:
                backoff = min(
                    INITIAL_BACKOFF * (BACKOFF_MULTIPLIER ** attempt),
                    MAX_BACKOFF
                )
                logger.warning(
                    f"Timeout on attempt {attempt + 1}/{MAX_RETRIES + 1}: {e}. "
                    f"Retrying in {backoff:.0f}s..."
                )
                time.sleep(backoff)
                last_error = e
                continue

        # All retries exhausted
        raise last_error or Exception(f"Failed after {MAX_RETRIES + 1} attempts for {endpoint}")

    def _paginate(self, endpoint: str, params: Optional[dict] = None) -> Iterator[dict]:
        """
        Yield all results from a paginated FEC endpoint.
        Uses cursor-based pagination via last_index fields when available,
        falls back to page-number pagination.
        """
        params = dict(params or {})
        params.setdefault("per_page", MAX_PER_PAGE)
        page = 1

        while True:
            params["page"] = page
            data = self._get(endpoint, params)
            results = data.get("results", [])
            if not results:
                break
            yield from results

            pagination = data.get("pagination", {})
            total_pages = pagination.get("pages", 1)
            if page >= total_pages:
                break
            page += 1
            logger.info(f"  Page {page}/{total_pages} for {endpoint}")

    # ──────────────────────────────────────────────
    # Candidate & Committee Lookups
    # ──────────────────────────────────────────────

    def get_candidate(self, candidate_id: str) -> dict:
        """Get candidate metadata."""
        data = self._get(f"/candidate/{candidate_id}/")
        return data.get("results", [{}])[0]

    def get_candidate_totals(self, candidate_id: str, cycle: int = 2026) -> list:
        """Get aggregated financial totals for a candidate."""
        return list(self._paginate(
            f"/candidate/{candidate_id}/totals/",
            {"cycle": cycle}
        ))

    def get_committee(self, committee_id: str) -> dict:
        """Get committee metadata."""
        data = self._get(f"/committee/{committee_id}/")
        return data.get("results", [{}])[0]

    def get_committee_totals(self, committee_id: str, cycle: int = 2026) -> list:
        """Get aggregated financial totals for a committee."""
        return list(self._paginate(
            f"/committee/{committee_id}/totals/",
            {"cycle": cycle}
        ))

    def search_committees(self, query: str, committee_type: Optional[str] = None) -> list:
        """
        Search for committees by name.
        committee_type: 'H' (House), 'S' (Senate), 'P' (Presidential),
                        'U' (Super PAC / IE-only), 'O' (Super PAC / hybrid), etc.
        """
        params = {"q": query, "per_page": 20}
        if committee_type:
            params["committee_type"] = committee_type
        return list(self._paginate("/committees/", params))

    def search_candidates(self, name: str, state: str = "KY",
                          district: str = "04", office: str = "H") -> list:
        """Search for candidates by name and district."""
        params = {
            "name": name,
            "state": state,
            "district": district,
            "office": office,
            "election_year": 2026,
            "per_page": 20,
        }
        return list(self._paginate("/candidates/search/", params))

    # ──────────────────────────────────────────────
    # Schedule A: Itemized Receipts (Donations)
    # ──────────────────────────────────────────────

    def get_receipts(self, committee_id: str, cycle: int = 2026,
                     min_date: Optional[str] = None,
                     max_date: Optional[str] = None,
                     min_amount: Optional[float] = None,
                     contributor_name: Optional[str] = None) -> Iterator[dict]:
        """
        Yield itemized receipts (Schedule A) for a committee.
        Only includes donations > $200 (FEC itemization threshold).
        """
        params = {
            "committee_id": committee_id,
            "two_year_transaction_period": cycle,
            "sort": "-contribution_receipt_date",
            "is_individual": True,
        }
        if min_date:
            params["min_date"] = min_date
        if max_date:
            params["max_date"] = max_date
        if min_amount:
            params["min_amount"] = min_amount
        if contributor_name:
            params["contributor_name"] = contributor_name
        return self._paginate("/schedules/schedule_a/", params)

    def get_receipts_by_size(self, committee_id: str, cycle: int = 2026) -> list:
        """Get receipts grouped by donation size bracket."""
        return list(self._paginate(
            "/schedules/schedule_a/by_size/",
            {"committee_id": committee_id, "cycle": cycle}
        ))

    def get_receipts_by_state(self, committee_id: str, cycle: int = 2026) -> list:
        """Get receipts grouped by contributor state."""
        return list(self._paginate(
            "/schedules/schedule_a/by_state/",
            {"committee_id": committee_id, "cycle": cycle}
        ))

    def get_receipts_by_zip(self, committee_id: str, cycle: int = 2026) -> list:
        """Get receipts grouped by contributor zip code."""
        return list(self._paginate(
            "/schedules/schedule_a/by_zip/",
            {"committee_id": committee_id, "cycle": cycle, "per_page": 100}
        ))

    # ──────────────────────────────────────────────
    # Schedule B: Itemized Disbursements (Spending)
    # ──────────────────────────────────────────────

    def get_disbursements(self, committee_id: str, cycle: int = 2026) -> Iterator[dict]:
        """Yield itemized disbursements (Schedule B) for a committee."""
        return self._paginate(
            "/schedules/schedule_b/",
            {
                "committee_id": committee_id,
                "two_year_transaction_period": cycle,
                "sort": "-disbursement_date",
            }
        )

    # ──────────────────────────────────────────────
    # Schedule E: Independent Expenditures
    # ──────────────────────────────────────────────

    def get_independent_expenditures(
        self,
        candidate_id: Optional[str] = None,
        committee_id: Optional[str] = None,
        cycle: int = 2026,
        support_oppose: Optional[str] = None,
        min_date: Optional[str] = None,
        max_date: Optional[str] = None,
    ) -> Iterator[dict]:
        """
        Yield independent expenditure filings (Schedule E).
        support_oppose: 'S' (support) or 'O' (oppose)
        """
        params = {
            "cycle": cycle,
            "sort": "-expenditure_date",
        }
        if candidate_id:
            params["candidate_id"] = candidate_id
        if committee_id:
            params["committee_id"] = committee_id
        if support_oppose:
            params["support_oppose_indicator"] = support_oppose
        if min_date:
            params["min_date"] = min_date
        if max_date:
            params["max_date"] = max_date
        return self._paginate("/schedules/schedule_e/", params)

    def get_recent_ie_filings(
        self,
        candidate_id: Optional[str] = None,
        committee_id: Optional[str] = None,
    ) -> Iterator[dict]:
        """
        Yield recent e-filed independent expenditures (24/48 hour reports).
        These are the most up-to-date IE filings available.
        """
        params = {"sort": "-receipt_date", "per_page": MAX_PER_PAGE}
        if candidate_id:
            params["candidate_id"] = candidate_id
        if committee_id:
            params["committee_id"] = committee_id
        return self._paginate("/schedules/schedule_e/efile/", params)

    # ──────────────────────────────────────────────
    # Election Overview
    # ──────────────────────────────────────────────

    def get_election(self, state: str = "KY", district: str = "04",
                     cycle: int = 2026, office: str = "house") -> list:
        """Get election overview including all candidates and their totals."""
        return list(self._paginate(
            f"/elections/",
            {
                "state": state,
                "district": district,
                "cycle": cycle,
                "office": office,
            }
        ))

    # ──────────────────────────────────────────────
    # Utility
    # ──────────────────────────────────────────────

    def save_json(self, data, filepath: str):
        """Save data to a JSON file."""
        path = Path(filepath)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            json.dump(data, f, indent=2, default=str)
        logger.info(f"Saved {path} ({path.stat().st_size:,} bytes)")


# ──────────────────────────────────────────────
# Quick-run: Committee ID lookup
# ──────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    client = FECClient()

    print("=" * 60)
    print("MassieMoney — FEC Committee ID Lookup")
    print("=" * 60)

    # Look up known committees
    known = {
        "Thomas Massie for Congress": "C00509729",
        "Protect Freedom PAC": "C00657866",
    }
    for name, cid in known.items():
        info = client.get_committee(cid)
        print(f"\n✓ {name} ({cid})")
        print(f"  Type: {info.get('committee_type_full', 'N/A')}")
        print(f"  Designation: {info.get('designation_full', 'N/A')}")
        print(f"  Treasurer: {info.get('treasurer_name', 'N/A')}")

    # Search for unknown committees
    searches = [
        ("Gallrein", None),
        ("Kentucky First", "U"),   # U = Super PAC / IE-only
        ("MAGA KY", "U"),
        ("MAGA Kentucky", "U"),
        ("Preserve America", "U"),
    ]

    print("\n" + "=" * 60)
    print("Searching for committees...")
    print("=" * 60)

    for query, ctype in searches:
        results = client.search_committees(query, ctype)
        print(f"\nSearch: '{query}' (type={ctype})")
        if not results:
            print("  No results found")
        for r in results[:5]:
            print(f"  → {r['name']} ({r['committee_id']})")
            print(f"    Type: {r.get('committee_type_full', 'N/A')}")
            print(f"    State: {r.get('state', 'N/A')}")
            print(f"    Cycles: {r.get('cycles', [])}")

    # Search for Gallrein as a candidate
    print("\n" + "=" * 60)
    print("Searching for Gallrein as candidate...")
    print("=" * 60)
    candidates = client.search_candidates("Gallrein")
    for c in candidates:
        print(f"  → {c['name']} ({c['candidate_id']})")
        print(f"    Party: {c.get('party_full', 'N/A')}")
        print(f"    Office: {c.get('office_full', 'N/A')}")
        print(f"    District: {c.get('state', '')}-{c.get('district', '')}")
        print(f"    Committee ID: {c.get('principal_committees', [{}])[0].get('committee_id', 'N/A') if c.get('principal_committees') else 'N/A'}")
