<a id="readme-top"></a>

<br />
<div align="center">
  <img src="assets/fort-worth-intelligence.png" alt="Fort Worth Intelligence" width="180">

  <h3 align="center">Fort Worth Intelligence</h3>

  <p align="center">
    Structured source catalog and research narrative for the deepest validated public data surface around Fort Worth and Tarrant County.
    <br />
    <a href="docs/source-catalog.md"><strong>Explore the source catalog »</strong></a>
    <br />
    <br />
    <a href="docs/research-narrative.md">Research Narrative</a>
    ·
    <a href="https://github.com/tylerdotai/fort-worth-intelligence/issues">Report Bug</a>
    ·
    <a href="https://github.com/tylerdotai/fort-worth-intelligence/issues">Request Feature</a>
  </p>
</div>

---

[![MIT License][license-shield]][license-url]
[![Issues][issues-shield]][issues-url]
[![Stars][stars-shield]][stars-url]
[![Forks][forks-shield]][forks-url]

## About The Project

Most “city data” projects are thin wrappers around a city homepage or open data portal.

Fort Worth does not work like that.

The real public-information surface is distributed across:
- City of Fort Worth
- Tarrant County
- Legistar and vendor-hosted records systems
- appraisal and tax systems
- school districts
- transit and regional planning bodies
- water and special districts
- health systems
- airport and regional infrastructure surfaces
- federal and state APIs that enrich the local picture

This repo exists to map that whole surface in a way that is actually usable.

It combines:
- a **structured source catalog**
- a **research narrative** explaining the landscape
- a **capability matrix** for API / GIS / portal / docs / bulk / scrape-only classification
- DAO-discovered discovery maps used as leads only
- validation bias toward official and institutional sources

### Built With

- Markdown
- Python-friendly raw source files
- GitHub
- Official public APIs and public portals

## Repository Structure

```text
fort-worth-intelligence/
├── assets/
│   └── fort-worth-intelligence.png
├── data/
│   ├── raw/
│   │   ├── discovery_urls.txt               # DAO-discovered leads (83 sources)
│   │   ├── discovery_urls.validated.json   # All 83 validated + categorized
│   │   ├── discovery_urls.normalized.json  # Cleaned, deduped
│   │   ├── canonical_institutions.json     # 14 core canonical institutions
│   │   └── source_layer_mappings.json      # Layer → institution crosswalk
│   ├── legistar-meetings.json              # City council calendar (20 meetings)
│   ├── legistar-agenda-items.json          # Agenda items from council meetings (429 items)
│   ├── tad-parcels-fort-worth-SAMPLE.json  # TAD sample (~1%, ~2800 records)
│   └── tad/                                # Full TAD certified data (283,802 parcels)
│       └── PropertyData_R_2025(Certified).ZIP  # Download from tad.org
├── docs/
│   ├── source-catalog.md
│   ├── capability-matrix.md
│   ├── parcel-appraisal-tax-layer.md
│   ├── gis-address-resolution-layer.md
│   ├── legistar-agenda-ordinance-layer.md
│   ├── school-district-layer.md
│   ├── utilities-special-district-layer.md
│   ├── address-resolution-gis-join.md      # GIS join + geocoding architecture
│   ├── tad-parcel-data-ingestion.md        # TAD data layout + field docs
│   └── relationship-scaffold.md
└── scripts/
    ├── extract_legistar.py                # City council calendar scraper (iCal enrich)
    ├── extract_legistar_agenda.py         # Agenda item extractor (MeetingDetail parser)
    ├── extract_tad_parcels.py             # TAD certified data parser
    ├── resolve_address_full.py           # End-to-end: Census → TAD → council → school → utilities
    └── resolve_address.py                 # Census geocoder + TAD parcel join
```

## What’s Included

### 1. Structured Source Catalog
`docs/source-catalog.md`

Validation progress is also tracked in:
- `data/raw/discovery_urls.validated.json`

A normalized catalog of Fort Worth / Tarrant public data sources, organized by domain:
- core government
- council / agendas / ordinances
- elections / representation
- property / appraisal / tax / parcel
- zoning / planning / development
- crime / courts / public safety
- schools / ISDs / colleges
- transit / roads / infrastructure / GIS
- utilities / water / special districts / health
- business / nonprofits / economic development

Each source is tagged with:
- validation tier
- access type
- role in the data graph
- notes for downstream productization

### 2. Research Narrative
`docs/research-narrative.md`

