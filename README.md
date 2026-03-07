# MassieMoney

**Campaign finance transparency tool for the KY-04 2026 Republican Primary**

Tracks and visualizes the flow of money in the Thomas Massie vs. Ed Gallrein primary race, with a focus on outside PAC spending.

## Quick Start

```bash
# 1. Get a free FEC API key (1000 requests/hour vs 60 with DEMO_KEY)
#    Sign up at: https://api.data.gov/signup/
export FEC_API_KEY="your-key-here"

# 2. Install dependencies (just requests + pandas, likely already installed)
pip install requests pandas

# 3. Look up any remaining committee IDs (optional — all key ones are filled in)
cd src/
python run.py --lookup

# 4. Run the full pipeline: ingest from FEC → export JSON
python run.py

# 5. Or do a quick refresh (committees + independent expenditures only)
python run.py --quick

# 6. Re-export JSON without hitting the API
python run.py --export-only
```

## Project Structure

```
MassieMoney/
├── PROJECT.md          # Detailed project documentation & roadmap
├── README.md           # This file
├── src/
│   ├── config.py       # Committee IDs, candidate IDs, all constants
│   ├── fec_client.py   # FEC API wrapper with pagination & rate limiting
│   ├── database.py     # SQLite schema & helpers
│   ├── ingest.py       # ETL pipeline (FEC API → SQLite)
│   ├── export_json.py  # SQLite → static JSON for frontend
│   └── run.py          # Main entry point (ties it all together)
├── data/               # SQLite database (gitignored, generated)
└── output/             # Static JSON files for the frontend
    ├── summary.json
    ├── committees.json
    ├── ie_timeline.json
    ├── ie_by_committee.json
    ├── donors_by_state.json
    ├── donors_by_size.json
    ├── top_donors.json
    ├── sankey.json
    └── meta.json
```

## Key Committee IDs

### Pro-Massie
| Entity | FEC ID |
|---|---|
| Thomas Massie for Congress | C00509729 |
| Protect Freedom PAC (Yass) | C00657866 |
| Kentucky First PAC | C00918227 |

### Anti-Massie
| Entity | FEC ID |
|---|---|
| Ed Gallrein for Congress | C00923995 |
| MAGA KY | C00908723 |
| Preserve America PAC (Adelson) | C00878801 |

### Watchlist
| Entity | FEC ID |
|---|---|
| United Democracy Project (AIPAC) | C00798140 |

## Configuration

Environment variables:

| Variable | Default | Description |
|---|---|---|
| `FEC_API_KEY` | `DEMO_KEY` | FEC API key. Get one free at api.data.gov/signup/ |
| `MASSIEMONEY_DATA_DIR` | `~/.massiemoney/data` | Where to store the SQLite database |

## Data Sources

All data is sourced from public FEC filings via the [OpenFEC API](https://api.open.fec.gov/developers/).

## License

This is a public interest transparency project. All underlying data is public record from the Federal Election Commission.
