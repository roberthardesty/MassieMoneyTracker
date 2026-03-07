"""
MassieMoney — JSON Export
Reads from the SQLite database and generates static JSON files
for the frontend visualization to consume.

Usage:
    python export_json.py               # Export all JSON to output/
    python export_json.py --output-dir /path/to/site/data

Output files:
    summary.json           - High-level totals for both sides
    committees.json        - All committee details and financials
    ie_timeline.json       - Independent expenditures over time
    ie_by_committee.json   - IE totals grouped by committee
    donors_by_state.json   - Donor geography (in-state vs out-of-state)
    donors_by_size.json    - Donation size distribution
    sankey.json            - Sankey diagram data (donors → PACs → spending)
    top_donors.json        - Top individual donors per committee
    meta.json              - Last updated timestamp and data freshness
"""

import argparse
import json
import logging
from datetime import datetime
from pathlib import Path

from database import get_connection
from config import DB_PATH, OUTPUT_DIR, CANDIDATES, KEY_DONORS

logger = logging.getLogger("massiemoney.export")


def save(data, filepath: Path):
    filepath.parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, "w") as f:
        json.dump(data, f, indent=2, default=str)
    logger.info(f"Exported {filepath.name} ({filepath.stat().st_size:,} bytes)")


def export_summary(conn, output_dir: Path):
    """High-level spending summary: pro-Massie vs anti-Massie."""
    rows = conn.execute("""
        SELECT
            side,
            SUM(total_receipts) as total_receipts,
            SUM(total_disbursements) as total_disbursements,
            SUM(total_independent_exp) as total_ie,
            SUM(cash_on_hand) as cash_on_hand,
            COUNT(*) as num_committees
        FROM committees
        WHERE side IN ('pro_massie', 'anti_massie')
        GROUP BY side
    """).fetchall()

    summary = {}
    for row in rows:
        summary[row["side"]] = {
            "total_receipts": row["total_receipts"],
            "total_disbursements": row["total_disbursements"],
            "total_independent_expenditures": row["total_ie"],
            "cash_on_hand": row["cash_on_hand"],
            "num_committees": row["num_committees"],
        }

    # Add IE totals from the independent_expenditures table (more accurate)
    ie_rows = conn.execute("""
        SELECT
            c.side,
            ie.support_oppose_indicator,
            SUM(ie.expenditure_amount) as total
        FROM independent_expenditures ie
        LEFT JOIN committees c ON ie.committee_id = c.committee_id
        GROUP BY c.side, ie.support_oppose_indicator
    """).fetchall()

    ie_detail = {}
    for row in ie_rows:
        side = row["side"] or "unknown"
        so = row["support_oppose_indicator"]
        if side not in ie_detail:
            ie_detail[side] = {}
        ie_detail[side][f"ie_{'support' if so == 'S' else 'oppose'}"] = row["total"]

    summary["ie_detail"] = ie_detail
    summary["primary_date"] = "2026-05-19"
    summary["days_until_primary"] = (datetime(2026, 5, 19) - datetime.now()).days

    save(summary, output_dir / "summary.json")


def export_committees(conn, output_dir: Path):
    """All committee details and financials."""
    rows = conn.execute("""
        SELECT * FROM committees ORDER BY side, total_receipts DESC
    """).fetchall()

    committees = []
    for row in rows:
        committees.append(dict(row))

    save(committees, output_dir / "committees.json")


