# Fort Worth Source Capability Matrix

A working matrix for how each major source class can be consumed.

## Capability legend
- **API**: documented API or direct machine-readable endpoint
- **GIS**: map service, feature service, geospatial viewer, or spatial layer endpoint
- **Portal**: searchable public records or vendor-hosted system
- **Docs**: agendas, minutes, notices, plans, departmental pages, PDFs
- **Bulk**: downloadable files or datasets
- **Scrape**: public HTML extraction required

---

## Core city / county / regional matrix

| Source Class | Example | API | GIS | Portal | Docs | Bulk | Scrape |
|---|---|---:|---:|---:|---:|---:|---:|
| City homepage / departments | fortworthtexas.gov | No | Partial | No | Yes | Partial | Yes |
| City map portal | mapit.fortworthtexas.gov | Partial | Yes | Yes | Partial | Partial | Sometimes |
| Legislative system | fortworthgov.legistar.com | No public API confirmed | No | Yes | Yes | Partial | Yes |
| County government | tarrantcountytx.gov | Limited | Partial | Partial | Yes | Partial | Yes |
| Public records vendor systems | publicsearch / countyfusion / ncourt | No public API confirmed | No | Yes | Partial | Rare | Yes |
| Appraisal / tax systems | TAD / tax office | No public API confirmed | Partial | Yes | Partial | Rare | Yes |
| School district sites | ISD official domains | Rare | Rare | Partial | Yes | Rare | Yes |
| Transit / regional planning | Trinity Metro / NCTCOG | Partial | Partial | Partial | Yes | Partial | Yes |
| Water / special districts | TRWD / MUDs / ESDs | Rare | Partial | Partial | Yes | Rare | Yes |
| Federal enrichment layers | Census / FBI / EPA / NOAA / FEC | Yes | Partial | Partial | Yes | Yes | Rare |

---

## Highest-value ingestion priorities

### 1. Address / GIS stack
Best leverage for productization.

Should combine:
- Fort Worth map portal
- parcel / appraisal references
- district boundaries
- school district boundaries
- transit overlays
- utility / special district overlays

### 2. Legislative intelligence stack
Should combine:
- Legistar
- city department pages
- board / commission pages
- planning / zoning agendas

### 3. Property / tax / district stack
Should combine:
- TAD
- tax office
- county public search
- city GIS
- district boundaries

### 4. Education governance stack
Should combine:
- ISD board agendas
- bond / election pages
- district metadata
- campus / attendance / governance references

---

## Data maturity notes

### Most mature machine-readable layers
- federal APIs (Census, FBI, EPA, NOAA, FEC)
- GIS and map portals
- some regional planning data

### Most important but portal-heavy layers
- Legistar
- county records systems
- appraisal / tax systems
- MUD and special district sites

### Most likely to need custom scraping
- school district governance pages
- special districts
- health and utility pages
- city department pages with PDFs and notices

---

## Recommended ingestion order

1. APIs and GIS first
2. vendor portals second
3. core document surfaces third
4. scrape-only long tail after that

That order gives the cleanest path from raw source inventory to usable civic intelligence infrastructure.
