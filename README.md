# Free Multi-Source Lead Discovery Engine

A standalone, 100% free, multi-source **Lead Discovery and Web Intelligence Engine** built in Python with FastAPI, Pydantic, Playwright, SQLite + SQLAlchemy, and modular extractors.

This engine operates independently without requiring Apollo, Clay, paid Google Maps APIs, or any paid enrichment services.

---

## Architecture Overview

```text
User Discovery Request
        ↓
Query Expansion Engine (Basic, Services, Contact, Intent, Dorks)
        ↓
┌────────────────────────────────────────────────────────┐
│ Pluggable Discovery Sources                            │
│ ├── Public Search Source (DuckDuckGo / Search Engines) │
│ ├── Maps / Local Business (OSM Nominatim + Web Local)  │
│ ├── Instagram Public Source (Snippets & Bio Meta)      │
│ ├── Search Operator / Dork Source                      │
│ └── Historical Source (Wayback Machine CDX API)        │
└───────────────────────────┬────────────────────────────┘
                            ↓
                   Candidate Businesses
                            ↓
                   Website Intelligence
  ├── robots.txt inspection & Sitemap.xml URL discovery
  ├── Priority page discovery (/contact, /about, /services, /team, /locations)
  └── Hybrid Fetcher (Fast HTTPX async + Playwright fallback for dynamic JS)
                            ↓
                 Multi-Layer Extraction
  ├── JSON-LD / Schema.org (LocalBusiness, Medical, Dentist, Organization, etc.)
  ├── Meta & OpenGraph / Twitter Cards
  ├── Contact Extraction (E.164 Phones, Email de-obfuscation & spam filtering)
  ├── Social Profile Extraction (Instagram, FB, LinkedIn, Twitter/X, YouTube)
  └── Business Services & Description Extraction
                            ↓
                      Normalization
  ├── Domain, Phone (E.164), Email (clean/lowercase), Address, Business Name
                            ↓
                      Deduplication
  ├── Tier 1: Exact normalized root domain match
  ├── Tier 2: Exact normalized phone number match
  ├── Tier 3: Normalized social profile handle match (Instagram/LinkedIn)
  ├── Tier 4: Normalized business name + Location match
  └── Tier 5: Fuzzy name similarity (>0.85) + Location match
                            ↓
                   Evidence Aggregation
  └── Merge candidate records, preserve all source URLs, source types & confidence
                            ↓
                   Discovery Results
```

---

## Critical Rules

### Final Lead Eligibility
Discovery may retain incomplete records internally, but final results contain only identifiable businesses that match the target industry, match a requested location, and have at least one usable public contact path. A phone-only, email-only, social-only, or own-website lead is valid; every optional contact field is not required.

* **`requirements.must_have`** → **Additional eligibility**: Extra constraints that can discard an otherwise valid candidate (e.g., `["website"]`).
* **`collect`** → **Extraction Request**: Tells the engine what to *attempt* to extract (e.g. `"email"`, `"phone"`, `"linkedin"`). Missing fields become `null` or `[]` and the business is still KEPT.
* **`found`** → **Actual Result**: What was successfully discovered with supporting evidence.

---

## Setup & Running Locally

### 1. Requirements
* Python 3.10+
* Playwright Chromium (for JS-rendered page fallbacks)

### 2. Installation
```bash
# Create and activate virtualenv
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Install Playwright browser
playwright install chromium
```

### 3. Run FastAPI Server
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Interactive OpenAPI Docs will be available at:
* Swagger UI: `http://localhost:8000/docs`
* ReDoc: `http://localhost:8000/redoc`

---

## API Endpoints

### 1. Submit a Discovery Job
`POST /api/v1/discovery`

**Request Payload:**
```json
{
  "target": {
    "industry": "Dental clinics",
    "services": [
      "dental implants",
      "cosmetic dentistry"
    ],
    "keywords": [
      "dentist",
      "dental clinic"
    ]
  },
  "locations": [
    "Bangalore",
    "Mysore"
  ],
  "lead_objective": "Find businesses that may need a new website",
  "requirements": {
    "must_have": [
      "website"
    ],
    "preferred": [
      "instagram",
      "email"
    ],
    "exclude": [
      "hospitals",
      "government clinics"
    ]
  },
  "collect": [
    "business_name",
    "website",
    "phone",
    "email",
    "address",
    "instagram",
    "facebook",
    "linkedin",
    "services",
    "description"
  ],
    "settings": {
      "target_leads": 20,
      "max_candidates_checked": 250,
      "max_search_queries": 100,
      "max_runtime_minutes": 10,
    "language": "en",
    "discovery_depth": "standard",
    "enable_historical": false
  }
}
```

**Response (HTTP 202):**
```json
{
  "job_id": "84c8be19-913a-4428-a531-dfd1997d8c6b",
  "status": "pending",
  "message": "Discovery job successfully submitted and running in the background."
}
```

### 2. Check Job Status
`GET /api/v1/discovery/{job_id}`

### 3. Get Concise Discovered Leads
`GET /api/v1/discovery/{job_id}/results`

The public results contain only `company_name`, `company_details`, `website`, `phone`, `email`, and useful additional contact links. Internal evidence is not included in this response.

### 4. Get Rejected Candidates (Diagnostic)
`GET /api/v1/discovery/{job_id}/rejections`

This endpoint contains only candidates rejected during identity, relevance, location, contact, or final validation. Each record includes a standardized `reason_code`, `reason_detail`, and pipeline `stage`.

### 5. Get Raw Discovered Candidates (Diagnostic)
`GET /api/v1/discovery/{job_id}/candidates`

### 6. List All Jobs
`GET /api/v1/discovery`

---

## Running Automated Tests

```bash
source .venv/bin/activate
pytest -q
```

## Manual API Test

Run the server from WSL:

```bash
source .venv/bin/activate
cp -n .env.example .env
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

In a second WSL terminal, verify the server:

```bash
curl http://localhost:8000/health
```

Submit a small discovery request first:

```bash
curl -X POST http://localhost:8000/api/v1/discovery \
  -H 'Content-Type: application/json' \
  -d '{
    "target": {
      "industry": "Dental clinics",
      "services": ["dental implants"],
      "keywords": ["dentist", "dental clinic"]
    },
    "locations": ["Bangalore"],
    "services_offered": ["SEO", "Website Design"],
    "settings": {
      "target_leads": 5,
      "max_candidates_checked": 50,
      "max_search_queries": 20,
      "max_runtime_minutes": 3,
      "enable_historical": false
    }
  }'
```

Copy the returned `job_id`, then check progress:

```bash
curl http://localhost:8000/api/v1/discovery/<job_id>
```

When `status` is `completed`, fetch the concise leads:

```bash
curl http://localhost:8000/api/v1/discovery/<job_id>/results
```

The result should contain only real, relevant, correctly located, contactable businesses. Records with only a name/address, directory page names, generic listing titles, wrong locations, or mixed source contacts should be absent.
