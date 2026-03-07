"""
MassieMoney — ETL Ingestion Pipeline
Pulls data from the FEC API and loads it into the local SQLite database.
Supports checkpointing and resume so partial runs can pick up where they left off.

Usage:
    python ingest.py                    # Full ingest (resumes from last checkpoint)
    python ingest.py --fresh            # Ignore checkpoints, start from scratch
    python ingest.py --committees-only  # Just refresh committee metadata & totals
    python ingest.py --ie-only          # Just refresh independent expenditures
    python ingest.py --lookup           # Look up missing committee IDs
    python ingest.py --status           # Show checkpoint status

Set FEC_API_KEY env var for higher rate limits (1000 req/hr vs 60/hr with DEMO_KEY).
Set MASSIEMONEY_DATA_DIR env var to control where the SQLite DB lives.
"""

import argparse
import json
import logging
import sys
from datetime import datetime
from pathlib import Path

from fec_client import FECClient
from database import init_db, upsert_committee, upsert_receipt, \
    upsert_independent_expenditure, upsert_disbursement
from config import (
    PRO_MASSIE_COMMITTEES, ANTI_MASSIE_COMMITTEES, WATCHLIST_COMMITTEES,
    CANDIDATES, CYCLE, all_tracked_committees, DATA_DIR
)

logger = logging.getLogger("massiemoney.ingest")


# ──────────────────────────────────────────────
# Checkpoint System
# ──────────────────────────────────────────────
CHECKPOINT_FILE = DATA_DIR / "checkpoint.json"

# Pipeline steps in execution order. Each is a (phase_name, description) tuple.
PIPELINE_STEPS = [
    ("committees",        "Committee Metadata & Totals"),
    ("ie_massie",         "Independent Expenditures targeting Massie"),
    ("ie_gallrein",       "Independent Expenditures targeting Gallrein"),
    ("ie_pac_maga_ky",    "Independent Expenditures from MAGA KY"),
    ("ie_pac_ky_first",   "Independent Expenditures from Kentucky First PAC"),
    ("agg_by_size",       "Receipts Aggregates by Size"),
    ("agg_by_state",      "Receipts Aggregates by State"),
    ("receipts_massie",   "Itemized Receipts — Massie Campaign"),
    ("receipts_gallrein", "Itemized Receipts — Gallrein Campaign"),
    ("receipts_maga_ky",  "Itemized Receipts — MAGA KY"),
    ("disb_massie",       "Disbursements — Massie Campaign"),
    ("disb_gallrein",     "Disbursements — Gallrein Campaign"),
    ("disb_maga_ky",      "Disbursements — MAGA KY"),
]


def load_checkpoint() -> dict:
    """Load checkpoint state from disk. Returns dict of completed steps."""
    if CHECKPOINT_FILE.exists():
        try:
            with open(CHECKPOINT_FILE) as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return {"completed_steps": [], "last_run": None, "errors": {}}


def save_checkpoint(state: dict):
    """Save checkpoint state to disk."""
    CHECKPOINT_FILE.parent.mkdir(parents=True, exist_ok=True)
    state["last_run"] = datetime.now().isoformat()
    with open(CHECKPOINT_FILE, "w") as f:
        json.dump(state, f, indent=2)


def mark_step_done(state: dict, step_name: str):
    """Mark a pipeline step as completed and persist."""
    if step_name not in state["completed_steps"]:
        state["completed_steps"].append(step_name)
    # Clear any previous error for this step
    state["errors"].pop(step_name, None)
    save_checkpoint(state)


def mark_step_error(state: dict, step_name: str, error: str):
    """Record an error for a pipeline step (doesn't mark it complete)."""
    state["errors"][step_name] = {
        "error": str(error),
        "timestamp": datetime.now().isoformat(),
    }
    save_checkpoint(state)


def should_run(state: dict, step_name: str) -> bool:
    """Check if a step should run (not yet completed in checkpoint)."""
    return step_name not in state["completed_steps"]


def print_status():
    """Print the current checkpoint status."""
    state = load_checkpoint()
    print("=" * 60)
    print("MassieMoney — Pipeline Checkpoint Status")
    print(f"Last run: {state.get('last_run', 'Never')}")
    print("=" * 60)

    for step_name, description in PIPELINE_STEPS:
        if step_name in state["completed_steps"]:
            status = "✓ DONE"
        elif step_name in state.get("errors", {}):
            err = state["errors"][step_name]
            status = f"✗ ERROR: {err['error'][:60]}"
        else:
            status = "○ PENDING"
        print(f"  {status:20s}  {description}")

    print("=" * 60)
    completed = len(state["completed_steps"])
    total = len(PIPELINE_STEPS)
    print(f"Progress: {completed}/{total} steps complete")
    if completed == total:
        print("Pipeline fully complete! Use --fresh to re-run from scratch.")
    else:
        print("Run 'python ingest.py' to resume from where you left off.")


