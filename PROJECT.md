# Operation MassieMoney

## Follow the Money: A Campaign Finance Transparency Tool for KY-04

**Author:** Rob Hardesty
**Created:** March 5, 2026
**Primary Election Date:** May 19, 2026 (~75 days)

---

## 1. Mission

Build an interactive, shareable web-based visualization that tells the definitive money story of the Kentucky 4th District Republican primary: **who is funding each side, where the money comes from, and how the totals compare.**

The core narrative: DC billionaires and MAGA-aligned super PACs are spending unprecedented sums to unseat a seven-term congressman — while Massie's support comes from grassroots donors and liberty-aligned organizations. That story exists in scattered FEC filings and news articles today. Our job is to make it undeniable with data.

---

## 2. The Race at a Glance

| Detail | Value |
|---|---|
| **Race** | KY-04 Republican Primary |
| **Date** | May 19, 2026 |
| **Incumbent** | Rep. Thomas Massie (R) — 7 terms, since Nov 2012 |
| **Challenger** | Ed Gallrein (R) — Former Navy SEAL, Trump-endorsed |
| **Cook Rating** | R+18 (safe R district; primary is the real contest) |
| **Key dynamic** | Trump endorsed Gallrein after Massie voted against the short-term funding bill (Mar 2025). MAGA world has poured millions into unseating Massie. |

---

## 3. Committees & Entities to Track

### 3.1 Pro-Massie

| Entity | FEC ID | Type | Notes |
|---|---|---|---|
| **Thomas Massie for Congress** | `C00509729` | Principal Campaign Committee | Active quarterly House committee. Registered Jan 18, 2012. |
| **Protect Freedom PAC** | `C00657866` | Super PAC (IE-Only) | Active monthly. Registered Oct 11, 2017. Run by former Rand Paul staffers. ~$30M+ lifetime from Jeff Yass (~80% of all receipts). Donated $1M to Kentucky First PAC for pro-Massie ads. |
| **Kentucky First PAC** | `C00918227` | Super PAC (IE-Only) | New PAC created specifically for this race. Received $1M from Protect Freedom on Oct 23, 2025. Paid $1,006,986 to Maverix Media for pro-Massie media buy. |

**Key pro-Massie donors to profile:**
- **Jeff Yass** — Susquehanna International Group co-founder, billionaire, libertarian mega-donor. Funds Protect Freedom. Yass's giving totals ~$35M to Protect Freedom over its lifetime.
- **Sen. Rand Paul** — Not a financial backer per se, but the key political ally. Plans to campaign with Massie in spring 2026.

### 3.2 Anti-Massie