def export_ie_timeline(conn, output_dir: Path):
    """Independent expenditures as a timeline for charting."""
    rows = conn.execute("""
        SELECT
            expenditure_date,
            committee_id,
            committee_name,
            candidate_name,
            support_oppose_indicator,
            expenditure_amount,
            expenditure_description,
            payee_name
        FROM independent_expenditures
        WHERE expenditure_date IS NOT NULL AND expenditure_date != ''
        ORDER BY expenditure_date ASC
    """).fetchall()

    timeline = []
    running_total_oppose = 0
    running_total_support = 0

    for row in rows:
        amount = row["expenditure_amount"] or 0
        if row["support_oppose_indicator"] == "O":
            running_total_oppose += amount
        else:
            running_total_support += amount

        timeline.append({
            "date": row["expenditure_date"],
            "committee_id": row["committee_id"],
            "committee_name": row["committee_name"],
            "candidate": row["candidate_name"],
            "support_oppose": row["support_oppose_indicator"],
            "amount": amount,
            "description": row["expenditure_description"],
            "payee": row["payee_name"],
            "running_total_oppose": running_total_oppose,
            "running_total_support": running_total_support,
        })

    save(timeline, output_dir / "ie_timeline.json")


def export_ie_by_committee(conn, output_dir: Path):
    """IE totals grouped by committee and support/oppose."""
    rows = conn.execute("""
        SELECT
            ie.committee_id,
            ie.committee_name,
            c.side,
            ie.support_oppose_indicator,
            ie.candidate_name,
            COUNT(*) as num_filings,
            SUM(ie.expenditure_amount) as total_amount,
            MIN(ie.expenditure_date) as first_filing,
            MAX(ie.expenditure_date) as last_filing
        FROM independent_expenditures ie
        LEFT JOIN committees c ON ie.committee_id = c.committee_id
        GROUP BY ie.committee_id, ie.support_oppose_indicator, ie.candidate_name
        ORDER BY total_amount DESC
    """).fetchall()

    save([dict(r) for r in rows], output_dir / "ie_by_committee.json")


def export_donors_by_state(conn, output_dir: Path):
    """Donor geography breakdown per committee."""
    rows = conn.execute("""
        SELECT
            committee_id,
            state,
            state_full,
            cycle,
            total,
            count
        FROM receipts_by_state
        ORDER BY committee_id, total DESC
    """).fetchall()

    # Group by committee
    by_committee = {}
    for row in rows:
        cid = row["committee_id"]
        if cid not in by_committee:
            by_committee[cid] = {"states": [], "total_in_state": 0, "total_out_of_state": 0}
        by_committee[cid]["states"].append(dict(row))
        if row["state"] == "KY":
            by_committee[cid]["total_in_state"] = row["total"] or 0
        else:
            by_committee[cid]["total_out_of_state"] += row["total"] or 0

    save(by_committee, output_dir / "donors_by_state.json")


def export_donors_by_size(conn, output_dir: Path):
    """Donation size distribution per committee."""
    rows = conn.execute("""
        SELECT committee_id, cycle, size, total, count
        FROM receipts_by_size
        ORDER BY committee_id, size
    """).fetchall()

    by_committee = {}
    for row in rows:
        cid = row["committee_id"]
        if cid not in by_committee:
            by_committee[cid] = []
        by_committee[cid].append(dict(row))

    save(by_committee, output_dir / "donors_by_size.json")


def export_top_donors(conn, output_dir: Path):
    """Top individual donors per committee."""
    # Get top 50 donors per committee by total amount
    committees = conn.execute(
        "SELECT DISTINCT committee_id FROM receipts"
    ).fetchall()

    result = {}
    for c in committees:
        cid = c["committee_id"]
        rows = conn.execute("""
            SELECT
                contributor_name,
                contributor_employer,
                contributor_occupation,
                contributor_state,
                contributor_city,
                SUM(contribution_receipt_amount) as total_contributed,
                COUNT(*) as num_contributions,
                MIN(contribution_receipt_date) as first_contribution,
                MAX(contribution_receipt_date) as last_contribution
            FROM receipts
            WHERE committee_id = ?
            GROUP BY contributor_name, contributor_state
            ORDER BY total_contributed DESC
            LIMIT 50
        """, (cid,)).fetchall()

        result[cid] = [dict(r) for r in rows]

    save(result, output_dir / "top_donors.json")