# ──────────────────────────────────────────────
# Ingestion Functions
# ──────────────────────────────────────────────

def ingest_committee_metadata(client: FECClient, conn):
    """Pull committee metadata and financial totals from FEC API."""
    committees = all_tracked_committees()

    for key, info in committees.items():
        cid = info["committee_id"]
        if not cid:
            logger.warning(f"Skipping {info['name']} — no committee_id yet (needs manual lookup)")
            continue

        logger.info(f"Fetching committee: {info['name']} ({cid})")

        # Get metadata
        try:
            meta = client.get_committee(cid)
        except Exception as e:
            logger.error(f"  Failed to fetch metadata for {cid}: {e}")
            continue

        # Get financial totals
        totals = {}
        try:
            totals_list = client.get_committee_totals(cid, cycle=CYCLE)
            if totals_list:
                totals = totals_list[0]
        except Exception as e:
            logger.warning(f"  No totals for {cid}: {e}")

        record = {
            "committee_id": cid,
            "name": meta.get("name", info["name"]),
            "committee_type": meta.get("committee_type", ""),
            "committee_type_full": meta.get("committee_type_full", ""),
            "designation": meta.get("designation", ""),
            "designation_full": meta.get("designation_full", ""),
            "treasurer_name": meta.get("treasurer_name", ""),
            "state": meta.get("state", ""),
            "party": meta.get("party", ""),
            "filing_frequency": meta.get("filing_frequency", ""),
            "organization_type": meta.get("organization_type", ""),
            "side": info.get("group", ""),
            "local_key": key,
            "description": info.get("description", ""),
            "total_receipts": totals.get("receipts", 0) or 0,
            "total_disbursements": totals.get("disbursements", 0) or 0,
            "total_independent_exp": totals.get("independent_expenditures", 0) or 0,
            "cash_on_hand": totals.get("last_cash_on_hand_end_period", 0) or 0,
            "debt": totals.get("last_debts_owed_by_committee", 0) or 0,
            "coverage_start_date": totals.get("coverage_start_date", ""),
            "coverage_end_date": totals.get("coverage_end_date", ""),
        }

        upsert_committee(conn, record)
        logger.info(f"  ✓ {info['name']}: receipts=${record['total_receipts']:,.0f}, "
                     f"disbursements=${record['total_disbursements']:,.0f}, "
                     f"COH=${record['cash_on_hand']:,.0f}")

    conn.commit()


def _ingest_ie_for_target(client, conn, candidate_id=None, committee_id=None, label=""):
    """Pull independent expenditures for a specific candidate or from a specific committee."""
    logger.info(f"Fetching IEs: {label}")
    count = 0

    for ie in client.get_independent_expenditures(
        candidate_id=candidate_id, committee_id=committee_id, cycle=CYCLE
    ):
        record = {
            "sub_id": ie.get("sub_id", f"ie_{count}"),
            "committee_id": ie.get("committee_id", committee_id or ""),
            "committee_name": (
                ie.get("committee", {}).get("name", "")
                if isinstance(ie.get("committee"), dict)
                else ie.get("committee_name", "")
            ),
            "candidate_id": ie.get("candidate_id", ""),
            "candidate_name": ie.get("candidate_name", ""),
            "support_oppose_indicator": ie.get("support_oppose_indicator", ""),
            "expenditure_amount": ie.get("expenditure_amount", 0),
            "expenditure_date": ie.get("expenditure_date", ""),
            "expenditure_description": ie.get("expenditure_description", ""),
            "payee_name": ie.get("payee_name", ""),
            "payee_state": ie.get("payee_state", ""),
            "purpose": ie.get("category_code_full", ""),
            "filing_date": ie.get("filing_date", ""),
            "pdf_url": ie.get("pdf_url", ""),
            "memo_text": ie.get("memo_text", ""),
            "cycle": CYCLE,
        }
        upsert_independent_expenditure(conn, record)
        count += 1

        if count % 50 == 0:
            conn.commit()
            logger.info(f"  ... {count} IEs so far")

    conn.commit()
    logger.info(f"  ✓ {count} IEs loaded for: {label}")
    return count


