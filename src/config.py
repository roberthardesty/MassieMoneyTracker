"""
MassieMoney — Central configuration for committee IDs, candidate IDs,
and other constants used across the pipeline.
"""

import os

# ──────────────────────────────────────────────
# FEC API
# ──────────────────────────────────────────────
FEC_API_KEY = os.environ.get("FEC_API_KEY", "DEMO_KEY")
FEC_BASE_URL = "https://api.open.fec.gov/v1"
CYCLE = 2026

# ──────────────────────────────────────────────
# Candidates
# ──────────────────────────────────────────────
CANDIDATES = {
    "massie": {
        "name": "Thomas Massie",
        "candidate_id": "H2KY04121",
        "party": "REP",
        "side": "pro_massie",
    },
    "gallrein": {
        "name": "Ed Gallrein",
        "candidate_id": "H6KY04171",
        "party": "REP",
        "side": "anti_massie",
    },
}

# ──────────────────────────────────────────────
# Committees — Pro-Massie
# ──────────────────────────────────────────────
PRO_MASSIE_COMMITTEES = {
    "massie_campaign": {
        "name": "Thomas Massie for Congress",
        "committee_id": "C00509729",
        "type": "campaign",
        "description": "Massie's principal campaign committee. Active quarterly House committee since Jan 2012.",
    },
    "protect_freedom": {
        "name": "Protect Freedom Political Action Committee",
        "committee_id": "C00657866",
        "type": "super_pac",
        "description": "Rand Paul-aligned Super PAC. ~$35M lifetime from Jeff Yass (~80% of receipts). Donated $1M to Kentucky First PAC.",
    },
    "kentucky_first": {
        "name": "Kentucky First PAC",
        "committee_id": "C00918227",
        "type": "super_pac",
        "description": "New PAC created for this race. Received $1M from Protect Freedom Oct 23, 2025. Paid ~$1M to Maverix Media for pro-Massie ads.",
        "website": "https://www.kentuckyfirstpac.com/",
    },
    "make_liberty_win": {
        "name": "Make Liberty Win",
        "committee_id": "C00731133",
        "type": "super_pac",
        "description": "Liberty-aligned Super PAC. Filed $180K in IEs supporting Massie (Jan 2026).",
    },
}

# ──────────────────────────────────────────────
# Committees — Anti-Massie
# ──────────────────────────────────────────────
ANTI_MASSIE_COMMITTEES = {
    "gallrein_campaign": {
        "name": "Ed Gallrein for Congress",
        "committee_id": "C00923995",
        "type": "campaign",
        "description": "Gallrein's principal campaign committee. Raised $1.2M in Q4 2025.",
    },
    "maga_ky": {
        "name": "MAGA KY",
        "committee_id": "C00908723",
        "type": "super_pac",
        "description": "Trump-aligned Super PAC. Run by Fabrizio & LaCivita. $4.1M+ spent opposing Massie. Registered Jun 19, 2025.",
    },
    "preserve_america": {
        "name": "Preserve America PAC",
        "committee_id": "C00878801",
        "type": "super_pac",
        "description": "Adelson-funded Super PAC. Donated $750K to MAGA KY. $114M+ total receipts (not all KY-04).",
    },
    "rjc_victory_fund": {
        "name": "RJC Victory Fund",
        "committee_id": "C00528554",
        "type": "super_pac",
        "description": "Republican Jewish Coalition Victory Fund. Filed $2.87M opposing Massie and $2.87M supporting Gallrein (Feb 2026).",
    },
}

# ──────────────────────────────────────────────
# Entities to watch (may file IEs later)
# ──────────────────────────────────────────────
WATCHLIST_COMMITTEES = {
    "united_democracy_project": {
        "name": "United Democracy Project",
        "committee_id": "C00799031",  # AIPAC's Super PAC (IE-only)
        "type": "super_pac",
        "description": "AIPAC-affiliated Super PAC. Filed a small IE in KY-04 (Oct 2025). Historically spends tens of millions in primaries — watch closely.",
    },
    "america_first_works": {
        "name": "America First Works",
        "committee_id": None,  # 501(c)(4) — may not file with FEC
        "type": "dark_money_501c4",
        "description": "Endorsed Gallrein Mar 3, 2026. Began door-knocking. 501(c)(4) so donors not disclosed to FEC.",
    },
    "us_chamber": {
        "name": "U.S. Chamber of Commerce PAC",
        "committee_id": None,  # TODO: look up if they've filed IEs
        "type": "pac",
        "description": "Backed Gallrein per Bloomberg Government. May file IEs.",
    },
}

# ──────────────────────────────────────────────
# Key individual donors to track
# ──────────────────────────────────────────────
KEY_DONORS = {
    "jeff_yass": {
        "name": "Jeffrey Yass",
        "employer": "Susquehanna International Group",
        "state": "PA",
        "side": "pro_massie",
        "known_contributions": "$35M+ to Protect Freedom (lifetime), $1M indirect to Kentucky First PAC",
    },
    "paul_singer": {
        "name": "Paul Singer",
        "employer": "Elliott Management",
        "state": "NY",
        "side": "anti_massie",
        "known_contributions": "$1M to MAGA KY",
    },
    "john_paulson": {
        "name": "John Paulson",
        "employer": "Paulson & Co",
        "state": "FL",
        "side": "anti_massie",
        "known_contributions": "$250K to MAGA KY",
    },
    "miriam_adelson": {
        "name": "Miriam Adelson",
        "employer": None,
        "state": "NV",
        "side": "anti_massie",
        "known_contributions": "$750K to MAGA KY (via Preserve America PAC)",
    },
}

# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────
def all_committee_ids(include_none=False):
    """Return a flat list of all committee IDs we want to pull data for."""
    ids = []
    for group in [PRO_MASSIE_COMMITTEES, ANTI_MASSIE_COMMITTEES, WATCHLIST_COMMITTEES]:
        for key, info in group.items():
            cid = info["committee_id"]
            if cid or include_none:
                ids.append(cid)
    return [c for c in ids if c is not None]


def all_tracked_committees():
    """Return all committees (pro + anti + watchlist) as a flat dict."""
    merged = {}
    for group_name, group in [
        ("pro_massie", PRO_MASSIE_COMMITTEES),
        ("anti_massie", ANTI_MASSIE_COMMITTEES),
        ("watchlist", WATCHLIST_COMMITTEES),
    ]:
        for key, info in group.items():
            info["group"] = group_name
            info["key"] = key
            merged[key] = info
    return merged


# ──────────────────────────────────────────────
# Database & Paths
# ──────────────────────────────────────────────
import pathlib

PROJECT_ROOT = pathlib.Path(__file__).parent.parent
OUTPUT_DIR = PROJECT_ROOT / "output"

# SQLite needs a filesystem with proper locking support.
# The mounted workspace volume may not support this (e.g., FUSE/NFS mounts),
# so we use a local directory for the DB and export final artifacts to the mount.
# When running locally on your machine, you can point this at the project dir.
LOCAL_DATA_DIR = pathlib.Path(os.environ.get(
    "MASSIEMONEY_DATA_DIR",
    pathlib.Path.home() / ".massiemoney" / "data"
))
DATA_DIR = LOCAL_DATA_DIR
DB_PATH = DATA_DIR / "massiemoney.db"
