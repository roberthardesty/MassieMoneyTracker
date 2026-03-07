"""
MassieMoney — SQLite database schema and helpers.
Stores normalized FEC data for committees, receipts, disbursements,
and independent expenditures related to the KY-04 2026 primary.
"""

import sqlite3
import logging
from pathlib import Path
from config import DB_PATH, DATA_DIR

logger = logging.getLogger(__name__)

SCHEMA = """
-- ──────────────────────────────────────────────
-- Committees
-- ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS committees (
    committee_id        TEXT PRIMARY KEY,    -- FEC committee ID (C00...)
    name                TEXT NOT NULL,
    committee_type      TEXT,                -- H, S, P, U (Super PAC), etc.
    committee_type_full TEXT,
    designation         TEXT,                -- P (principal), A (authorized), etc.
    designation_full    TEXT,
    treasurer_name      TEXT,
    state               TEXT,
    party               TEXT,
    filing_frequency    TEXT,
    organization_type   TEXT,
    -- MassieMoney classification
    side                TEXT,                -- 'pro_massie', 'anti_massie', 'watchlist'
    local_key           TEXT,                -- our internal key (e.g., 'maga_ky')
    description         TEXT,
    -- Financials (latest totals)
    total_receipts          REAL DEFAULT 0,
    total_disbursements     REAL DEFAULT 0,
    total_independent_exp   REAL DEFAULT 0,
    cash_on_hand            REAL DEFAULT 0,
    debt                    REAL DEFAULT 0,
    coverage_start_date     TEXT,
    coverage_end_date       TEXT,
    -- Meta
    last_updated        TEXT DEFAULT (datetime('now'))
);

-- ──────────────────────────────────────────────
-- Candidates
-- ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS candidates (
    candidate_id        TEXT PRIMARY KEY,    -- FEC candidate ID (H2KY04121)
    name                TEXT NOT NULL,
    party               TEXT,
    state               TEXT,
    district            TEXT,
    office              TEXT,
    incumbent_challenge  TEXT,               -- I, C, O
    -- MassieMoney classification
    side                TEXT,
    -- Financials
    total_receipts      REAL DEFAULT 0,
    total_disbursements REAL DEFAULT 0,
    cash_on_hand        REAL DEFAULT 0,
    debt                REAL DEFAULT 0,
    -- Meta
    last_updated        TEXT DEFAULT (datetime('now'))
);

-- ──────────────────────────────────────────────
-- Schedule A: Itemized Receipts (Donations > $200)
-- ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS receipts (
    sub_id                      TEXT PRIMARY KEY,   -- FEC unique transaction ID
    committee_id                TEXT NOT NULL,
    contributor_name            TEXT,
    contributor_first_name      TEXT,
    contributor_last_name       TEXT,
    contributor_employer        TEXT,
    contributor_occupation      TEXT,
    contributor_city            TEXT,
    contributor_state           TEXT,
    contributor_zip             TEXT,
    contribution_receipt_amount REAL,
    contribution_receipt_date   TEXT,
    receipt_type                TEXT,
    receipt_type_full           TEXT,
    memo_text                   TEXT,
    is_individual               INTEGER,           -- boolean
    entity_type                 TEXT,               -- IND, COM, ORG, etc.
    -- Meta
    two_year_transaction_period INTEGER,
    last_updated                TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (committee_id) REFERENCES committees(committee_id)
);

-- ──────────────────────────────────────────────
-- Schedule A Aggregates: By Size
-- ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS receipts_by_size (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    committee_id    TEXT NOT NULL,
    cycle           INTEGER,
    size            INTEGER,        -- Donation size bucket (e.g., 200, 500, 1000, 2000)
    total           REAL,
    count           INTEGER,
    last_updated    TEXT DEFAULT (datetime('now')),
    UNIQUE(committee_id, cycle, size)
);

-- ──────────────────────────────────────────────
-- Schedule A Aggregates: By State
-- ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS receipts_by_state (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    committee_id    TEXT NOT NULL,
    cycle           INTEGER,
    state           TEXT,
    state_full      TEXT,
    total           REAL,
    count           INTEGER,
    last_updated    TEXT DEFAULT (datetime('now')),
    UNIQUE(committee_id, cycle, state)
);

-- ──────────────────────────────────────────────
-- Schedule B: Itemized Disbursements
-- ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS disbursements (
    sub_id                  TEXT PRIMARY KEY,
    committee_id            TEXT NOT NULL,
    recipient_name          TEXT,
    recipient_city          TEXT,
    recipient_state         TEXT,
    disbursement_amount     REAL,
    disbursement_date       TEXT,
    disbursement_description TEXT,
    disbursement_type       TEXT,
    memo_text               TEXT,
    -- Meta
    two_year_transaction_period INTEGER,
    last_updated            TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (committee_id) REFERENCES committees(committee_id)
);

-- ──────────────────────────────────────────────
-- Schedule E: Independent Expenditures
-- ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS independent_expenditures (
    sub_id                  TEXT,
    committee_id            TEXT NOT NULL,
    committee_name          TEXT,
    candidate_id            TEXT,
    candidate_name          TEXT,
    support_oppose_indicator TEXT,          -- S = support, O = oppose
    expenditure_amount      REAL,
    expenditure_date        TEXT,
    expenditure_description TEXT,
    payee_name              TEXT,
    payee_state             TEXT,
    purpose                 TEXT,
    filing_date             TEXT,
    pdf_url                 TEXT,
    memo_text               TEXT,
    -- Meta
    cycle                   INTEGER,
    last_updated            TEXT DEFAULT (datetime('now')),
    PRIMARY KEY (sub_id, committee_id)
);

-- ──────────────────────────────────────────────
-- Key Donors (manually tracked mega-donors)
-- ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS key_donors (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT NOT NULL,
    employer        TEXT,
    state           TEXT,
    side            TEXT,                   -- pro_massie, anti_massie
    notes           TEXT,
    UNIQUE(name)
);

-- ──────────────────────────────────────────────
-- Indexes for common query patterns
-- ──────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_receipts_committee ON receipts(committee_id);
CREATE INDEX IF NOT EXISTS idx_receipts_date ON receipts(contribution_receipt_date);
CREATE INDEX IF NOT EXISTS idx_receipts_state ON receipts(contributor_state);
CREATE INDEX IF NOT EXISTS idx_receipts_amount ON receipts(contribution_receipt_amount);
CREATE INDEX IF NOT EXISTS idx_receipts_contributor ON receipts(contributor_name);

CREATE INDEX IF NOT EXISTS idx_disbursements_committee ON disbursements(committee_id);
CREATE INDEX IF NOT EXISTS idx_disbursements_date ON disbursements(disbursement_date);

CREATE INDEX IF NOT EXISTS idx_ie_committee ON independent_expenditures(committee_id);
CREATE INDEX IF NOT EXISTS idx_ie_candidate ON independent_expenditures(candidate_id);
CREATE INDEX IF NOT EXISTS idx_ie_support_oppose ON independent_expenditures(support_oppose_indicator);
CREATE INDEX IF NOT EXISTS idx_ie_date ON independent_expenditures(expenditure_date);

-- ──────────────────────────────────────────────
-- Views for common analysis patterns
-- ──────────────────────────────────────────────

-- Total spending by side (pro vs anti Massie)
CREATE VIEW IF NOT EXISTS v_spending_by_side AS
SELECT
    c.side,
    SUM(c.total_receipts) AS total_receipts,
    SUM(c.total_disbursements) AS total_disbursements,
    SUM(c.total_independent_exp) AS total_ie_spending,
    SUM(c.cash_on_hand) AS total_cash_on_hand
FROM committees c
WHERE c.side IN ('pro_massie', 'anti_massie')
GROUP BY c.side;

-- Independent expenditures summary by committee
CREATE VIEW IF NOT EXISTS v_ie_summary AS
SELECT
    ie.committee_id,
    ie.committee_name,
    c.side,
    ie.support_oppose_indicator,
    ie.candidate_name,
    COUNT(*) AS num_filings,
    SUM(ie.expenditure_amount) AS total_amount,
    MIN(ie.expenditure_date) AS earliest_filing,
    MAX(ie.expenditure_date) AS latest_filing
FROM independent_expenditures ie
LEFT JOIN committees c ON ie.committee_id = c.committee_id
GROUP BY ie.committee_id, ie.support_oppose_indicator, ie.candidate_id;

-- Donor geography: in-state (KY) vs out-of-state
CREATE VIEW IF NOT EXISTS v_donor_geography AS
SELECT
    r.committee_id,
    c.name AS committee_name,
    c.side,
    CASE WHEN r.contributor_state = 'KY' THEN 'In-State (KY)' ELSE 'Out-of-State' END AS geo,
    COUNT(*) AS num_donations,
    SUM(r.contribution_receipt_amount) AS total_amount,
    AVG(r.contribution_receipt_amount) AS avg_amount
FROM receipts r
LEFT JOIN committees c ON r.committee_id = c.committee_id
GROUP BY r.committee_id, geo;
""";