def ingest_receipts_for_committee(client, conn, committee_id, label=""):
    """Pull itemized receipts (Schedule A) for a single committee."""
    logger.info(f"Fetching receipts for: {label} ({committee_id})")
    count = 0

    for receipt in client.get_receipts(committee_id, cycle=CYCLE):
        record = {
            "sub_id": receipt.get("sub_id", ""),
            "committee_id": committee_id,
            "contributor_name": receipt.get("contributor_name", ""),
            "contributor_first_name": receipt.get("contributor_first_name", ""),
            "contributor_last_name": receipt.get("contributor_last_name", ""),
            "contributor_employer": receipt.get("contributor_employer", ""),
            "contributor_occupation": receipt.get("contributor_occupation", ""),
            "contributor_city": receipt.get("contributor_city", ""),
            "contributor_state": receipt.get("contributor_state", ""),
            "contributor_zip": receipt.get("contributor_zip", ""),
            "contribution_receipt_amount": receipt.get("contribution_receipt_amount", 0),
            "contribution_receipt_date": receipt.get("contribution_receipt_date", ""),
            "receipt_type": receipt.get("receipt_type", ""),
            "receipt_type_full": receipt.get("receipt_type_full", ""),
            "memo_text": receipt.get("memo_text", ""),
            "is_individual": 1 if receipt.get("is_individual") else 0,
            "entity_type": receipt.get("entity_type", ""),
            "two_year_transaction_period": receipt.get("two_year_transaction_period", CYCLE),
        }
        upsert_receipt(conn, record)
        count += 1

        if count % 100 == 0:
            conn.commit()
            logger.info(f"  ... {count} receipts so far")

    conn.commit()
    logger.info(f"  ✓ {count} receipts loaded for {label}")
    return count


def ingest_disbursements_for_committee(client, conn, committee_id, label=""):
    """Pull itemized disbursements (Schedule B) for a single committee."""
    logger.info(f"Fetching disbursements for: {label} ({committee_id})")
    count = 0

    for disb in client.get_disbursements(committee_id, cycle=CYCLE):
        record = {
            "sub_id": disb.get("sub_id", ""),
            "committee_id": committee_id,
            "recipient_name": disb.get("recipient_name", ""),
            "recipient_city": disb.get("recipient_city", ""),
            "recipient_state": disb.get("recipient_state", ""),
            "disbursement_amount": disb.get("disbursement_amount", 0),
            "disbursement_date": disb.get("disbursement_date", ""),
            "disbursement_description": disb.get("disbursement_description", ""),
            "disbursement_type": disb.get("disbursement_type", ""),
            "memo_text": disb.get("memo_text", ""),
            "two_year_transaction_period": disb.get("two_year_transaction_period", CYCLE),
        }
        upsert_disbursement(conn, record)
        count += 1

        if count % 100 == 0:
            conn.commit()
            logger.info(f"  ... {count} disbursements so far")

    conn.commit()
    logger.info(f"  ✓ {count} disbursements loaded for {label}")
    return count


def ingest_receipts_aggregates(client, conn):
    """Pull aggregated receipt data (by size, by state) for all committees."""
    committees = all_tracked_committees()
    for key, info in committees.items():
        cid = info["committee_id"]
        if not cid:
            continue
        logger.info(f"Fetching aggregates for: {info['name']} ({cid})")
        try:
            for row in client.get_receipts_by_size(cid, cycle=CYCLE):
                conn.execute("""
                    INSERT OR REPLACE INTO receipts_by_size
                    (committee_id, cycle, size, total, count, last_updated)
                    VALUES (?, ?, ?, ?, ?, datetime('now'))
                """, (cid, row.get("cycle", CYCLE), row.get("size", 0),
                      row.get("total", 0), row.get("count", 0)))
        except Exception as e:
            logger.warning(f"  No size data for {cid}: {e}")
        try:
            for row in client.get_receipts_by_state(cid, cycle=CYCLE):
                conn.execute("""
                    INSERT OR REPLACE INTO receipts_by_state
                    (committee_id, cycle, state, state_full, total, count, last_updated)
                    VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
                """, (cid, row.get("cycle", CYCLE), row.get("state", ""),
                      row.get("state_full", ""), row.get("total", 0), row.get("count", 0)))
        except Exception as e:
            logger.warning(f"  No state data for {cid}: {e}")
    conn.commit()


