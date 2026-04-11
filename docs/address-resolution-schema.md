# Address Resolution Schema

Canonical data model for resolving a Fort Worth address into every relevant district, entity, and taxing body.

## Overview

```
Query Address
     │
     ▼
┌─────────────────────────┐
│   COORDINATES           │  ← Census geocoder (always)
│   lat, lon, quality     │
└────────┬────────────────┘
         │
    ┌────┴────────────────────────────────────┐
    ▼              ▼              ▼            ▼
┌────────┐  ┌────────────┐  ┌──────────┐  ┌───────────┐
│ PARCEL │  │ SCHOOL     │  │ COUNCIL  │  │ UTILITY   │
│ (TAD)  │  │ DISTRICT   │  │ DISTRICT │  │ DISTRICTS │
└────────┘  └────────────┘  └──────────┘  └───────────┘
    │              │              │            │
    ▼              ▼              ▼            ▼
┌──────────────────────────────────────────────────────┐
│              RESOLVED ADDRESS RECORD                  │
│  address + coordinates + parcel + districts + reps   │
└──────────────────────────────────────────────────────┘
```

## Entity Schemas

---

### 1. Coordinates

```json
{
  "lat": 32.759263,
  "lon": -97.328255,
  "geocoder": "census",
  "matched_address": "704 E WEATHERFORD ST, FORT WORTH, TX, 76102",
  "quality": " rooftop",
  "input_address": "704 E Weatherford St, Fort Worth, TX 76102"
}
```

Fields:
- `lat`, `lon` — decimal degrees, WGS84
- `geocoder` — which service resolved: `census` | `arcgis` | `nominatim` | `maps`
- `matched_address` — normalized address returned by geocoder
- `quality` — geocoder confidence: `rooftop` (exact) | `range` (interpolated) | `city` (rough)
- `input_address` — what was queried

---

### 2. Parcel (TAD)

```json
{
  "pidn": "14437-29-32",
  "gis_link": "14437-29-32",
  "mapsco": "12K",
  "address": "704 E WEATHERFORD ST",
  "city": "FORT WORTH",
  "zip": "76102",
  "owner_name": "DAILEY, TODD",
  "owner_type": "Individual",
  "market_value": 556381,
  "land_value": 150000,
  "improvement_value": 406381,
  "land_acres": 0.137,
  "land_sqft": 5968,
  "year_built": 1910,
  "improvement_year": null,
  "school_district": "FORT WORTH ISD",
  "taxing_units": ["Fort Worth", "Tarrant County", "Tarrant County Hospital", "Tarrant County College", "City of Fort Worth"],
  "exemptions": ["HS", "OV65"],
  "legal_description": "DAILEY'S SUBDIVISION BLK 29 LOT 32",
  "census_tract": "111302",
  "census_block": "1001"
}
```

Fields:
- `pidn` — Tarrant Appraisal District Parcel ID Number (10-digit legacy code)
- `gis_link` — join key to Fort Worth GIS ESRI Shape file (TAXPIN column)
- `mapsco` — MAPSCO grid reference (proxy for neighborhood + district lookup)
- `address`, `city`, `zip` — situs address
- `owner_name`, `owner_type` — Individual | Corporation | Partnership | etc.
- `market_value`, `land_value`, `improvement_value` — most recent assessed values
- `land_acres`, `land_sqft` — lot size
- `year_built` — improvement construction year
- `school_district` — full name of serving ISD
- `taxing_units` — array of all entities levying taxes on this parcel
- `exemptions` — HS (homestead), OV65 (over 65), etc.
- `legal_description` — full legal from CAD
- `census_tract`, `census_block` — decennial census geography

---

### 3. School District

```json
{
  "name": "FORT WORTH INDEPENDENT SCHOOL DISTRICT",
  "code": "FWSID",
  "type": "independent",
  "address": "100 N UNIVERSITY DR, FORT WORTH TX 76107",
  "phone": "(817) 814-2000",
  "website": "https://www.fwisd.org",
  "board_info_url": "https://www.fwisd.org/domain/33",
  "serviced_by_tad": "FORT WORTH ISD"
}
```

---

### 4. Council District

```json
{
  "district_number": 2,
  "name": "Council District 2",
  "councilmember": "Carlos Flores",
  "email": "district2@fortworthtexas.gov",
  "office_phone": "(817) 392-8802",
  "kml_url": "https://www.fortworthtexas.gov/files/ocmapfile/get/{uuid}/FCD_2.kmz",
  "boundary_source": "fortworthtexas.gov council district maps",
  "note": "Districts 1 and 10 KML URLs return 404; use Tarrant County GIS for those"
}
```

