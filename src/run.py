#!/usr/bin/env python3
"""
MassieMoney — Main entry point
Runs the full pipeline: ingest → export → report.
Supports resume from checkpoint if a previous run was interrupted.

Usage:
    # Full pipeline (resumes from last checkpoint if interrupted)
    python run.py

    # Start fresh (ignore previous checkpoints)
    python run.py --fresh

    # Check pipeline status
    python run.py --status

    # Just refresh and re-export (skip API calls, use existing DB)
    python run.py --export-only

    # Verbose mode
    python run.py -v

Environment variables:
    FEC_API_KEY          Your FEC API key (default: DEMO_KEY, 60 req/hr)
    MASSIEMONEY_DATA_DIR Where to store the SQLite DB (default: ~/.massiemoney/data)
"""

import argparse
import logging
import sys
from pathlib import Path

# Ensure src/ is on the path
sys.path.insert(0, str(Path(__file__).parent))

from config import DB_PATH, OUTPUT_DIR, CANDIDATES
from database import init_db, get_connection
from fec_client import FECClient
from ingest import (
    run_full_ingest, lookup_missing_ids, print_status,
    ingest_committee_metadata, _ingest_ie_for_target
)
from export_json import export_all


def print_db_summary(conn):
    """Print a quick summary of what's in the database."""
    print("\n" + "=" * 60)
    print("DATABASE SUMMARY")
    print("=" * 60)

    for table in ["committees", "receipts", "independent_expenditures",
                   "disbursements", "receipts_by_size", "receipts_by_state"]:
        count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        print(f"  {table:30s} {count:>8,} rows")

    # Spending by side
    print("\n--- Spending by Side ---")
    rows = conn.execute("""
        SELECT side, SUM(total_receipts) as receipts,
               SUM(total_disbursements) as disbursements,
               SUM(cash_on_hand) as coh
        FROM committees
        WHERE side IN ('pro_massie', 'anti_massie')
        GROUP BY side
    """).fetchall()
    for row in rows:
        print(f"  {row['side']:15s}  Receipts: ${row['receipts']:>12,.0f}  "
              f"Disbursed: ${row['disbursements']:>12,.0f}  "
              f"COH: ${row['coh']:>12,.0f}")

    # IE summary
    print("\n--- Independent Expenditure Summary ---")
    rows = conn.execute("""
        SELECT committee_name, support_oppose_indicator,
               candidate_name, SUM(expenditure_amount) as total,
               COUNT(*) as filings
        FROM independent_expenditures
        GROUP BY committee_name, support_oppose_indicator, candidate_name
        ORDER BY total DESC
    """).fetchall()
    if rows:
        for row in rows:
            so = "SUPPORT" if row["support_oppose_indicator"] == "S" else "OPPOSE "
            print(f"  {row['committee_name'][:30]:30s} {so} {row['candidate_name'] or 'N/A':20s} "
                  f"${row['total']:>12,.0f} ({row['filings']} filings)")
    else:
        print("  (no IE data yet)")

    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(description="MassieMoney — Campaign Finance Pipeline")
    parser.add_argument("--lookup", action="store_true",
                        help="Look up missing committee IDs, then exit")
    parser.add_argument("--status", action="store_true",
                        help="Show pipeline checkpoint status")
    parser.add_argument("--fresh", action="store_true",
                        help="Clear checkpoints and restart the full pipeline")
    parser.add_argument("--export-only", action="store_true",
                        help="Skip API ingestion, just re-export JSON from existing DB")
    parser.add_argument("--quick", action="store_true",
                        help="Quick refresh: committees + IEs only (skip itemized receipts)")
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )

    if args.status:
        print_status()
        return

    if args.lookup:
        client = FECClient()
        lookup_missing_ids(client)
        return

    if args.export_only:
        logging.info("Export-only mode: reading from existing database")
        conn = get_connection()
        print_db_summary(conn)
        conn.close()
        export_all(args.output_dir)
        return

    if args.quick:
        logging.info("Quick refresh: committees + IEs only")
        client = FECClient()
        conn = init_db()
        try:
            ingest_committee_metadata(client, conn)
            massie_id = CANDIDATES["massie"]["candidate_id"]
            gallrein_id = CANDIDATES["gallrein"]["candidate_id"]
            _ingest_ie_for_target(client, conn, candidate_id=massie_id,
                                  label=f"targeting Massie ({massie_id})")
            _ingest_ie_for_target(client, conn, candidate_id=gallrein_id,
                                  label=f"targeting Gallrein ({gallrein_id})")
            _ingest_ie_for_target(client, conn, committee_id="C00908723",
                                  label="from MAGA KY")
            print_db_summary(conn)
        finally:
            conn.close()
        export_all(args.output_dir)
        return

    # Full pipeline with checkpoint support
    run_full_ingest(fresh=args.fresh)

    conn = get_connection()
    print_db_summary(conn)
    conn.close()

    export_all(args.output_dir)
    print(f"\nJSON files exported to: {args.output_dir}")
    print("Next step: serve the output/ directory or copy to your static site")


if __name__ == "__main__":
    main()
