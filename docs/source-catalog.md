# Fort Worth Intelligence Source Catalog

Structured source catalog for Fort Worth + Tarrant County civic, institutional, and public-data intelligence.

Validation standard:
- official sources first
- DAO repos used as discovery maps only
- secondary sources only when needed and clearly labeled

## Source grading
- **Tier A**: official government / institutional / direct API / direct portal
- **Tier B**: official vendor-hosted system acting as system of record
- **Tier C**: secondary or derivative source, use only when A/B unavailable

## Access type legend
- **API**: documented API or machine-readable endpoint
- **Portal**: searchable web portal / vendor portal
- **GIS**: map service, feature service, or geospatial site
- **Docs**: pages, PDFs, agendas, minutes, notices
- **Bulk**: downloadable dataset or files
- **Scrape**: extraction needed from public pages

---

## 1. Core Government / Institutional Surface

| Entity | Source | Tier | Access | Notes |
|---|---|---:|---|---|
| City of Fort Worth | <https://www.fortworthtexas.gov> | A | Docs/Scrape | City departments, notices, plans, service pages |
| City map portal | <https://mapit.fortworthtexas.gov> | A | GIS/Portal | Address-centric map and layer discovery |
| City legislative system | <https://fortworthgov.legistar.com> | A | Portal/Docs | Council agendas, meetings, minutes, legislation |
| Tarrant County | <https://www.tarrantcountytx.gov> | A | Docs/Scrape | County departments, courts, records, elections |
| Tarrant public records search | <https://tarrant.tx.publicsearch.us> | B | Portal | Public records / searchable county vendor portal |
| Tarrant County systems | <https://countyfusion.tarrantcounty.com> | B | Portal | County vendor-hosted service layer |
| Tarrant County admin/procurement surface | <https://hscmsoa.tarrantcounty.com> | B | Portal | Admin/procurement system surface |

## 2. Council / Agendas / Ordinances / Public Meetings

| Entity | Source | Tier | Access | Notes |
|---|---|---:|---|---|
| Fort Worth Legistar | <https://fortworthgov.legistar.com> | A | Portal/Docs | Core meeting intelligence source |
| City boards / commissions pages | <https://www.fortworthtexas.gov> | A | Docs/Scrape | Board membership, meeting docs, notices |
| School boards (various ISDs) | district sites | A | Docs/Scrape | Meeting agendas, bond proposals, board actions |

## 3. Elections / Representation / Districts

| Entity | Source | Tier | Access | Notes |
|---|---|---:|---|---|
| Tarrant County Elections | county site | A | Docs/Portal | Election dates, polling locations, results references |
| OpenElections | <https://openelections.net> | C | Bulk | Cross-check historic election results |
| OpenFEC API | <https://api.open.fec.gov/developers/> | A | API | Federal campaign finance relevant for congressional / federal Fort Worth races |
| Census API | <https://www.census.gov/data/developers/data-sets.html> | A | API | District demographics and population context |

## 4. Property / Appraisal / Tax / Parcel

| Entity | Source | Tier | Access | Notes |
|---|---|---:|---|---|
| Tarrant Appraisal District | <https://www.tad.org> / `tarrantappraisal.com` lead | A/B | Portal | Parcel, valuation, account lookup |
| Tarrant Tax Assessor-Collector | <https://taxoffice.tarrantcounty.com> / `tarranttax.com` lead | A/B | Portal | Tax payments, tax office processes |
| City map portal | <https://mapit.fortworthtexas.gov> | A | GIS | Parcel-adjacent and address layers |
| County public records | <https://tarrant.tx.publicsearch.us> | B | Portal | Deeds / records context |

## 5. Zoning / Planning / Development / Permits

| Entity | Source | Tier | Access | Notes |
|---|---|---:|---|---|
| City planning / development pages | <https://www.fortworthtexas.gov> | A | Docs/Scrape | Zoning, planning, permit guidance |
| Legistar | <https://fortworthgov.legistar.com> | A | Portal/Docs | Agenda-level zoning and ordinance changes |
| GIS / map layers | <https://mapit.fortworthtexas.gov> | A | GIS | Boundaries, overlays, potentially zoning layers |

## 6. Crime / Courts / Jail / Public Safety

| Entity | Source | Tier | Access | Notes |
|---|---|---:|---|---|
| Tarrant County public safety surfaces | county sites and countyfusion/publicsearch | A/B | Portal | Jail/court/records related surfaces |
| Court payment system | vendor court portal in DAO config | B | Portal | City citation/payment system surface |
| FBI Crime Data API | <https://crime-data-api-explorer.fbi.gov> | A | API | County/city crime context and benchmarking |
| Fort Worth Police / Fire pages | city site | A | Docs/Scrape | Department pages, policies, districts, notices |