def init_db(db_path: Path = DB_PATH) -> sqlite3.Connection:
    """Initialize the database with schema. Returns a connection."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    conn.commit()
    logger.info(f"Database initialized at {db_path}")
    return conn


def get_connection(db_path: Path = DB_PATH) -> sqlite3.Connection:
    """Get a connection to the existing database."""
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


def upsert_committee(conn, data: dict):
    """Insert or update a committee record."""
    conn.execute("""
        INSERT INTO committees (
            committee_id, name, committee_type, committee_type_full,
            designation, designation_full, treasurer_name, state, party,
            filing_frequency, organization_type, side, local_key, description,
            total_receipts, total_disbursements, total_independent_exp,
            cash_on_hand, debt, coverage_start_date, coverage_end_date,
            last_updated
        ) VALUES (
            :committee_id, :name, :committee_type, :committee_type_full,
            :designation, :designation_full, :treasurer_name, :state, :party,
            :filing_frequency, :organization_type, :side, :local_key, :description,
            :total_receipts, :total_disbursements, :total_independent_exp,
            :cash_on_hand, :debt, :coverage_start_date, :coverage_end_date,
            datetime('now')
        )
        ON CONFLICT(committee_id) DO UPDATE SET
            name = excluded.name,
            total_receipts = excluded.total_receipts,
            total_disbursements = excluded.total_disbursements,
            total_independent_exp = excluded.total_independent_exp,
            cash_on_hand = excluded.cash_on_hand,
            debt = excluded.debt,
            coverage_start_date = excluded.coverage_start_date,
            coverage_end_date = excluded.coverage_end_date,
            last_updated = datetime('now')
    """, data)


def upsert_receipt(conn, data: dict):
    """Insert or update a receipt (Schedule A) record."""
    conn.execute("""
        INSERT OR REPLACE INTO receipts (
            sub_id, committee_id, contributor_name,
            contributor_first_name, contributor_last_name,
            contributor_employer, contributor_occupation,
            contributor_city, contributor_state, contributor_zip,
            contribution_receipt_amount, contribution_receipt_date,
            receipt_type, receipt_type_full, memo_text,
            is_individual, entity_type,
            two_year_transaction_period, last_updated
        ) VALUES (
            :sub_id, :committee_id, :contributor_name,
            :contributor_first_name, :contributor_last_name,
            :contributor_employer, :contributor_occupation,
            :contributor_city, :contributor_state, :contributor_zip,
            :contribution_receipt_amount, :contribution_receipt_date,
            :receipt_type, :receipt_type_full, :memo_text,
            :is_individual, :entity_type,
            :two_year_transaction_period, datetime('now')
        )
    """, data)


def upsert_independent_expenditure(conn, data: dict):
    """Insert or update an independent expenditure (Schedule E) record."""
    conn.execute("""
        INSERT OR REPLACE INTO independent_expenditures (
            sub_id, committee_id, committee_name,
            candidate_id, candidate_name,
            support_oppose_indicator, expenditure_amount,
            expenditure_date, expenditure_description,
            payee_name, payee_state, purpose,
            filing_date, pdf_url, memo_text,
            cycle, last_updated
        ) VALUES (
            :sub_id, :committee_id, :committee_name,
            :candidate_id, :candidate_name,
            :support_oppose_indicator, :expenditure_amount,
            :expenditure_date, :expenditure_description,
            :payee_name, :payee_state, :purpose,
            :filing_date, :pdf_url, :memo_text,
            :cycle, datetime('now')
        )
    """, data)


def upsert_disbursement(conn, data: dict):
    """Insert or update a disbursement (Schedule B) record."""
    conn.execute("""
        INSERT OR REPLACE INTO disbursements (
            sub_id, committee_id, recipient_name,
            recipient_city, recipient_state,
            disbursement_amount, disbursement_date,
            disbursement_description, disbursement_type,
            memo_text, two_year_transaction_period, last_updated
        ) VALUES (
            :sub_id, :committee_id, :recipient_name,
            :recipient_city, :recipient_state,
            :disbursement_amount, :disbursement_date,
            :disbursement_description, :disbursement_type,
            :memo_text, :two_year_transaction_period, datetime('now')
        )
    """, data)


# ──────────────────────────────────────────────
# Quick test
# ──────────────────────────────────────────────
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    conn = init_db()

    # Verify tables exist
    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    )
    tables = [row["name"] for row in cursor.fetchall()]
    print(f"Tables created: {tables}")

    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='view' ORDER BY name"
    )
    views = [row["name"] for row in cursor.fetchall()]
    print(f"Views created: {views}")

    conn.close()
    print(f"\nDatabase ready at: {DB_PATH}")