def lookup_missing_ids(client: FECClient):
    """Interactive helper to find committee IDs that are still TBD."""
    print("=" * 60)
    print("MassieMoney — Missing Committee ID Lookup")
    print("=" * 60)

    print("\n--- Searching for Ed Gallrein (candidate) ---")
    try:
        candidates = client.search_candidates("Gallrein", state="KY", district="04")
        if candidates:
            for c in candidates:
                committees = c.get("principal_committees", [])
                committee_id = committees[0].get("committee_id", "N/A") if committees else "N/A"
                print(f"  ✓ {c['name']}")
                print(f"    Candidate ID: {c['candidate_id']}")
                print(f"    Committee ID: {committee_id}")
        else:
            print("  No results. Try: https://www.fec.gov/data/elections/house/KY/04/2026/")
    except Exception as e:
        print(f"  Error: {e}")

    for query, label in [("Kentucky First", "Kentucky First PAC"),
                          ("Preserve America", "Preserve America PAC"),
                          ("MAGA Kentucky", "MAGA KY"), ("United Democracy", "UDP/AIPAC")]:
        print(f"\n--- Searching for: {label} ---")
        try:
            results = client.search_committees(query)
            for r in (results or [])[:5]:
                cycles = r.get("cycles", [])
                marker = "✓" if (2026 in cycles or 2025 in cycles) else "○"
                print(f"  {marker} {r['name']} ({r['committee_id']})")
                print(f"    Type: {r.get('committee_type_full', 'N/A')}, Cycles: {cycles[-5:]}")
        except Exception as e:
            print(f"  Error: {e}")

    print("\n--- KY-04 2026 Election Overview ---")
    try:
        for e in client.get_election(state="KY", district="04", cycle=2026):
            print(f"  {e.get('candidate_name', 'N/A')} ({e.get('candidate_id', 'N/A')})")
            print(f"    Receipts: ${e.get('total_receipts', 0):,.0f}, Committee: {e.get('candidate_pcc_id', 'N/A')}")
    except Exception as e:
        print(f"  Error: {e}")


# ──────────────────────────────────────────────
# Main Pipeline (with checkpointing)
# ──────────────────────────────────────────────

