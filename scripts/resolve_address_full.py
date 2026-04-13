#!/usr/bin/env python3
"""
Fort Worth Address Resolution — Full Orchestrator

End-to-end pipeline: takes an address → returns every relevant layer in one JSON blob.

Pipeline:
  1. Census geocoder → lat/lon + normalized address
  2. TAD parcel lookup → owner, value, school, exemptions, gis_link
  3. Council district → FWPD Crime Data table (council_district field) as fast path;
       for precision: KML point-in-polygon (Districts 2-9 available)
  4. School district → from TAD `school_name` field
  5. Utility districts → deterministic from city/ETJ boundary
  6. State representative → census tract → district lookup

Usage:
  python3 resolve_address_full.py "704 E Weatherford St"
  python3 resolve_address_full.py "313 N Harding St" --output /tmp/resolved.json
"""
import json, sys, argparse, urllib.parse, urllib.request, re, time, zipfile, io
from pathlib import Path
from datetime import datetime, timezone, timedelta
from shapely.geometry import Point, Polygon
from shapely import contains
try:
    from pyproj import Transformer
    HAS_PYPROJ = True
except ImportError:
    HAS_PYPROJ = False
try:
    from shapely.geometry import Point as SPoint
    HAS_SHAPELY = True
except ImportError:
    HAS_SHAPELY = False

# ─── Paths ───────────────────────────────────────────────────────────────────
REPO      = Path(__file__).parent.parent
TAD_PATH  = REPO / "data" / "tad" / "tad-parcels-fort-worth.json"
OUT_DIR   = REPO / "data" / "resolved"
CD_KML_DIR = REPO / "data" / "council-districts"
PERMITS_PATH = REPO / "data" / "fw-permits.json"
_permits_cache = None


# ─── Census Geocoder ─────────────────────────────────────────────────────────

CENSUS_BASE = "https://geocoding.geo.census.gov/geocoder/locations/onelineaddress"