Note: Districts 1 and 10 have broken KML links on the city site. Districts 2–9 load via Google Maps proxy. Use Tarrant County election data or TCGIS boundary files as fallback for all 10.

---

### 5. Utility Districts

```json
{
  "water": {
    "provider": "City of Fort Worth Water Department",
    "account_type": "Residential",
    "service_zone": "FW1"
  },
  "electric": {
    "provider": "Oncor Electric Delivery",
    "tdsp": "Oncor"
  },
  "gas": {
    "provider": "Atmos Energy",
    "schedule": "R"
  },
  "wastewater": {
    "provider": "City of Fort Worth",
    "service_area": "Fort Worth Service Area"
  },
  "stormwater": {
    "provider": "City of Fort Worth",
    "drainage_fees_applicable": true
  }
}
```

Utility districts are inferred from city/county boundary + address, not from explicit lookup API. Service area maps available via Fort Worth Open Data (stormwater drainage districts).

---

### 6. Tarrant County Tax Office

```json
{
  "entity": "Tarrant County Tax Assessor-Collector",
  "office": "500 E 3RD ST, FORT WORTH TX 76102",
  "phone": "(817) 884-1100",
  "website": "https://www.tarrantcounty.com/tax",
  "payment_portal": "https://www.tarrantcounty.com/tax/payment",
  "tax_statement_url": "https://www.tarrantcounty.com/tax/search"
}
```

---

### 7. State Representative

```json
{
  "level": "state_house",
  "district": "91",
  "name": "Dr. James L. B. Anderson",
  "party": "Republican",
  "address": "5400 CAROSE LANE, FORT WORTH TX 76114",
  "phone": "(817) 738-3015",
  "email": "james.anderson@house.texas.gov",
  "committee": "Licensing and Administrative Procedures"
}
```

---

## Full Resolved Address Record

This is the canonical output of the address resolution pipeline:

```json
{
  "schema_version": "1.0",
  "resolved_at": "2026-04-11T04:20:00Z",
  "query_address": "704 E Weatherford St, Fort Worth, TX 76102",

  "coordinates": {
    "lat": 32.759263,
    "lon": -97.328255,
    "geocoder": "census",
    "matched_address": "704 E WEATHERFORD ST, FORT WORTH, TX, 76102",
    "quality": "rooftop"
  },

  "parcel": { /* TAD record */ },

  "school_district": { /* School District */ },

  "council_district": { /* Council District */ },

  "utilities": { /* Utility Districts */ },

  "tax_office": { /* Tarrant County Tax Office */ },

  "state_representative": { /* State House Rep */ },

  "_meta": {
    "parcel_lookup_time_ms": 12,
    "geocoder": "census",
    "data_freshness": {
      "parcel": "2025 certified roll",
      "council_district": "2025 election cycle",
      "school_district": "2024-2025 school year"
    },
    "caveats": [
      "Council districts 1 and 10 use fallback TCGIS boundaries",
      "TAD exemptions field requires manual verification for ownership claims",
      "Census tract/block is from 2020 decennial, not 2023 ACS"
    ]
  }
}
```

---

## Pipeline Implementation

```
Query address
     │
     ▼
1. Census geocoder ──────────────────────→ coordinates
     │
     │ (if found)
     ▼
2. TAD parcel lookup by GIS_Link ─────────→ parcel
     │ (from Census matched address ↔ TAD situs)
     ▼
3. School district from TAD `school_district` field
     │
     ▼
4. Council district
     ├─ Districts 2-9: Playwright → Google Maps → KML boundary → point-in-polygon
     └─ Districts 1, 10: TCGIS/NCTCOG shapefile fallback
     │
     ▼
5. Utility districts
     ├─ City of Fort Worth: address in city limits → all city utilities
     ├─ Oncor: universal service territory
     └─ Atmos: zip-code based schedule R
     │
     ▼
6. State representative
     └─ Census tract → district lookup via Texas Legiscan API
```

---

## Key Design Decisions

1. **Census over Google** — free, no API key, sufficient accuracy. ArcGIS if Census fails.
2. **TAD as the parcel anchor** — `gis_link` is the join key to Fort Worth GIS shapefiles.
3. **Council district via KML** — fragile but live. Primary fallback: TCGIS boundaries.
4. **Utility districts are deterministic** — no API needed, inferred from city/county membership.
5. **No auth required anywhere in the pipeline** — all sources are public.