## 7. Schools / ISDs / Colleges

| Entity | Source | Tier | Access | Notes |
|---|---|---:|---|---|
| FWISD | official district site | A | Docs/Scrape | Core district governance |
| Arlington ISD | official district site | A | Docs/Scrape | Regional education surface |
| Mansfield ISD | official district site | A | Docs/Scrape | Regional education surface |
| Keller ISD | official district site | A | Docs/Scrape | Regional education surface |
| HEB ISD | official district site | A | Docs/Scrape | Regional education surface |
| Birdville ISD | official district site | A | Docs/Scrape | Regional education surface |
| TCCD | <https://www.tccd.edu> | A | Docs/Scrape | College governance and services |

## 8. Transit / Roads / Infrastructure / GIS

| Entity | Source | Tier | Access | Notes |
|---|---|---:|---|---|
| Trinity Metro | <https://ridetrinitymetro.org> | A | Docs/Scrape | Transit routes, services, alerts |
| NCTCOG | <https://www.nctcog.org> | A | Docs/Bulk | Regional planning and transportation docs |
| DFW Airport | <https://www.dfwairport.com> | A | Docs/Scrape | Airport governance and ops context |
| TxDOT Open Data | <https://gis-txdot.opendata.arcgis.com/> | A | GIS/API | Roads, bridges, transportation layers |
| Fort Worth map portal | <https://mapit.fortworthtexas.gov> | A | GIS | Core local map surface |

## 9. Utilities / Water / Special Districts / Health

| Entity | Source | Tier | Access | Notes |
|---|---|---:|---|---|
| TRWD | <https://www.trwd.com> | A | Docs/Scrape | Water district, regional water infrastructure |
| JPS Health Network | <https://www.jpshealthnet.org> | A | Docs/Scrape | Public health / hospital system surface |
| Tarrant ESD 1 | <https://www.tarrantesd1.org> | A | Docs/Scrape | Emergency services district |
| WMUD and other MUDs | district sites from DAO config | A/B | Docs/Scrape | Special district governance, service boundaries |
| EPA / NOAA / HIFLD | federal sources | A | API/GIS | Waterway, air, infrastructure overlays |

## 10. Business / Nonprofits / Economic Development

| Entity | Source | Tier | Access | Notes |
|---|---|---:|---|---|
| OpenCorporates | <https://opencorporates.com> | C | API/Portal | Corporate registration cross-check |
| SEC EDGAR | <https://www.sec.gov/search-filings/edgar-application-programming-interfaces> | A | API | Public company presence / filings |
| IRS / ProPublica Nonprofit Explorer | <https://projects.propublica.org/nonprofits/api/> | A | API | Nonprofit financials |
| Chamber / economic development surfaces | official local institutional sites | A/B | Docs/Scrape | Growth, business and incentive narratives |

---

## Official APIs and Machine-Readable Sources to Layer In

| Source | Scope | Access | Relevance |
|---|---|---|---|
| U.S. Census API | demographics, housing, ACS | API | district and neighborhood context |
| FRED | macroeconomic overlays | API | economic context |
| FBI Crime Data API | crime benchmarks | API | public safety intelligence |
| OpenFEC | campaign finance | API | elections and representation |
| EPA Air/Water data | environment | API | health and infrastructure overlays |
| NOAA Weather API | alerts / observations | API | operational overlays |
| TxDOT Open Data | roads / bridges / transport | GIS/API | infrastructure layer |
| HIFLD | infrastructure datasets | GIS/Bulk | critical infrastructure mapping |

---

## Discovery Map Repos Used

These are not treated as truth sources. They are discovery maps.

| Repo | Role |
|---|---|
| `FWTX-DAO/fwtx-scraper` | source discovery map and crawl target inventory |
| `FWTX-DAO/fwtx-wiki-engine` | ontology / municipal knowledge graph design signal |

---

## Immediate Next Validation Targets

1. enumerate all 83 DAO-discovered URLs into normalized source records
2. confirm official canonical domains for each institution
3. identify which sources have:
   - API
   - GIS feature service
   - public search portal
   - downloadable docs
   - scrape-only content
4. build address-centric lookup stack for Fort Worth
5. map districts / taxes / schools / transit / utilities to address resolution