| Entity | FEC ID | Type | Notes |
|---|---|---|---|
| **MAGA KY** | `C00908723` | Super PAC (IE-Only) | Active quarterly. Registered Jun 19, 2025. Run by Tony Fabrizio & Chris LaCivita (Trump's senior political advisers). $1.8M+ spent opposing Massie as of late 2025. LaCivita said they'll spend "whatever it takes." |
| **Ed Gallrein Campaign Committee** | `C00923995` (Candidate: `H6KY04171`) | Principal Campaign Committee | Gallrein raised $1.2M in Q4 2025 (nearly 2x Massie's $640K). |
| **Preserve America PAC** | TBD — needs FEC lookup | Super PAC | Primarily funded by Miriam Adelson. Donated $750K to MAGA KY. |
| **America First Works** | N/A (501c4) | Dark money org | Endorsed Gallrein Mar 3, 2026. Began door-knocking operation. Not required to disclose donors to FEC. |
| **U.S. Chamber of Commerce PAC** | TBD | PAC | Backed Gallrein per Bloomberg Government reporting. |

**Key anti-Massie donors to profile:**
- **Paul Singer** — Elliott Management hedge fund founder, NYC. Gave $1M to MAGA KY.
- **John Paulson** — Paulson & Co hedge fund founder, FL. Gave $250K to MAGA KY.
- **Miriam Adelson** — via Preserve America PAC, gave $750K to MAGA KY.
- **Estimated total anti-Massie outside spending** — Experts predict up to **$45 million** by primary day.

### 3.3 Entities Still Being Researched
- AIPAC / United Democracy Project — historically spends big in primaries against non-interventionist Republicans. Monitor for late IE filings.
- Any additional 501(c)(4) dark money groups that don't file with FEC but may run "issue ads."

---

## 4. Data Sources

### 4.1 FEC API (Primary Source)

| Detail | Value |
|---|---|
| **Base URL** | `https://api.open.fec.gov/v1/` |
| **Docs** | https://api.open.fec.gov/developers/ |
| **Auth** | API key (free, sign up at FEC). `DEMO_KEY` available for testing. |
| **Rate limit** | 1,000 requests/hour with API key |
| **Managed by** | API Umbrella (handles keys, caching, rate limiting) |

**Key Endpoints:**

| Endpoint | Purpose |
|---|---|
| `/candidate/{candidate_id}/` | Candidate metadata |
| `/candidate/{candidate_id}/totals/` | Aggregated financial totals |
| `/committee/{committee_id}/` | Committee metadata |
| `/committee/{committee_id}/totals/` | Committee financial totals |
| `/schedules/schedule_a/` | **Itemized receipts** (individual donations >$200). Filter by committee, date, contributor. |
| `/schedules/schedule_a/by_size/` | Receipts grouped by donation size bracket |
| `/schedules/schedule_a/by_state/` | Receipts grouped by contributor state (in-state vs out-of-state) |
| `/schedules/schedule_a/by_zip/` | Receipts by zip code (geo visualization!) |
| `/schedules/schedule_b/` | **Itemized disbursements** (where money is spent) |
| `/schedules/schedule_e/` | **Independent expenditures** — critical for tracking PAC spending for/against candidates |
| `/schedules/schedule_e/efile/` | Real-time e-filed independent expenditures (24/48 hour reports) |
| `/electioneering/` | Electioneering communications |

**Key query parameters across endpoints:**
- `committee_id` — filter by specific committee
- `candidate_id` — filter by candidate (for Schedule E)
- `support_oppose_indicator` — `S` (support) or `O` (oppose) — critical for IE tracking
- `two_year_transaction_period` — `2026` for current cycle
- `min_date` / `max_date` — date range filtering
- `sort` / `sort_hide_null` — sorting
- `per_page` — pagination (max 100)

### 4.2 FEC Bulk Data Downloads

| Resource | URL |
|---|---|
| Bulk data files | https://www.fec.gov/data/browse-data/?tab=bulk-data |
| Format | Pipe-delimited text files, updated nightly |
| Use case | Faster than API for full dataset pulls. Good for initial data load. |

### 4.3 OpenSecrets

| Detail | Value |
|---|---|
| **Massie profile** | https://www.opensecrets.org/members-of-congress/thomas-massie/summary?cid=N00034041 |
| **API** | https://www.opensecrets.org/api (requires key) |
| **Use case** | Aggregated donor industry data, employer breakdowns, career totals. Good for enrichment but FEC is the primary source. |

### 4.4 ProPublica

| Detail | Value |
|---|---|
| **FEC Itemizer** | https://projects.propublica.org/itemizer/ |
| **Congress API** | https://projects.propublica.org/api-docs/congress-api/ |
| **Use case** | Quick lookup / cross-reference. Itemizer is good for spot-checking individual donations. |

### 4.5 Other Data Sources

| Source | Use |
|---|---|
| **@TrackAIPAC (X/Twitter)** | Best existing tracker of pro-Israel PAC spending in this race. Cross-reference their findings. |
| **Kentucky SBE** (elect.ky.gov) | Voter registration stats by district/county/precinct. Useful for Phase 2 GOTV work. |
| **Ballotpedia** | Race overview, endorsements, polling data. |
| **FollowTheMoney.org** | State-level campaign finance tracking. |

---

## 5. Technical Architecture

### 5.1 Recommended Stack

**Data Pipeline:**
- **Language:** Python 3.11+
- **FEC API client:** Custom lightweight wrapper or `requests` + `pandas`
- **Data storage:** SQLite for local dev, PostgreSQL for production
- **Scheduling:** Cron job or GitHub Actions to refresh FEC data daily (filings update nightly)
- **Data modeling:** Normalize committees, donors, transactions into relational tables

**Visualization / Frontend:**
- **Option A (fast MVP):** Single-page HTML/JS app with D3.js or Chart.js. Host on GitHub Pages or Vercel. Zero backend needed if data is pre-baked into JSON.
- **Option B (richer):** React + Recharts or Plotly.js. Still static hosting, but more interactive.
- **Option C (maximum impact):** Observable notebook — easy to share, embed, and iterate. Good for the data journalism angle.

**Recommended for 75-day timeline: Option A.** Ship a static site with pre-computed JSON data that updates daily via GitHub Actions. No backend infrastructure to maintain. Free hosting. Maximum shareability.

### 5.2 Key Visualizations

1. **The Money River (Sankey Diagram)**
   - Donors → PACs → Candidates/IE Spending
   - Left column: individual mega-donors (Singer, Paulson, Adelson, Yass)
   - Middle: PACs and committees
   - Right: Spending for/against each candidate
   - Color-coded: green for pro-Massie, red for anti-Massie

2. **In-State vs Out-of-State (Choropleth Map)**
   - Map showing where donations originate by zip code
   - Highlights the "DC/NYC money vs Kentucky money" narrative

3. **Running Totals Over Time (Line Chart)**
   - Cumulative spending by each side over the campaign timeline
   - Mark key events (Trump endorsement, ad buys, debates)

4. **Donor Size Distribution (Bar/Histogram)**
   - Small-dollar vs large-dollar donations for each candidate
   - Grassroots (Massie) vs billionaire-funded (Gallrein) contrast

5. **The Mega-Donor Profiles (Cards/Table)**
   - Who are Singer, Paulson, Adelson?
   - What else do they fund? (Defense contractors, pro-Israel orgs, hedge funds)
   - How much of their giving goes to KY-04 specifically?

6. **Independent Expenditure Tracker (Timeline)**
   - Every IE filing, with amount, date, purpose, and support/oppose indicator
   - 24/48 hour filings give near real-time visibility

### 5.3 Data Pipeline Architecture

```
┌─────────────────────────────────────────────────────┐
│                   DATA INGESTION                     │
│                                                      │
│  FEC API ──────┐                                     │
│  FEC Bulk ─────┤──→ Python ETL ──→ SQLite/Postgres   │
│  OpenSecrets ──┘      Scripts        Database        │
│                                                      │
└──────────────────────────┬──────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────┐
│                 DATA PROCESSING                      │
│                                                      │
│  - Normalize committee/donor entities                │
│  - Compute aggregates (by state, size, date)         │
│  - Classify support/oppose                           │
│  - Enrich with donor profiles                        │
│  - Generate static JSON for frontend                 │
│                                                      │
└──────────────────────────┬──────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────┐
│                   FRONTEND                           │
│                                                      │
│  Static HTML/JS site (GitHub Pages / Vercel)         │
│  - D3.js Sankey diagram                              │
│  - Leaflet/Mapbox choropleth                         │
│  - Chart.js / Recharts for time series & bars        │
│  - Mobile-responsive for sharing                     │
│  - Updated daily via CI/CD                           │
│                                                      │
└─────────────────────────────────────────────────────┘
```

### 5.4 Refresh Strategy

- **GitHub Actions** runs nightly at ~2am ET (after FEC bulk data updates)
- Pulls latest data from FEC API
- Rebuilds static JSON artifacts
- Commits and deploys to hosting
- Optional: Slack/Discord webhook on significant new filings (e.g., new IE >$100K)

---

## 6. AI Agent Skills & Tooling

### 6.1 Claude Code / Cowork Skills

These Claude skills are available and potentially useful during development:

| Skill | Use Case |
|---|---|
| **xlsx** | Generate spreadsheet exports of donor data, spending summaries. Useful for sharing raw data with journalists or the campaign. |
| **pdf** | Generate printable one-pager PDFs summarizing key findings. Could be used at campaign events or shared with media. |
| **docx** | Generate formatted reports or press-ready documents with the data findings. |
| **pptx** | If the campaign or a PAC wants a slide deck summarizing the money story for presentations or town halls. |
| **skill-creator** | Create a custom MassieMoney skill that encapsulates the data pipeline — e.g., a skill that can answer "who are Gallrein's top donors?" or "how much has MAGA KY spent this month?" on demand. |
| **schedule** | Set up automated scheduled tasks for daily FEC data refreshes, new filing alerts, or weekly summary generation. |

### 6.2 Claude as Development Partner

Claude can help with:
- **FEC API wrapper code** — writing the Python client, handling pagination, rate limiting, error handling
- **Data modeling** — designing the SQLite/Postgres schema
- **ETL scripts** — ingesting, cleaning, normalizing FEC data
- **Visualization code** — D3.js Sankey diagrams, Chart.js configs, Leaflet maps
- **Static site generation** — HTML/CSS/JS for the frontend
- **GitHub Actions workflows** — CI/CD for automated daily refreshes
- **Data analysis** — ad hoc queries, anomaly detection (e.g., suspicious last-minute donations)
- **Content generation** — shareable social media summaries from the data

### 6.3 Potential Custom Skill: `massiemoney`

A custom Claude skill could be built (using `skill-creator`) that:
- Ingests the latest MassieMoney database
- Answers natural language questions about campaign finance data
- Generates formatted summaries and charts on demand
- Monitors for new FEC filings and alerts

---

## 7. Phased Roadmap

### Phase 1: Data Foundation (Week 1)
- [ ] Register for FEC API key
- [ ] Write Python FEC API client (committees, Schedule A, Schedule E)
- [ ] Pull initial data for all known committee IDs
- [ ] Look up remaining TBD committee IDs (Gallrein, Kentucky First PAC, Preserve America)
- [ ] Design database schema
- [ ] Load and normalize data
- [ ] Validate against known figures from journalism ($1.8M MAGA KY, $1M Protect Freedom → Kentucky First, etc.)

### Phase 2: MVP Visualization (Week 2)
- [ ] Build static HTML/JS site scaffold
- [ ] Implement Sankey diagram (donors → PACs → spending)
- [ ] Implement in-state vs out-of-state map
- [ ] Implement running totals chart
- [ ] Implement donor size distribution
- [ ] Generate static JSON from database
- [ ] Deploy to GitHub Pages
- [ ] Mobile responsiveness pass

### Phase 3: Polish & Share (Week 3)
- [ ] Mega-donor profile cards
- [ ] IE filing timeline
- [ ] Social sharing metadata (Open Graph tags, Twitter cards)
- [ ] Write shareable "about" page explaining the project and methodology
- [ ] Set up GitHub Actions for daily data refresh
- [ ] Contact Massie campaign and/or Protect Freedom with the finished tool
- [ ] Share with liberty-aligned media (Reason, The Intercept, etc.)

### Phase 4: GOTV Integration (Weeks 4+, stretch goal)
- [ ] Pull Kentucky SBE voter registration data
- [ ] Build precinct-level turnout model from historical primary data
- [ ] Create volunteer-facing GOTV dashboard
- [ ] Build "Can you vote for Massie?" registration checker

---

## 8. Legal & Ethical Notes

- **All data is public.** FEC filings are public records. This project uses only publicly available information.
- **No campaign coordination required.** An independent transparency tool is fully legal as a public education effort. If you want to coordinate with the campaign, consult FEC rules on in-kind contributions.
- **Attribution.** Cite all data sources clearly. Link back to FEC.gov for raw data.
- **No editorializing in the data.** Let the numbers speak. The visualization should be factual and verifiable. Commentary/framing is for social posts, not the tool itself.
- **Domain options:** massiemoney.com, followthemoneyky.com, ky4money.org, etc. Check availability.

---

## 9. Key Reference Links

| Resource | URL |
|---|---|
| FEC - Massie candidate page | https://www.fec.gov/data/candidate/H2KY04121/ |
| FEC - Massie committee | https://www.fec.gov/data/committee/C00509729/ |
| FEC - MAGA KY committee | https://www.fec.gov/data/committee/C00908723/ |
| FEC - Protect Freedom PAC | https://www.fec.gov/data/committee/C00657866/ |
| FEC - KY-04 2026 election page | https://www.fec.gov/data/elections/house/KY/04/2026/ |
| FEC API docs | https://api.open.fec.gov/developers/ |
| FEC bulk data | https://www.fec.gov/data/browse-data/?tab=bulk-data |
| OpenSecrets - Massie | https://www.opensecrets.org/members-of-congress/thomas-massie/summary?cid=N00034041 |
| ProPublica Itemizer | https://projects.propublica.org/itemizer/ |
| Massie official site | https://www.thomasmassie.com/ |
| Massie vote record | https://massie.house.gov/voterecord/ |
| Freedom Index - Massie | https://thefreedomindex.org/legislator/m001184/ |
| Ballotpedia - KY-04 primary | https://ballotpedia.org/Kentucky's_4th_Congressional_District_election,_2026_(May_19_Republican_primary) |
| @TrackAIPAC | https://x.com/TrackAIPAC |
| Protect Freedom - Endorse Massie | https://www.protectfreedompac.com/endorse-massie |
| OpenFEC GitHub repo | https://github.com/fecgov/openFEC |

---

## 10. Open Questions

1. **Gallrein's FEC committee ID** — not yet found via search. Need to look up directly on FEC.gov elections page for KY-04 2026.
2. **Kentucky First PAC FEC ID** — new PAC, may be registered under a slightly different name. Need FEC lookup.
3. **Preserve America PAC FEC ID** — Adelson-linked PAC. Need FEC lookup.
4. **AIPAC / United Democracy Project involvement** — have they filed any IEs in this race yet? Monitor Schedule E filings.
5. **Domain name** — secure a domain early for shareability.
6. **Hosting** — GitHub Pages (free, simple) vs Vercel (free tier, more features) vs custom.
7. **Campaign contact** — should we reach out to Massie's campaign before or after the MVP ships?