def geocode(address: str) -> dict | None:
    if not re.search(r",\s*[A-Z]{2}\s+\d{5}", address):
        address = address + ", Fort Worth, TX"
    params = urllib.parse.urlencode({
        "address": address, "benchmark": "Public_AR_Current", "format": "json",
    })
    req = urllib.request.Request(f"{CENSUS_BASE}?{params}",
        headers={"User-Agent": "FortWorthIntelligence/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.loads(r.read())
        matches = data.get("result", {}).get("addressMatches", [])
        if not matches:
            return None
        best = matches[0]
        coords = best.get("coordinates", {})
        return {
            "matched_address": best.get("matchedAddress"),
            "lat":  coords.get("y"),
            "lon":  coords.get("x"),
            "zip":  best.get("addressComponents", {}).get("zip"),
        }
    except Exception as e:
        print(f"[WARN] Census geocode failed: {e}", file=sys.stderr)
        return None


# ─── TAD Parcel ───────────────────────────────────────────────────────────────

_tad_cache = None

def load_tad():
    global _tad_cache
    if _tad_cache is not None:
        return _tad_cache
    if not TAD_PATH.exists():
        print(f"[WARN] TAD data not found at {TAD_PATH}", file=sys.stderr)
        _tad_cache = {}
        return _tad_cache
    with open(TAD_PATH) as f:
        d = json.load(f)
    parcels = d.get("parcels", [])
    # Index by normalized situs address
    idx = {}
    for p in parcels:
        addr = (p.get("situs_address") or "").upper().strip()
        if addr:
            norm = re.sub(r"\s+", " ", addr)
            idx.setdefault(norm, []).append(p)
    print(f"[OK] Loaded {len(parcels):,} TAD parcels → {len(idx):,} addresses", file=sys.stderr)
    _tad_cache = idx
    return idx


# ─── Permits ──────────────────────────────────────────────────────────────────

def load_permits():
    global _permits_cache
    if _permits_cache is not None:
        return _permits_cache
    if not PERMITS_PATH.exists():
        print(f"[WARN] Permits data not found at {PERMITS_PATH}", file=sys.stderr)
        _permits_cache = []
        return _permits_cache
    with open(PERMITS_PATH) as f:
        d = json.load(f)
    permits = d.get("permits", [])
    print(f"[OK] Loaded {len(permits):,} permits", file=sys.stderr)
    _permits_cache = permits
    return permits


def find_permits_by_coords(lat: float, lon: float, permits: list, max_results: int = 20, radius_deg: float = 0.01) -> list:
    """Find permits within radius_deg of lat/lon. Returns sorted by date desc."""
    matches = []
    for p in permits:
        coord = p.get("coordinates") or {}
        plat = coord.get("lat")
        plon = coord.get("lon")
        if plat is None or plon is None:
            continue
        if abs(plat - lat) > radius_deg or abs(plon - lon) > radius_deg:
            continue
        dist = ((plat - lat) ** 2 + (plon - lon) ** 2) ** 0.5
        matches.append((dist, p))
    matches.sort(key=lambda x: x[0])
    return [p for _, p in matches[:max_results]]


def find_parcel(address: str, geo: dict, tad_idx: dict) -> list:
    """Find TAD parcels matching address."""
    # Try exact normalized match
    norm = re.sub(r"\s+", " ", address.upper().strip())
    if norm in tad_idx:
        return tad_idx[norm]
    # Try census matched address
    if geo and geo.get("matched_address"):
        matched_norm = re.sub(r"\s+", " ", geo["matched_address"].upper().strip())
        if matched_norm in tad_idx:
            return tad_idx[matched_norm]
        # Try last part of matched address (situs may omit city/state)
        # e.g. "704 E WEATHERFORD ST, FORT WORTH, TX, 76102" → "704 E WEATHERFORD ST"
        street_part = re.sub(r",.*", "", matched_norm).strip()
        if street_part in tad_idx:
            return tad_idx[street_part]
    return []


# ─── FWPD Council District (fast path) ───────────────────────────────────────
# The FWPD crime data table has a council_district field for every incident.
# We do a nearest-point lookup by geocoding the address and querying
# the crime table for a point at that location.

FWPD_SVC = (
    "https://services5.arcgis.com/3ddLCBXe1bRt7mzj/arcgis/rest/services"
    "/CFW_Open_Data_Police_Crime_Data_Table_view/FeatureServer/0"
)

def find_council_district(lat: float, lon: float) -> str | None:
    """
    Query FWPD crime data table for the council district at a given lat/lon.
    We query for any record near that location and extract the council_district field.
    """
    # The crime table doesn't have geometry (it's a table view, no lat/lon columns).
    # We use the BLOCK_ADDRESS as a proxy — query for records near that block.
    # Since we have geocoded the address, we can query by block address.
    # Actually, the crime table doesn't have lat/lon either.
    # Best approach: query by block address from the TAD parcel.
    return None  # Council district from crime data requires address lookup, handled separately.


def find_council_district_by_block(block_address: str) -> str | None:
    """
    Query the FWPD crime table for a record matching the block address,
    returning the council district. Returns first record with non-empty council district.
    """
    # Escape single quotes
    safe = block_address.replace("'", "''")
    where = f"BLOCK_ADDRESS LIKE '{safe}%' AND CouncilDistrict <> ''"
    params = {
        "f": "json",
        "where": where,
        "outFields": "CouncilDistrict,BLOCK_ADDRESS",
        "resultRecordCount": 3,
        "returnGeometry": "false",
    }
    url = FWPD_SVC + "/query?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "FortWorthIntelligence/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            data = json.loads(r.read())
        features = data.get("features", [])
        if features:
            cd = features[0]["attributes"].get("CouncilDistrict")
            return str(cd).strip() if cd else None
    except Exception as e:
        print(f"[WARN] FWPD council district lookup failed: {e}", file=sys.stderr)
    return None


# ─── Council Districts — via mapit.fortworthtexas.gov/OpenData_Boundaries/MapServer/2 ───
# Source: https://data.fortworthtexas.gov/datasets/a97a4a16cfa240c99b4127b4728aceea_2
# All 10 districts available. Spatial ref: EPSG:2276 (NAD83 StatePlane Texas North Central, feet).

_council_polygons = {}   # cached in memory: {dist_num: {"name": str, "polygon": Polygon}}
_districts_loaded = False

# ── TX House Rep polygon cache (separate from council districts) ──────────────
_state_rep_polygons = {}   # {dist_num: Polygon}

COUNCIL_SERVICE = (
    "https://mapit.fortworthtexas.gov/ags/rest/services"
    "/CIVIC/OpenData_Boundaries/MapServer/2"
)
COUNCIL_EPSG = "EPSG:2276"

# ── council member roster (verified 2026) ────────────────────────────────────
COUNCIL_MEMBERS = {
    "2":  {"name": "Carlos Flores",        "email": "district2@fortworthtexas.gov"},
    "3":  {"name": "Michael D. Crain",      "email": "district3@fortworthtexas.gov"},
    "4":  {"name": "Charles Lauersdorf",    "email": "district4@fortworthtexas.gov"},
    "5":  {"name": "Deborah Peoples",        "email": "district5@fortworthtexas.gov"},
    "6":  {"name": "Mia Hall",              "email": "district6@fortworthtexas.gov"},
    "7":  {"name": "Macy Hill",             "email": "district7@fortworthtexas.gov"},
    "8":  {"name": "Chris Nettles",         "email": "district8@fortworthtexas.gov"},
    "9":  {"name": "Elizabeth M. Beck",      "email": "district9@fortworthtexas.gov"},
    "10": {"name": "Alan Blaylock",          "email": "district10@fortworthtexas.gov"},
    "11": {"name": "Jeanette Martinez",      "email": "district11@fortworthtexas.gov"},
}


def load_council_districts() -> dict[int, Polygon]:
    """
    Fetch all 10 Fort Worth council district polygons from mapit.fortworthtexas.gov
    and cache them.  Uses EPSG:2276 (StatePlane TX North Central, feet).
    """
    global _council_polygons, _districts_loaded
    if _districts_loaded:
        return _council_polygons
    if not (HAS_PYPROJ and HAS_SHAPELY):
        print("[WARN] pyproj or shapely not available — council district lookup disabled",
              file=sys.stderr)
        _districts_loaded = True
        return _council_polygons

    params = urllib.parse.urlencode({
        "f": "json",
        "where": "1=1",
        "outFields": "OBJECTID,NAME,DISTRICT",
        "returnGeometry": "true",
        "resultRecordCount": 20,
    })
    req = urllib.request.Request(COUNCIL_SERVICE + "/query?" + params,
                                 headers={"User-Agent": "Mozilla/5.0 (FortWorthIntelligence/1.0)"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            data = json.loads(r.read())
    except Exception as e:
        print(f"[WARN] Could not fetch council districts: {e}", file=sys.stderr)
        _districts_loaded = True
        return _council_polygons

    transformer = Transformer.from_crs("epsg:4326", COUNCIL_EPSG, always_xy=True)

    for feat in data.get("features", []):
        dist_str = str(feat["attributes"]["DISTRICT"])
        name     = feat["attributes"]["NAME"]
        rings    = feat["geometry"]["rings"][0]
        poly_coords = [(ring[0], ring[1]) for ring in rings]
        poly = Polygon(poly_coords)
        _council_polygons[int(dist_str)] = {"name": name, "polygon": poly}

    print(f"[OK] Loaded {len(_council_polygons)} council district polygons", file=sys.stderr)
    _districts_loaded = True
    return _council_polygons


def find_district_by_tcgis(lat: float, lon: float) -> int | None:
    """
    Point-in-polygon against all 10 Fort Worth council districts.
    Uses the mapit.fortworthtexas.gov OpenData_Boundaries MapServer layer 2.
    Returns the district number (2-11) or None.
    """
    if not HAS_SHAPELY or not HAS_PYPROJ:
        return None

    polygons = load_council_districts()
    if not polygons:
        return None

    # Transform lat/lon (EPSG:4326) → EPSG:2276
    pt_x, pt_y = Transformer.from_crs("epsg:4326", COUNCIL_EPSG, always_xy=True).transform(lon, lat)
    pt = Point(pt_x, pt_y)

    for dist_num in sorted(polygons.keys()):
        poly = polygons[dist_num]["polygon"]
        if poly.is_valid and poly.contains(pt):
            return dist_num
    return None


# ─── Utility Districts ────────────────────────────────────────────────────────

def resolve_utilities(address: str, city: str = "FORT WORTH") -> dict:
    """
    Determine utility service providers based on city limits.
    This is deterministic: city address → city utilities + regional utilities.
    """
    in_city = city.upper() in ["FORT WORTH", "FORT WORTH, TX"]

    result = {
        "water":       {"provider": None, "note": "outside city limits"},
        "electric":    {"provider": "Oncor Electric Delivery", "note": "universal service territory"},
        "gas":         {"provider": "Atmos Energy", "schedule": "R (residential)"},
        "wastewater":  {"provider": None, "note": "outside city limits"},
        "stormwater":  {"provider": None, "note": "outside city limits"},
    }

    if in_city:
        result["water"]     = {"provider": "City of Fort Worth Water Department", "account_type": "Residential"}
        result["wastewater"] = {"provider": "City of Fort Worth", "service_area": "Fort Worth Service Area"}
        result["stormwater"] = {"provider": "City of Fort Worth", "drainage_fees_applicable": True}

    return result


# ─── Full Pipeline ────────────────────────────────────────────────────────────

def resolve_full(address: str, output_path: str = None) -> dict:
    """
    Resolve an address through the full intelligence pipeline.
    Returns the canonical resolved record dict.
    """
    start = datetime.now(timezone.utc)
    result = {
        "schema_version": "1.0",
        "resolved_at":     start.isoformat(),
        "query_address":   address,
        "coordinates":     None,
        "parcel":          None,
        "school_district": None,
        "council_district": None,
        "utilities":       None,
        "permits":         None,
        "future_land_use": None,
        "_meta": {
            "geocoder":     None,
            "tad_lookup":   None,
            "cd_lookup":    None,
            "resolution_ms": None,
        },
        "_caveats": [],
    }

    # 1. Census geocode
    geo = geocode(address)
    result["_meta"]["geocoder"] = "census"
    if geo:
        result["coordinates"] = {
            "lat":           geo["lat"],
            "lon":           geo["lon"],
            "geocoder":      "census",
            "matched_address": geo["matched_address"],
            "zip":           geo.get("zip"),
            "quality":       "rooftop",
        }
    else:
        result["_caveats"].append("Census geocoding failed — address not resolvable")
        result["_meta"]["resolution_ms"] = int((datetime.now(timezone.utc) - start).total_seconds() * 1000)
        return result

    lat, lon = geo["lat"], geo["lon"]

    # 2. TAD parcel lookup
    tad_idx = load_tad()
    parcels = find_parcel(address, geo, tad_idx)
    if parcels:
        p0 = parcels[0]
        result["parcel"] = {
            "pidn":          p0.get("account_num"),
            "gis_link":       p0.get("gis_link"),
            "mapsco":         p0.get("mapsco"),
            "address":        p0.get("situs_address"),
            "owner_name":     p0.get("owner_name"),
            "owner_type":     p0.get("owner_type"),
            "market_value":  p0.get("total_value"),
            "land_value":     p0.get("land_value"),
            "improvement_value": p0.get("improvement_value"),
            "year_built":    p0.get("year_built"),
            "school_district": p0.get("school_name"),
            "exemptions":     p0.get("exemptions", "").split(",") if p0.get("exemptions") else [],
            "legal":          p0.get("legal_desc"),
            "census_tract":  p0.get("census_tract"),
        }
        result["school_district"] = {
            "name": p0.get("school_name"),
            "source": "TAD certified roll",
        }
        result["_meta"]["tad_lookup"] = f"matched {len(parcels)} parcel(s)"
    else:
        result["_caveats"].append("No TAD parcel found for this address")
        result["_meta"]["tad_lookup"] = "no_match"

    # 3. Council district — via mapit.fortworthtexas.gov (all 10 districts)
    cd = find_district_by_tcgis(lat, lon)
    council_info = {}
    if cd:
        member = COUNCIL_MEMBERS.get(str(cd), {})
        council_info = {
            "district_number": cd,
            "councilmember":   member.get("name", "(verify current)"),
            "email":           member.get("email", ""),
            "source":          "mapit.fortworthtexas.gov/OpenData_Boundaries/MapServer/2",
        }
    result["council_district"] = council_info if council_info else None
    result["_meta"]["cd_lookup"] = f"tcgis={cd}" if cd else "not_found"

    # 4. Utilities
    parcel_city = parcels[0].get("situs_city", "FORT WORTH") if parcels else "FORT WORTH"
    result["utilities"] = resolve_utilities(address, parcel_city)

    # 5. Permits — within 0.01 deg (~0.7 mi) of resolved coordinates
    all_permits = load_permits()
    nearby = find_permits_by_coords(lat, lon, all_permits) if all_permits and lat and lon else []
    if nearby:
        result["permits"] = {
            "count": len(nearby),
            "items": [
                {
                    "permit_no":         p.get("permit_no"),
                    "type":              p.get("permit_type"),
                    "subtype":           p.get("permit_subtype"),
                    "work_description":  p.get("work_description"),
                    "status":            p.get("current_status"),
                    "file_date":         p.get("file_date"),
                    "job_value":         p.get("job_value"),
                    "use_type":          p.get("use_type"),
                    "address":           p.get("address"),
                    "owner":             p.get("owner_name"),
                }
                for p in nearby
            ],
            "source": "City of Fort Worth Open Data",
        }
        result["_meta"]["permit_lookup"] = f"{len(nearby)} permits within ~0.7mi"
    else:
        result["permits"] = {"count": 0, "items": [], "source": "City of Fort Worth Open Data"}
        result["_meta"]["permit_lookup"] = "no permits within search radius"

    # 6. Future Land Use — FW PlanningDevelopment MapServer layer 51
    flu = resolve_future_land_use(lat, lon)
    if flu:
        result["future_land_use"] = flu
        result["_meta"]["flu_lookup"] = f'{flu.get("land_use")} in {flu.get("growth_center") or "Fort Worth"}'
    else:
        result["future_land_use"] = None
        result["_meta"]["flu_lookup"] = "not in FW planning area"

    # 7. State Representative — via TCGIS StateRepresentative layer
    # Requires pyproj + shapely. Static lookup table for Fort Worth TX House districts.
    if HAS_PYPROJ and HAS_SHAPELY and lat and lon:
        from shapely.geometry import Point as SPoint
        tcg_svc = (
            "https://mapit.tarrantcounty.com/arcgis/rest/services"
            "/Dynamic/StateRepresentative/MapServer/0"
        )
        TX_SP_EPSG = "EPSG:2276"
        TX_HOUSE_REPS = {
            90: {"name": "Ramon Romero, Jr.", "party": "Democratic",
                 "phone": "(512) 463-0608", "email": "ramon.romero@house.texas.gov"},
            91: {"name": "Stephanie Klick", "party": "Republican",
                 "phone": "(512) 463-0656", "email": "stephanie.klick@house.texas.gov"},
            92: {"name": "Salman Bhojani", "party": "Democratic",
                 "phone": "(512) 463-0714", "email": "salman.bhojani@house.texas.gov"},
            93: {"name": "Nate Schatzline", "party": "Republican",
                 "phone": "(512) 463-0682", "email": "nate.schatzline@house.texas.gov"},
            94: {"name": "Tony Tinderholt", "party": "Republican",
                 "phone": "(512) 463-0724", "email": "tony.tinderholt@house.texas.gov"},
            95: {"name": "Nicole Collier", "party": "Democratic",
                 "phone": "(512) 463-0710", "email": "nicole.collier@house.texas.gov"},
            96: {"name": "David Cook", "party": "Republican",
                 "phone": "(512) 463-0494", "email": "david.cook@house.texas.gov"},
            97: {"name": "Craig Goldman", "party": "Republican",
                 "phone": "(512) 463-0688", "email": "craig.goldman@house.texas.gov"},
            98: {"name": "Giovanni Capriglione", "party": "Republican",
                 "phone": "(512) 463-0622", "email": "giovanni.capriglione@house.texas.gov"},
            99: {"name": "Charlie Geren", "party": "Republican",
                 "phone": "(512) 463-0616", "email": "charlie.geren@house.texas.gov"},
            101: {"name": "Chris Turner", "party": "Democratic",
                  "phone": "(512) 463-0696", "email": "chris.turner@house.texas.gov"},
        }
        try:
            transformer = Transformer.from_crs("epsg:4326", TX_SP_EPSG, always_xy=True)
            x, y = transformer.transform(lon, lat)
            point = SPoint(x, y)
            # Try cached polygons first
            found_district = None
            if _state_rep_polygons:
                for d, poly in _state_rep_polygons.items():
                    if poly.is_valid and contains(poly, point):
                        found_district = d
                        break
            if found_district is None:
                # Load polygons on demand
                import urllib.request, urllib.parse
                params = urllib.parse.urlencode({
                    "f": "json", "where": "1=1", "outFields": "District",
                    "returnGeometry": "true", "resultRecordCount": 200,
                })
                req = urllib.request.Request(
                    f"{tcg_svc}/query?{params}",
                    headers={"User-Agent": "FortWorthIntelligence/1.0"}
                )
                with urllib.request.urlopen(req, timeout=60) as r:
                    tcg_data = json.loads(r.read())
                for feat in tcg_data.get("features", []):
                    d = feat["attributes"].get("District")
                    rings = feat.get("geometry", {}).get("rings", [])
                    if d and rings:
                        poly_d = Polygon(rings[0])
                        _state_rep_polygons[d] = poly_d
                        if poly_d.is_valid and contains(poly_d, point):
                            found_district = d
            if found_district:
                rep = TX_HOUSE_REPS.get(found_district, {})
                result["state_representative"] = {
                    "level": "state_house",
                    "district": str(found_district),
                    "name": rep.get("name", "Unknown"),
                    "party": rep.get("party"),
                    "phone": rep.get("phone"),
                    "email": rep.get("email"),
                    "boundary_source": "TCG​IS StateRepresentative MapServer",
                }
                result["_meta"]["state_rep_lookup"] = f"district {found_district}"
        except Exception as e:
            result["_meta"]["state_rep_lookup"] = f"error: {e}"

    # Timing
    result["_meta"]["resolution_ms"] = int(
        (datetime.now(timezone.utc) - start).total_seconds() * 1000
    )

    # Save if requested
    if output_path:
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        out_file = OUT_DIR / output_path
        with open(out_file, "w") as f:
            json.dump(result, f, indent=2)
        print(f"[WROTE] {out_file}", file=sys.stderr)

    return result


# ─── CLI ─────────────────────────────────────────────────────────────────────

# ─── Future Land Use ──────────────────────────────────────────────────────────

_FLU_SVC = (
    "https://mapit.fortworthtexas.gov/ags/rest/services"
    "/Planning_Development/PlanningDevelopment/MapServer/51"
)

def resolve_future_land_use(lat: float, lon: float) -> dict | None:
    """
    Query Future Land Use Categories for a lat/lon via ArcGIS bbox query.
    Returns land use designation, growth center, and change type.
    """
    if not (lat and lon and HAS_PYPROJ):
        return None
    try:
        from pyproj import Transformer
        transformer = Transformer.from_crs("epsg:4326", "epsg:2276", always_xy=True)
        x, y = transformer.transform(lon, lat)
        # 150m bbox around point
        bbox = f"{x-150},{y-150},{x+150},{y+150}"
        params = urllib.parse.urlencode({
            "f": "json",
            "geometry": bbox,
            "geometryType": "esriGeometryEnvelope",
            "inSR": "EPSG:2276",
            "spatialRel": "esriSpatialRelIntersects",
            "outFields": "LU,FROM_,TO_,TYPE,DOCUMENT,MU_Category,GC_NAME",
            "outSR": "EPSG:4326",
            "resultRecordCount": 5,
        })
        req = urllib.request.Request(f"{_FLU_SVC}/query?{params}", headers={"User-Agent": "FortWorthIntelligence/1.0"})
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.loads(r.read())
        features = data.get("features", [])
        if not features:
            return None
        # Deduplicate by LU
        seen = set()
        unique = []
        for f in features:
            lu = str(f["attributes"].get("LU") or "").strip()
            if lu and lu not in seen:
                seen.add(lu)
                unique.append(f["attributes"])
        if not unique:
            return None
        primary = unique[0]
        return {
            "land_use": str(primary.get("LU") or "").strip() or None,
            "designation": str(primary.get("TO_") or "").strip() or str(primary.get("LU") or "").strip(),
            "growth_center": str(primary.get("GC_NAME") or "").strip() or None,
            "change_type": str(primary.get("TYPE") or "").strip() or None,
            "document": str(primary.get("DOCUMENT") or "").strip() or None,
            "alternatives": [
                {"land_use": str(f.get("LU") or "").strip(), "growth_center": str(f.get("GC_NAME") or "").strip()}
                for f in unique[1:]
            ] if len(unique) > 1 else [],
            "source": _FLU_SVC,
        }
    except Exception as e:
        return None
def main():
    p = argparse.ArgumentParser(description="Fort Worth full address resolution")
    p.add_argument("address", nargs="?", help="Address to resolve")
    p.add_argument("--output", "-o", help="Output JSON file")
    p.add_argument("--tad-path", help="Override TAD parcels path")
    args = p.parse_args()

    if not args.address:
        p.print_help()
        return

    global TAD_PATH
    if args.tad_path:
        TAD_PATH = Path(args.tad_path)

    print(f"Resolving: {args.address}", file=sys.stderr)
    result = resolve_full(args.address, args.output)

    # Print summary
    coord = result.get("coordinates") or {}
    parcel = result.get("parcel") or {}
    cd = result.get("council_district") or {}
    school = result.get("school_district") or {}

    print()
    print(f"  Address: {coord.get('matched_address', 'N/A')}")
    print(f"  Lat/Lon: {coord.get('lat', 'N/A'):.6f}, {coord.get('lon', 'N/A'):.6f}" if coord.get('lat') else "  Lat/Lon: N/A")
    print(f"  Parcel:  {parcel.get('pidn', 'N/A')} | {parcel.get('owner_name', 'N/A')}")
    print(f"  Value:   ${parcel.get('market_value', 0):,}" if parcel.get('market_value') else "  Value: N/A")
    print(f"  School:  {school.get('name', 'N/A')}")
    print(f"  Council: District {cd.get('district_number', 'N/A')} — {cd.get('councilmember', 'N/A')}")
    if result.get('state_representative'):
        sr = result['state_representative']
        print(f"  TX House: District {sr.get('district')} — {sr.get('name')} ({sr.get('party')})")
        print(f"  TX House email: {sr.get('email', 'N/A')} | {sr.get('phone', 'N/A')}")
    water = result['utilities']['water']['provider'] if result.get('utilities') else None
    print(f"  Utilities: water={water or 'N/A'}")
    if result.get("_caveats"):
        for c in result["_caveats"]:
            print(f"  ! {c}")
    print(f"\n  Resolved in {result['_meta']['resolution_ms']}ms")

    if args.output:
        print(f"\n  → {OUT_DIR / args.output}")


if __name__ == "__main__":
    main()