def run_full_ingest(fresh: bool = False):
    """
    Run the complete ingestion pipeline with checkpoint support.
    Skips steps that completed in a previous run unless --fresh is specified.
    On error, saves progress so the next run picks up where it left off.
    """
    start = datetime.now()
    logger.info(f"Starting ingest at {start.isoformat()}")

    state = {} if fresh else load_checkpoint()
    if fresh:
        state = {"completed_steps": [], "last_run": None, "errors": {}}
        save_checkpoint(state)
        logger.info("Fresh run — cleared all checkpoints")
    else:
        completed = len(state.get("completed_steps", []))
        if completed > 0:
            logger.info(f"Resuming from checkpoint: {completed}/{len(PIPELINE_STEPS)} steps already done")

    client = FECClient()
    conn = init_db()

    # Map step names to their execution logic
    massie_cid = "C00509729"
    gallrein_cid = "C00923995"
    maga_ky_cid = "C00908723"
    ky_first_cid = "C00918227"
    massie_candidate = CANDIDATES["massie"]["candidate_id"]
    gallrein_candidate = CANDIDATES["gallrein"]["candidate_id"]

    step_runners = {
        "committees": lambda: ingest_committee_metadata(client, conn),
        "ie_massie": lambda: _ingest_ie_for_target(
            client, conn, candidate_id=massie_candidate,
            label=f"targeting Massie ({massie_candidate})"
        ),
        "ie_gallrein": lambda: _ingest_ie_for_target(
            client, conn, candidate_id=gallrein_candidate,
            label=f"targeting Gallrein ({gallrein_candidate})"
        ),
        "ie_pac_maga_ky": lambda: _ingest_ie_for_target(
            client, conn, committee_id=maga_ky_cid,
            label=f"from MAGA KY ({maga_ky_cid})"
        ),
        "ie_pac_ky_first": lambda: _ingest_ie_for_target(
            client, conn, committee_id=ky_first_cid,
            label=f"from Kentucky First PAC ({ky_first_cid})"
        ),
        "agg_by_size": lambda: ingest_receipts_aggregates(client, conn),
        "agg_by_state": lambda: None,  # handled together with agg_by_size
        "receipts_massie": lambda: ingest_receipts_for_committee(
            client, conn, massie_cid, "Thomas Massie for Congress"
        ),
        "receipts_gallrein": lambda: ingest_receipts_for_committee(
            client, conn, gallrein_cid, "Ed Gallrein for Congress"
        ),
        "receipts_maga_ky": lambda: ingest_receipts_for_committee(
            client, conn, maga_ky_cid, "MAGA KY"
        ),
        "disb_massie": lambda: ingest_disbursements_for_committee(
            client, conn, massie_cid, "Thomas Massie for Congress"
        ),
        "disb_gallrein": lambda: ingest_disbursements_for_committee(
            client, conn, gallrein_cid, "Ed Gallrein for Congress"
        ),
        "disb_maga_ky": lambda: ingest_disbursements_for_committee(
            client, conn, maga_ky_cid, "MAGA KY"
        ),
    }

    try:
        for step_name, description in PIPELINE_STEPS:
            if not should_run(state, step_name):
                logger.info(f"  ⏭  Skipping (already done): {description}")
                continue

            logger.info(f"\n{'='*60}")
            logger.info(f"=== {description} ===")
            logger.info(f"{'='*60}")

            try:
                runner = step_runners.get(step_name)
                if runner:
                    runner()
                mark_step_done(state, step_name)
                logger.info(f"  ✓ Checkpoint saved: {step_name}")

            except Exception as e:
                logger.error(f"  ✗ Step '{step_name}' failed: {e}")
                mark_step_error(state, step_name, str(e))
                logger.error(f"    Progress saved. Run again to retry from this step.")
                logger.error(f"    Or use --fresh to restart the entire pipeline.")
                # Don't bail — try the next step (it may not depend on this one)
                continue

        # Final summary
        elapsed = (datetime.now() - start).total_seconds()
        logger.info(f"\n{'=' * 60}")
        logger.info(f"Ingest complete in {elapsed:.1f}s")

        completed = len(state["completed_steps"])
        total = len(PIPELINE_STEPS)
        errors = len(state.get("errors", {}))

        if errors > 0:
            logger.warning(f"  {completed}/{total} steps succeeded, {errors} had errors")
            logger.warning(f"  Run again to retry failed steps")
        else:
            logger.info(f"  All {total} steps completed successfully!")

        # Print table counts
        for table in ["committees", "receipts", "independent_expenditures",
                       "disbursements", "receipts_by_size", "receipts_by_state"]:
            count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            logger.info(f"  {table}: {count:,} rows")

    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(description="MassieMoney FEC Data Ingestion")
    parser.add_argument("--lookup", action="store_true",
                        help="Look up missing committee IDs")
    parser.add_argument("--status", action="store_true",
                        help="Show checkpoint status and exit")
    parser.add_argument("--fresh", action="store_true",
                        help="Clear checkpoints and start from scratch")
    parser.add_argument("--committees-only", action="store_true",
                        help="Only refresh committee metadata and totals")
    parser.add_argument("--ie-only", action="store_true",
                        help="Only refresh independent expenditures")
    parser.add_argument("--receipts-only", action="store_true",
                        help="Only refresh itemized receipts")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Enable verbose logging")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )

    if args.status:
        print_status()
        return

    client = FECClient()

    if args.lookup:
        lookup_missing_ids(client)
        return

    if args.committees_only:
        conn = init_db()
        try:
            ingest_committee_metadata(client, conn)
        finally:
            conn.close()
        return

    if args.ie_only:
        conn = init_db()
        try:
            massie_id = CANDIDATES["massie"]["candidate_id"]
            gallrein_id = CANDIDATES["gallrein"]["candidate_id"]
            _ingest_ie_for_target(client, conn, candidate_id=massie_id,
                                  label=f"targeting Massie ({massie_id})")
            _ingest_ie_for_target(client, conn, candidate_id=gallrein_id,
                                  label=f"targeting Gallrein ({gallrein_id})")
            _ingest_ie_for_target(client, conn, committee_id="C00908723",
                                  label="from MAGA KY")
        finally:
            conn.close()
        return

    if args.receipts_only:
        conn = init_db()
        try:
            ingest_receipts_for_committee(client, conn, "C00509729", "Massie")
            ingest_receipts_for_committee(client, conn, "C00923995", "Gallrein")
            ingest_receipts_for_committee(client, conn, "C00908723", "MAGA KY")
            ingest_receipts_aggregates(client, conn)
        finally:
            conn.close()
        return

    # Default: full pipeline with checkpoint support
    run_full_ingest(fresh=args.fresh)


if __name__ == "__main__":
    main()
