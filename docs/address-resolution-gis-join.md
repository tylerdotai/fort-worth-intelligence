# Address Resolution + GIS Join Architecture

## The GIS_Link field

From the TAD data dictionary (2022):

> **GIS_Link** (position 529, 25 chars): Link for GIS to ESRI Shape file **TAXPIN** column

> **PIDN** (Parcel Identification Number): modulus-11 number permanently assigned to each parcel

The PIDN format encodes the property's location using the subdivision "Block and Lot" system:
- Positions 1-6: Addition/Abstract code (numeric, or 'A' prefix for abstracts)
- Positions 7-10: Block Base
- Position 11: Block Suffix
- Positions 12-15: Lot Base
- Position 16: Lot Suffix
- Positions 17-18: Tag

Example: `14437-29-32` = Addition 14437, Block 29, Lot 32

This is a **legacy Fort Worth / Tarrant County subdivision coding system**, not a modern coordinate system.

## How to join to parcel geometry

### Path A — Fort Worth MapIt GIS Portal (PREFERRED)

Fort Worth publishes GIS data via `mapit.fortworthtexas.gov`. The HTML source lists these bulk download ZIPs:
- `CAD_ABSTRACTS.zip` — CAD boundary drawings
- `POL_COUNCIL_DISTRICTS.zip` — council district polygons
- `POL_CITY_LIMIT.zip` — city limit boundary
- `City_Flood_Risk_Areas.zip` — flood zones

These appear to be internal URLs (`apitwest.fortworthtexas.gov/...`) not directly internet-accessible.

**What works:** Search `mapit.fortworthtexas.gov` directly in a browser — the files are served to browsers but blocked to direct HTTP access (likely IP-restricted or session-cookie gated).

**Alternative:** Fort Worth's OpenCities CMS at `fortworthtexas.gov` is a Granicus platform. The ArcGIS REST services for Fort Worth GIS are typically at:
- `gis.fortworthtexas.gov/arcgis/rest/services` (currently not responding)
- Try: `https://[fw-gis-ip]/arcgis/rest/services` if you have an internal IP

### Path B — Tarrant County CAD Data

Tarrant County Appraisal District provides parcel boundary data. The `GIS_Link` field is the join to the county's ESRI layer.

Key Tarrant County resources:
- Tarrant County Clerk: `tcpct.devocid.com` or similar
- Tarrant County CAD: `tarrantcad.gov`
- Tarrant County open data portal (if exists)

### Path C — ArcGIS World Geocoding Service

The simplest production approach for address → lat/lon:

1. **Census Geocoder** (free, no API key):
```
https://geocoding.geo.census.gov/geocoder/locations/address
  ?street=704+E+WEATHERFORD+ST
  &city=FORT+WOTH
  &state=TX
  &benchmark=Public_AR_Current
  &format=json
```

2. **ArcGIS World Geocoding Service** (requires token, but has free tier):
```
https://geocode.arcgis.com/arcgis/rest/services/World/GeocodeServer/findAddressCandidates
  ?singleLine=704+E+WEATHERFORD+ST,+FORT+WOTH,+TX
  &f=json
  &maxLocations=1
```

3. **OpenStreetMap Nominatim** (free, rate-limited):
```
https://nominatim.openstreetmap.org/search
  ?q=704+E+WEATHERFORD+ST,+FORT+WOTH,+TX,+76102
  &format=json
  &limit=1
```

### Path D — MAPSCO grid reference

The `MAPSCO` field in TAD data provides a grid reference:
- Format: `063W` (section + half-mile grid)
- This maps to Fort Worth's MAPSCO street guide system
- Not a direct coordinate, but sufficient for district lookup

MAPSCO codes can be used to:
1. Look up which city council district
2. Look up which school district
3. Look up which neighborhood/census tract

## Recommended Architecture

```
Fort Worth Address
       |
       v
Census Geocoder API (free) --> lat/lon
       |
       v
Fort Worth GIS Council District API
(or join to POL_COUNCIL_DISTRICTS shapefile)
       |
       v
TAD Parcel Lookup by lat/lon buffer
(GIS_Link = TAXPIN join)
       |
       v
Parcel record: owner, value, school, exemptions
```

## Implementation Plan

1. **Geocode all 283,808 Fort Worth addresses** via Census Geocoder batch API
   - Rate limit: 1 request/second for free tier
   - Cost: $0 (Census is free)
   - Estimated time: ~79 hours for full batch
   - Alternative: Use LocationIQ or similar for faster batch

2. **Build council district lookup** using Fort Worth's council district shapefile
   - Available via Tarrant County open data or NCTCOG

3. **Join geocoded points to council districts** using shapely/pyshp or PostGIS

4. **Join to TAD parcel data** via GIS_Link or lat/lon spatial join

## Quick Win First

Even without GIS joins, the TAD address data alone is immediately useful:
- Fort Worth property owner database (283K records)
- School district distribution across Fort Worth
- New construction signals (year built 2020+)
- Value distribution by council district area

The MAPSCO field can serve as a proxy for district lookup without geocoding.