A strategic narrative explaining:
- why the DAO source map matters
- what shape the Fort Worth civic graph actually takes
- where the highest-value data layers are
- what product and infrastructure opportunities this unlocks
- what to build next if the goal is a serious Fort Worth intelligence stack

### 3. Capability Matrix
`docs/capability-matrix.md`

A working matrix for how the Fort Worth source surface can actually be consumed:
- API
- GIS
- portal
- docs
- bulk
- scrape-only

### 4. High-Value Data Layers
Dedicated docs now exist for:
- parcel / appraisal / tax
- GIS / address resolution
- Legistar / agendas / ordinances
- school districts
- utilities / special districts
- `docs/monitoring-signals.md` — change-frequency matrix for all layers (polling intervals, alert triggers, output schema)

### 5. Discovery Map Input
`data/raw/discovery_urls.txt`

### 6. Live Intelligence Extractors
High-value source extractors that produce machine-readable output:

#### Legistar Calendar + Agenda Items
Two scripts — one for the calendar, one for agenda items.

**Calendar:** `scripts/extract_legistar.py` — Fetches Legistar calendar (Telerik RadGrid) and enriches each meeting with iCal records. Produces `data/legistar-meetings.json` with 20 meetings.

```bash
python3 scripts/extract_legistar.py --max-pages 2 --enrich --min-delay 3
```

**Agenda items:** `scripts/extract_legistar_agenda.py` — Fetches `MeetingDetail.aspx` for each meeting and parses the agenda table into structured JSON. ⚠ Produces 0 items — known schema mismatch (meetings[] used instead of items[]).

```bash
python3 scripts/extract_legistar_agenda.py --min-delay 4
```

**Per item:** file number (M&C, ZC, etc.), version, item number, type, title, council district (CD), status (Approved/Adopted/Continued), attachments, video link.

#### TAD Certified Appraisal Data
`scripts/extract_tad_parcels.py` — Tarrant Appraisal District certified residential data parser.

Downloads from `https://www.tad.org/content/data-download/` and parses the pipe-delimited certified export. Produces `data/tad/tad-parcels-fort-worth.json` with 283,808 Fort Worth residential parcels.

**Data per parcel:**
```
account_num, owner_name, owner_address, situs_address
school_name, year_built, living_area, num_bedrooms/bathrooms
total_value, appraised_value, land_value, improvement_value
land_acres, gis_link, legal_desc, deed_date, arb_indicator
```

```bash
# Download fresh data
curl -L "https://www.tad.org/content/data-download/PropertyData_R_2025(Certified).ZIP" \
  -o data/tad/PropertyData_R_2025(Certified).ZIP

# Extract Fort Worth parcels
python3 scripts/extract_tad_parcels.py

# Or use the Python module directly:
python3 scripts/extract_tad_parcels.py --city "FORT WORTH" --limit 100
```

**Stats:** 283,808 Fort Worth parcels | Median value $262,645 | P90 $452,011

#### Full Address Resolution Orchestrator
`scripts/resolve_address_full.py` — End-to-end address intelligence pipeline.

Single entry point: Census geocoder → TAD parcel → council district (all 10, point-in-polygon via TCGIS MapServer) → school district → utility providers.

```bash
# Python module
python3 -c "
import sys; sys.path.insert(0, 'scripts')
from resolve_address_full import resolve_full
import json; print(json.dumps(resolve_full('704 E Weatherford St'), indent=2))
"

# FastAPI server (live at http://127.0.0.1:8000):
# GET /resolve?address=704%20E%20Weatherford%20St
# GET /docs  (Swagger UI)

# Verified: Council District 9 (Elizabeth M. Beck) | Owner: DAILEY, TODD | $556,381 | FW ISD
```

#### Fort Worth Development Permits
`scripts/extract_fw_permits.py` — ArcGIS Hub API client for City of Fort Worth Open Data permits.

Uses the public `CFW_Open_Data_Development_Permits_View` feature service (no auth required).

```bash
# Last 7 days of permits (default — 1,200+ records)
python3 scripts/extract_fw_permits.py --days 7 --min-delay 2

# Issued permits from last 30 days
python3 scripts/extract_fw_permits.py --status Issued --days 30

# By permit type
python3 scripts/extract_fw_permits.py --type Building --days 7

# Search by address
python3 scripts/extract_fw_permits.py --address "E Weatherford"
```

**Data per permit:** permit\_no, type, subtype, address, owner, file\_date, current\_status, job\_value, work\_description, coordinates.