def export_sankey(conn, output_dir: Path):
    """
    Generate Sankey diagram data showing money flow:
    Donors → PACs/Committees → Spending (support/oppose)

    Format: { nodes: [...], links: [...] }
    """
    nodes = []
    links = []
    node_index = {}

    def add_node(name, category):
        if name not in node_index:
            node_index[name] = len(nodes)
            nodes.append({"name": name, "category": category})
        return node_index[name]

    # Add key donors as source nodes
    for key, donor in KEY_DONORS.items():
        add_node(donor["name"], f"donor_{donor['side']}")

    # Add committees as middle nodes
    committees = conn.execute("""
        SELECT committee_id, name, side, total_receipts, total_disbursements
        FROM committees
        WHERE side IN ('pro_massie', 'anti_massie')
    """).fetchall()

    for c in committees:
        add_node(c["name"], c["side"])

    # Add target nodes (support/oppose Massie, support/oppose Gallrein)
    add_node("Support Massie", "target_support")
    add_node("Oppose Massie", "target_oppose")
    add_node("Support Gallrein", "target_support_gallrein")

    # Links: Key donors → committees (from known contributions in config)
    known_flows = [
        ("Jeffrey Yass", "Protect Freedom Political Action Committee", 7500000),
        ("Protect Freedom Political Action Committee", "Kentucky First PAC", 1000000),
        ("Paul Singer", "MAGA KY", 1000000),
        ("John Paulson", "MAGA KY", 250000),
        ("Miriam Adelson", "MAGA KY", 750000),  # via Preserve America
    ]

    for source, target, amount in known_flows:
        if source in node_index and target in node_index:
            links.append({
                "source": node_index[source],
                "target": node_index[target],
                "value": amount,
            })

    # Links: Committees → targets (from IE data)
    ie_flows = conn.execute("""
        SELECT
            committee_name,
            candidate_name,
            support_oppose_indicator,
            SUM(expenditure_amount) as total
        FROM independent_expenditures
        GROUP BY committee_name, candidate_name, support_oppose_indicator
    """).fetchall()

    for ie in ie_flows:
        source_name = ie["committee_name"]
        if source_name not in node_index:
            continue

        if ie["support_oppose_indicator"] == "O" and "MASSIE" in (ie["candidate_name"] or "").upper():
            target_name = "Oppose Massie"
        elif ie["support_oppose_indicator"] == "S" and "MASSIE" in (ie["candidate_name"] or "").upper():
            target_name = "Support Massie"
        elif ie["support_oppose_indicator"] == "S" and "GALLREIN" in (ie["candidate_name"] or "").upper():
            target_name = "Support Gallrein"
        else:
            continue

        links.append({
            "source": node_index[source_name],
            "target": node_index[target_name],
            "value": ie["total"],
        })

    save({"nodes": nodes, "links": links}, output_dir / "sankey.json")


def export_meta(output_dir: Path):
    """Metadata about the export (timestamps, freshness)."""
    save({
        "exported_at": datetime.now().isoformat(),
        "primary_date": "2026-05-19",
        "days_until_primary": (datetime(2026, 5, 19) - datetime.now()).days,
        "data_source": "Federal Election Commission (FEC) via OpenFEC API",
        "project": "MassieMoney — KY-04 Campaign Finance Transparency",
        "fec_url": "https://www.fec.gov/data/elections/house/KY/04/2026/",
    }, output_dir / "meta.json")


def export_all(output_dir: Path = OUTPUT_DIR):
    """Run all exports."""
    conn = get_connection()
    try:
        export_summary(conn, output_dir)
        export_committees(conn, output_dir)
        export_ie_timeline(conn, output_dir)
        export_ie_by_committee(conn, output_dir)
        export_donors_by_state(conn, output_dir)
        export_donors_by_size(conn, output_dir)
        export_top_donors(conn, output_dir)
        export_sankey(conn, output_dir)
        export_meta(output_dir)
        logger.info(f"All exports complete → {output_dir}")
    finally:
        conn.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    parser = argparse.ArgumentParser(description="MassieMoney JSON Export")
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR,
                        help="Directory to write JSON files")
    args = parser.parse_args()

    export_all(args.output_dir)
