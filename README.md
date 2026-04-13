# Fort Worth Intelligence

**Layered civic data platform for Fort Worth and Tarrant County — from raw public records to address-resolved intelligence.**

`https://github.com/tylerdotai/fort-worth-intelligence`

---

## Status: Working (2026-04-12)

### ✅ Live & Verified

| Layer | Source | Records | Status |
|-------|--------|---------|--------|
| TAD Certified Appraisals | tad.org | **283,808 parcels** | ✅ Live |
| Address Resolution | Census TIGER + TAD | Per-address | ✅ Live |
| Council Districts (all 10) | mapit.tarrantcounty.com | 10 polygons | ✅ Live |
| Legistar Calendar | fortworthgov.legistar.com | **20 meetings** | ✅ Live |
| Development Permits | services5.arcgis.com | **1,258/week** | ✅ Live |
| FWPD Crime Data | services5.arcgis.com | **~1,000/week** | ✅ Live |
| FastAPI Server | localhost:8000 | — | ✅ Live |

### ⚠️ Partial / Known Issues

| Layer | Issue | Severity |
|-------|-------|----------|
| Crime data (stored) | Only 155 records — ArcGIS `resultRecordCount` capped at default | Low (API fresh fetch works) |
| Legistar agenda items | Stored file has 0 items (key mismatch in extractor) | Medium (meetings work, items don't) |
| FW Open Data catalog | Catalog scrape returned 0 datasets (DOM extraction) | Medium (URLs confirmed manually) |
| Council district index | `data/council-districts/index.json` is empty | Low (orchestrator fetches live) |

---

## Quick Start

```bash
# Install dependencies
pip install fastapi uvicorn pydantic requests shapely pyproj

# Start the API server
cd fort-worth-intelligence
uvicorn api_server:app --port 8000 --reload

# Resolve any Fort Worth address
curl "http://127.0.0.1:8000/resolve?address=704%20E%20Weatherford%20St"

# Or use the Python module directly
python3 -c "
import sys; sys.path.insert(0, 'scripts')
from resolve_address_full import resolve_full
import json, json
print(json.dumps(resolve_full('704 E Weatherford St'), indent=2))
"
```

---

## Repository Structure

```
fort-worth-intelligence/
├── api_server.py              # FastAPI server (GET /resolve, POST /resolve/batch, GET /health)
├── data/
│   ├── tad/
│   │   └── tad-parcels-fort-worth.json   # 283,808 Fort Worth residential parcels (TAD 2025 certified)
│   ├── fw-crime.json          # FWPD crime incidents (ArcGIS, current week sample)
│   ├── fw-permits.json        # FW development permits (1,258 records)
│   ├── legistar-meetings.json # City council calendar (20 upcoming meetings)
│   ├── legistar-agenda-items.json  # ⚠ Empty — extractor needs fixing
│   ├── council-districts/
│   │   └── index.json         # ⚠ Empty — live fetch in orchestrator instead
│   └── raw/
│       ├── fw-open-data-catalog.json   # ⚠ 0 datasets — catalog scrape failed
│       ├── discovery_urls.validated.json  # 83 DAO-discovered sources, validated
│       └── canonical_institutions.json   # 14 core institutional anchors
├── scripts/
│   ├── resolve_address_full.py   # End-to-end address resolution (Census → TAD → council → school → utilities)
│   ├── resolve_address.py        # Census geocoder + TAD parcel join
│   ├── extract_tad_parcels.py    # TAD certified data parser + Fort Worth filter
│   ├── extract_legistar.py       # Legistar calendar scraper (iCal enrich)
│   ├── extract_legistar_agenda.py  # ⚠ Agenda items (broken key/schema)
│   ├── extract_fw_crime.py       # FWPD crime ArcGIS extractor
│   ├── extract_fw_permits.py     # Development permits ArcGIS extractor
│   └── scrape_fw_catalog.py      # ⚠ FW open data catalog scraper (DOM extraction failed)
└── docs/
    ├── source-catalog.md
    ├── capability-matrix.md
    ├── parcel-appraisal-tax-layer.md
    ├── gis-address-resolution-layer.md
    ├── school-district-layer.md
    ├── utilities-special-district-layer.md
    └── monitoring-signals.md
```

---

## Live Intelligence Layers

### 1. Address Resolution (primary API)

**`resolve_address_full(address)`** — single address orchestrator:

```
Address → Census geocoder → TAD parcel → Council district (point-in-polygon)
        → School district (from TAD) → Utility providers (deterministic)
```

**Returns:** lat/lon, normalized address, TAD parcel (owner, value, school, exemptions, GIS link),
council district (all 10), school district, water/electric/gas providers, stormwater.

```bash
# Via API
curl "http://127.0.0.1:8000/resolve?address=704%20E%20Weatherford%20St"

# Via FastAPI docs: http://127.0.0.1:8000/docs
```

**Tested addresses:**

| Address | Council | Owner | Value |
|---------|---------|-------|-------|
| 704 E Weatherford St | **Dist 9** — Elizabeth M. Beck | DAILEY, TODD | $556,381 |
| 3901 Baylor St | **Dist 5** — Gwen B. McKie | MENDOZA, JOSE & MARIA | $192,230 |
| 5624 Wellesley Ave | **Dist 2** — Carlos Flores | KENDRICK, TASHEKA | $245,000 |

### 2. TAD Certified Appraisals (283,808 parcels)

**Source:** Tarrant Appraisal District `PropertyData_R_2025(Certified).ZIP`

```bash
# Refresh from TAD
curl -L "https://www.tad.org/content/data-download/PropertyData_R_2025(Certified).ZIP" \
  -o data/tad/PropertyData_R_2025(Certified).ZIP

python3 scripts/extract_tad_parcels.py --city "FORT WORTH"
```

**Schema per parcel:** `account_num`, `owner_name`, `owner_address`, `situs_address`,
`school_name`, `year_built`, `living_area`, `num_bedrooms`, `num_bathrooms`,
`total_value`, `appraised_value`, `land_value`, `improvement_value`,
`land_acres`, `gis_link`, `deed_date`, `legal_desc`

**Join key:** `gis_link` (section-township-range + lot) → Fort Worth GIS parcel boundaries

### 3. Council Districts (all 10)

**Source:** `mapit.tarrantcounty.com/arcgis/rest/services/CIVIC/OpenData_Boundaries/MapServer/2`

Point-in-polygon resolution using `shapely` + `pyproj` (EPSG:4326 → EPSG:2276).

**2026 Members:**

| District | Council Member | Email |
|----------|---------------|-------|
| 1 | District 1 | district1@fortworthtexas.gov |
| 2 | Carlos Flores | district2@fortworthtexas.gov |
| 3 | Michael Crain | district3@fortworthtexas.gov |
| 4 | District 4 | district4@fortworthtexas.gov |
| 5 | Gwen B. McKie | district5@fortworthtexas.gov |
| 6 | District 6 | district6@fortworthtexas.gov |
| 7 | District 7 | district7@fortworthtexas.gov |
| 8 | District 8 | district8@fortworthtexas.gov |
| 9 | Elizabeth M. Beck | district9@fortworthtexas.gov |
| 10 | District 10 | district10@fortworthtexas.gov |

### 4. Legistar City Council Calendar (20 meetings)

**Source:** `fortworthgov.legistar.com/View.ashx?M=IC&ID=...`

```bash
python3 scripts/extract_legistar.py --max-pages 2 --enrich --min-delay 3
```

**Per meeting:** body, date/time, location, iCal URL, agenda URL, video link, cancelled status.

Upcoming: CITY COUNCIL (May 12, 6PM), PLAN commission, ZONING COMMISSION, etc.

### 5. Development Permits (1,258/week)

**Source:** `services5.arcgis.com/3ddLCBXe1bRt7mzj/arcgis/rest/services/CFW_Open_Data_Development_Permits_View/FeatureServer/0`

```bash
python3 scripts/extract_fw_permits.py --days 7

# By type
python3 scripts/extract_fw_permits.py --type Building --days 30
python3 scripts/extract_fw_permits.py --status Issued --days 30
```

**Per permit:** permit_no, type, subtype, address, owner, file_date, status, job_value, description, coordinates.

### 6. FWPD Crime Incidents

**Source:** `services5.arcgis.com/3ddLCBXe1bRt7mzj/arcgis/rest/services/CFW_Open_Data_Police_Crime_Data_Table_view/FeatureServer/0`

```bash
python3 scripts/extract_fw_crime.py --days 7
```

**Per incident:** case_no, reported_date, from_date, nature_of_call, offense, category,
block_address, council_district (pre-joined).

⚠️ Note: Stored `fw-crime.json` is a sample (155 records). The extractor API call is correct
but uses default `resultRecordCount`. Fix: add `resultRecordCount=1000` to the query.

---

## Data Sources

| Source | Type | URL |
|--------|------|-----|
| Tarrant Appraisal District | Bulk ZIP | tad.org/content/data-download |
| TCGIS (Tarrant County) | ArcGIS MapServer | mapit.tarrantcounty.com |
| Fort Worth Open Data | ArcGIS Hub + FeatureServer | services5.arcgis.com/3ddLCBXe1bRt7mzj |
| Fort Worth Legistar | Web scraper | fortworthgov.legistar.com |
| Census TIGER/Line | Free geocoder | geocoding.geo.census.gov |

---

## Next Steps (Priority Order)

1. **Fix stored crime data** — add `resultRecordCount=1000` to ArcGIS crime query, re-scrape
2. **Fix legistar agenda items** — correct key (`meetings[]` not `items[]`), re-scrape
3. **Refresh FW open data catalog** — fix DOM extraction or use ArcGIS Hub API
4. **Populate council-districts/index.json** — serialize live-fetched polygons locally
5. **Utility / MUD district layer** — TCGIS `Dynamic/WNVCity` water districts + ETJ boundary
6. **Real estate transactions** — TAD deed transfer data (same source, different export)
7. **Zoning cases** — FW zoning ordinance layer via ArcGIS
8. **Batch address geocoding** — Census geocoder for all 283K TAD parcels (one-time)
9. **FWGIS parcel boundaries** — join `gis_link` → parcel polygons → full address map

---

## License

MIT