Stats: ~1,258 permits/week from Fort Worth Development Services permit center.

#### FWPD Crime Data
`scripts/extract_fw_crime.py` — ArcGIS FeatureServer client for Fort Worth Police Department incident data. Council district is pre-joined via FWPD 100m grid.

```bash
python3 scripts/extract_fw_crime.py --days 7
```

Important: this list is treated as **lead generation**, not truth.

## Methodology

This repo follows a strict validation rule:

1. **Use DAO repos as discovery maps**
2. **Independently verify each source**
3. **Prefer official domains and official APIs**
4. **Classify each source by access type and reliability**
5. **Document what can be operationalized into real intelligence products**

### Validation Tiers

- **Tier A**: official government / institutional / direct API / direct system of record
- **Tier B**: official vendor-hosted public system acting as record surface
- **Tier C**: secondary or derivative source, only used when necessary

## Why This Matters

The highest-value civic product here is probably not a “wiki.”

It is an **address-centric intelligence layer**.

If you can resolve:
- parcel
- tax bodies
- school district
- city / county districts
- utilities / special districts
- transit context
- nearby legislative actions
- zoning and development surfaces

for a single Fort Worth address, you have something immediately useful for:
- residents
- journalists
- developers
- real-estate operators
- civic orgs
- local researchers
- policy and campaign teams

## Roadmap

- [x] Build initial Fort Worth / Tarrant source catalog
- [x] Write research narrative from validated sources
- [x] Preserve DAO-discovered source inventory
- [x] Normalize all 83 DAO sources into canonical institution records
- [x] Run initial validation pass across all DAO-discovered sources
- [x] Legistar city council agenda extractor (20 meetings)
- [x] TAD certified appraisal data extractor (283,808 Fort Worth parcels)
- [x] Address resolver: Census geocoder + TAD parcel join
- [x] GIS join architecture doc (GIS_Link → TAXPIN → ESRI shape file)
- [x] Council district join: all 10 districts via TCGIS MapServer (point-in-polygon)
- [x] FastAPI server: single + batch address resolution endpoint
- [ ] Validate every source manually against canonical official domains
- [ ] Batch geocode all 283K Fort Worth addresses via Census (one-time setup)
- [ ] Build TAD entity association file (per-entity taxable values)
- [ ] Add legislative / agenda / ordinance change-tracking targets
- [ ] Add machine-readable JSON source registry
- [ ] Fix legistar agenda items extractor (schema mismatch: meetings[] not items[])
- [ ] Redis cache layer for address resolution (< 500ms p95 for cached addresses)
- [ ] Pre-geocode all 283K TAD parcels to Postgres for instant lookups

## Contributing

Contributions should improve one of three things:
- source validation
- source coverage
- structure and usability of the intelligence model

If you contribute:
1. prefer official sources
2. include exact URLs
3. note whether access is API, portal, GIS, bulk, docs, or scrape-only
4. document validation confidence
5. avoid mixing speculation with confirmed information

## License

Distributed under the MIT License. See `LICENSE` for more information.

## Acknowledgments

- [FWTX-DAO/fwtx-wiki-engine](https://github.com/FWTX-DAO/fwtx-wiki-engine)
- [FWTX-DAO/fwtx-scraper](https://github.com/FWTX-DAO/fwtx-scraper)
- [Best-README-Template](https://github.com/othneildrew/Best-README-Template)
- official Fort Worth, Tarrant County, district, regional, and federal public data sources

<p align="right">(<a href="#readme-top">back to top</a>)</p>

<!-- MARKDOWN LINKS & IMAGES -->
[license-shield]: https://img.shields.io/github/license/tylerdotai/fort-worth-intelligence.svg?style=for-the-badge
[license-url]: https://github.com/tylerdotai/fort-worth-intelligence/blob/main/LICENSE
[issues-shield]: https://img.shields.io/github/issues/tylerdotai/fort-worth-intelligence.svg?style=for-the-badge
[issues-url]: https://github.com/tylerdotai/fort-worth-intelligence/issues
[stars-shield]: https://img.shields.io/github/stars/tylerdotai/fort-worth-intelligence.svg?style=for-the-badge
[stars-url]: https://github.com/tylerdotai/fort-worth-intelligence/stargazers
[forks-shield]: https://img.shields.io/github/forks/tylerdotai/fort-worth-intelligence.svg?style=for-the-badge
[forks-url]: https://github.com/tylerdotai/fort-worth-intelligence/network/members
