# Fort Worth Intelligence — Ontology

**Version:** 1.0
**Base standard:** [OGC CityGML 3.0 Conceptual Model](https://github.com/opengeospatial/CityGML-3.0CM)
**Status:** Draft — working
**Repo:** `github.com/tylerdotai/fort-worth-intelligence`

---

## Why CityGML 3.0

CityGML is the Open Geospatial Consortium's standard for semantic 3D city models — the international interchange format for urban data. Using it as our base ontology means:

- **Interoperable** — feeds FME, ArcGIS CityEngine, Cesium, and any CityGML-compatible viewer out of the box
- **Proven** — federal governments, European cities, Singapore's Virtual Singapore all use it
- **Extensible** — Application Domain Extensions (ADEs) let us add Fort Worth–specific attrs without breaking the model
- **Temporal-first** — every feature has `validFrom/validTo` for tracking changes over time
- **LOD-aware** — Levels of Detail (LOD0–LOD4) structure how we add 3D geometry as data becomes available

We use the **CityGML UML** as our schema reference. The API layer stays JSON-LD. CityGML XML encoding is added when 3D geometry is ready.

---

## CityGML 3.0 Module Coverage

| CityGML Module | Fort Worth Entity | Status |
|---|---|---|
| `Core::CityObject` | Base entity type | ✅ |
| `LandUse` | TAD parcels | ✅ |
| `Building` | Building permits, footprints | ✅ |
| `Transportation` | Street centerlines, address points | 🔜 |
| `Vegetation` | Urban tree canopy, parks | 🔜 |
| `WaterBody` | Trinity River, creek corridors | 🔜 |
| `Core::Administrative` | Council districts, voting precincts | ✅ |
| `Core::Relief` | Terrain / elevation | 🔜 |
| `CityFurniture` | Street lights, signs, infrastructure | 🔜 |
| `Energy` | Utility consumption, solar potential | 🔜 |

---

## Fort Worth ADE — Custom Extensions

Every Fort Worth–specific attribute lives in the `FW` namespace. These extend the base CityGML types.

### Base Entity

```python
@dataclass
class FortWorthCityObject:
    id: str                      # Stable ID: fw:<type>:<hash>
    gml_id: str                  # CityGML id (gml:id)
    valid_from: datetime | None  # When this record became valid
    valid_to: datetime | None    # When this record expired (None = current)
    source: str                  # Data source layer
    source_url: str | None       # Original API or file URL
```

### Address

Extends: `Core::Address`

```python
@dataclass
class Address(FortWorthCityObject):
    type: Literal["Address"]
    full_address: str            # "704 E WEATHERFORD ST, FORT WORTH, TX, 76102"
    normalized_address: str       # Uppercase, punctuation stripped
    street_number: str            # "704"
    street_name: str              # "E WEATHERFORD"
    unit: str | None
    city: str                     # "FORT WORTH"
    state: str                    # "TX"
    zip_code: str | None
    coordinates: Coordinate | None  # lat/lon in WGS84
    city_limits: bool             # True if inside FW corporate boundary
    council_district: str | None  # "9"
    census_tract: str | None
    zip_plus_4: str | None
```

### Parcel

Extends: `LandUse::LandUse`

```python
@dataclass
class Parcel(FortWorthCityObject):
    type: Literal["Parcel"]
    gis_link: str                # "14437-29-32" — section-township-range + lot
    situs_address: str            # Physical situs address
    owner_name: str | None
    owner_mailing_address: str | None
    owner_out_of_state: bool | None
    total_value: int | None      # Assessed total value (TAD)
    appraised_value: int | None
    land_value: int | None
    improvement_value: int | None
    school_name: str | None
    legal_description: str | None
    year_built: int | None
    land_use_code: str | None    # TAD land use classification
    zoning: str | None           # Current zoning
    acres: float | None
    sqft: int | None
    geometry: Polygon | None      # Parcel boundary in WGS84
```

### Permit

Extends: `Building::BuildingConstruction`

```python
@dataclass
class Permit(FortWorthCityObject):
    type: Literal["Permit"]
    permit_no: str
    permit_type: str             # "Plumbing", "Mechanical", "Commercial Building"
    work_type: str | None        # "New", "Alteration", "Repair"
    status: str                  # "Issued", "Pending", "Expired", "Finaled"
    issued_date: date | None
    finaled_date: date | None
    address: str
    coordinates: Coordinate | None
    estimated_cost: float | None
    contractor_name: str | None
    description: str | None       # Scope of work
    council_district: str | None
```

### CouncilDistrict

Extends: `Core::Administrative`

```python
@dataclass
class CouncilDistrict(FortWorthCityObject):
    type: Literal["CouncilDistrict"]
    district_number: int
    member_name: str | None
    member_email: str | None
    member_phone: str | None
    office_address: str | None
    website: str | None
    geometry: Polygon | None
```

### CouncilMeeting

Extends: `Core::Administrative`

```python
@dataclass
class CouncilMeeting(FortWorthCityObject):
    type: Literal["CouncilMeeting"]
    meeting_id: int
    meeting_name: str             # "City Council Regular Meeting"
    meeting_date: date
    meeting_time: str
    status: str                   # "Scheduled", "Confirmed", "Cancelled"
    agenda_items: list[AgendaItem]

@dataclass
class AgendaItem(FortWorthCityObject):
    type: Literal["AgendaItem"]
    file_number: str
    title: str
    category: str | None          # "Zoning", "Purchasing", "Public Hearing"
    status: str | None            # "Approved", "Denied", "Tabled", "Pending"
    council_districts: list[str]  # Affected districts
    sponsors: str | None
    outcome: str | None
    meeting_ids: list[str]         # Links to parent meetings
```

### FutureLandUse

Extends: `LandUse`

```python
@dataclass
class FutureLandUse(FortWorthCityObject):
    type: Literal["FutureLandUse"]
    land_use: str                 # "MU", "SF", "RURAL", "NC"
    designation: str              # "Mixed-Use", "Single-Family"
    growth_center: str | None     # "MUGC DOWNTOWN", "MUGC SOUTHWEST"
    change_type: str | None       # "From R1 to MU-2"
    document: str | None          # Ordinance or comp plan doc
    geometry: Polygon | None
```

### UtilityProvider

```python
@dataclass
class UtilityProvider(FortWorthCityObject):
    type: Literal["UtilityProvider"]
    service: str                  # "water", "electric", "gas", "stormwater"
    provider_name: str            # "City of Fort Worth Water Department"
    emergency_phone: str | None
    website: str | None
```

### StateRepresentative

Extends: `Core::Administrative`

```python
@dataclass
class StateRepresentative(FortWorthCityObject):
    type: Literal["StateRep"]
    chamber: str                 # "House" or "Senate"
    district: int
    member_name: str
    party: str | None
    email: str | None
    office_address: str | None
    phone: str | None
    geometry: Polygon | None      # District boundary
```

### CrimeIncident

```python
@dataclass
class CrimeIncident(FortWorthCityObject):
    type: Literal["CrimeIncident"]
    case_no: str
    reported_date: datetime
    from_date: datetime
    nature_of_call: str
    offense: str                  # e.g. "90G"
    offense_desc: str
    category: str                 # "Vandalism", "Theft", "Assault"
    block_address: str
    city: str
    beat: str | None
    division: str | None
    council_district: str | None
    attempt_complete: str        # "Attempt" or "Complete"
    location_type: str | None
    coordinates: Coordinate | None
```

---

## Relationship Types

All relationships are typed and directional. `{from}` → `{to}`.

```python
RELATIONSHIPS: dict[str, tuple[str, str]] = {
    # Spatial containment
    "address_in_council_district":  ("Address", "CouncilDistrict"),
    "address_in_census_tract":      ("Address", "CensusTract"),
    "address_in_city_limits":       ("Address", "CityBoundary"),
    "parcel_in_council_district":   ("Parcel", "CouncilDistrict"),
    "parcel_in_school_district":    ("Parcel", "SchoolDistrict"),
    "crime_in_council_district":    ("CrimeIncident", "CouncilDistrict"),

    # Ownership
    "address_has_parcel":           ("Address", "Parcel"),
    "parcel_has_owner":             ("Parcel", "Owner"),  # Owner is implicit

    # Governance
    "council_district_has_member":  ("CouncilDistrict", "CouncilMember"),  # implicit
    "meeting_has_item":             ("CouncilMeeting", "AgendaItem"),
    "item_affects_district":        ("AgendaItem", "CouncilDistrict"),
    "rep_represents_district":      ("StateRepresentative", "CouncilDistrict"),

    # Physical
    "parcel_has_building_permit":   ("Parcel", "Permit"),
    "address_has_permit":           ("Address", "Permit"),
    "land_use_designates_parcel":   ("FutureLandUse", "Parcel"),

    # Utilities
    "address_served_by_utility":    ("Address", "UtilityProvider"),
}
```

---

## Stable Entity IDs

Every entity gets a stable, content-addressable ID:

```
fw:<type>:<hash>
```

| Entity | Hash input | Example |
|---|---|---|
| Address | lower(normalized address) | `fw:addr:c3a7b9e2` |
| Parcel | upper(gis_link) | `fw:parcel:14437-29-32` |
| Permit | upper(permit_no) | `fw:permit:PP26-06398` |
| CouncilDistrict | district number | `fw:cd:9` |
| FutureLandUse | lat,lon rounded to 4dp | `fw:flu:32.7593_-97.3283` |

Hash collision handling: append 2-char suffix from base36 of collision counter.

---

## Query Patterns

### Single-entity resolve

```bash
GET /resolve?address=704+E+Weatherford+St
```

Returns all known data for one address.

### Graph traversal

```bash
GET /graph/fw:addr:c3a7b9e2?depth=1
GET /graph/fw:parcel:14437-29-32?depth=2
```

Returns all entities connected to the target at given depth.

### Domain queries

```bash
# All parcels in a district owned by out-of-state investors
GET /query/entities?type=Parcel&council_district=9&out_of_state=true

# All permits filed in the last 90 days
GET /query/entities?type=Permit&issued_after=2026-01-13

# All council agenda items affecting a district
GET /query/agenda?district=9&since=2026-01-01

# Parcels with pending zone change
GET /query/entities?type=FutureLandUse&change_type=pending
```

### Aggregate queries

```bash
# Value of all parcels owned by out-of-state investors in District 9
GET /query/aggregate?type=Parcel&group_by=owner_out_of_state&district=9&sum=total_value
```

---

## Levels of Detail (LOD)

As we add geometry data, LOD structures how we expose it:

| LOD | Geometry | When |
|---|---|---|
| LOD0 | Point (lat/lon) | Now — every entity has coordinates |
| LOD1 | Extruded footprint (building height) | TCGIS building footprints + height field |
| LOD2 | Full textured building | Aerial LiDAR + street-level imagery |
| LOD3 | Architectural detail | Survey-grade data |
| LOD4 | Interior | Not planned |

---

## Export Formats

```bash
GET /resolve?address=704+E+Weatherford+St&format=json    # Default — JSON-LD
GET /resolve?address=704+E+Weatherford+St&format=citygml # CityGML 3.0 XML
GET /resolve?address=704+E+Weatherford+St&format=geojson # GeoJSON Feature
```

CityGML export requires LOD1 geometry. GeoJSON is available now.

---

## Data Sources

| Source | Layer | Refresh cadence |
|---|---|---|
| TAD Certified Appraisal | Parcels, owners, values | Annual (January) |
| TCGIS MapServer | Council districts, addresses, permits | Weekly |
| Fort Worth Legistar | Council meetings, agenda items | Daily |
| City of Fort Worth Open Data | Utility providers | Static |
| FWPD Crime Stats | Crime incidents | Daily |
| TCGIS Future Land Use | Zoning, FLU designations | Semi-annual |
| Fort Worth GIS | Building footprints, terrain | As available |

---

## Open Issues

1. **Temporal tracking** — TAD only gives current state. Historical sales, ownership changes need TCAD + county clerk data.
2. **Address standardization** — USPS validation against DPV could clean up ~3% of addresses that don't resolve cleanly.
3. **Geometry** — Parcel polygons available but not yet joined to address records. `gis_link` join key exists but requires GIS boundary lookup.
4. **3D building data** — TCGIS has building footprints + estimated height. LOD1 export possible once geometry pipeline is built.
5. **Owner de-duplication** — "JOHN D SMITH" vs "SMITH, JOHN D" vs "SMITH JOHN" are same person. Name canonicalization needed for aggregate queries.

---

## References

- [OGC CityGML 3.0 Conceptual Model](https://github.com/opengeospatial/CityGML-3.0CM)
- [CityGML 3.0 Users Guide (PDF)](http://docs.ogc.org/DRAFTS/20-066.pdf)
- [CityGML 3.0 UML Diagrams](http://docs.ogc.org/DRAFTS/20-010.html)
- [OGC API — Features](https://ogcapi.ogc.org/features/) — API standard that pairs with CityGML
