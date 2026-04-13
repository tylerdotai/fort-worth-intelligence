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


# ─── Council District KML (Districts 2-9 available) ────────────────────────
# Districts 1 and 10 have broken KML URLs on fortworthtexas.gov.
# For those, use TCGIS/NCTCOG shapefile as fallback (not yet downloaded).

_district_polygons = {}

def load_district_polygon(district: int) -> Polygon | None:
    """Load a council district polygon from the cached GeoJSON."""
    geojson_path = CD_KML_DIR / f"district_{district}.geojson"
    if not geojson_path.exists():
        return None
    with open(geojson_path) as f:
        geo = json.load(f)
    coords = geo.get("geometry", {}).get("coordinates", [[]])[0]
    if not coords:
        return None
    # Ensure closed ring
    ring = coords + [coords[0]] if coords[0] != coords[-1] else coords
    return Polygon(ring)


def find_district_by_kml(lat: float, lon: float) -> int | None:
    """
    Point-in-polygon using cached KML GeoJSON for Districts 2-9.
    Returns the district number or None.
    """
    global _district_polygons
    point = Point(lon, lat)

    for dist in range(2, 10):
        if dist in _district_polygons:
            poly = _district_polygons[dist]
        else:
            poly = load_district_polygon(dist)
            if poly:
                _district_polygons[dist] = poly

        if poly and poly.is_valid:
            try:
                if contains(poly, point):
                    return dist
            except Exception:
                pass
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

    # 3. Council district — via KML point-in-polygon (Districts 2-9 available)
    # NOTE: Districts 1 and 10 have broken KML URLs on fortworthtexas.gov.
    #       For production, use TCGIS shapefile: https://www.tarrantcountytx.gov/gis
    # NOTE: Crime data council_district field reflects pre-redistricting (2011-2021) boundaries
    #       and is not reliable for current council district lookup.
    cd_from_kml = find_district_by_kml(lat, lon)
    cd = str(cd_from_kml) if cd_from_kml else None
    council_info = {}

    if cd:
        COUNCIL_INFO = {
            "2":  {"councilmember": "Carlos Flores",  "email": "district2@fortworthtexas.gov"},
            "3":  {"councilmember": "Michael Crain", "email": "district3@fortworthtexas.gov"},
            "4":  {"councilmember": "John Gray", "email": "district4@fortworthtexas.gov"},
            "5":  {"councilmember": "Gyna B. Johnson", "email": "district5@fortworthtexas.gov"},
            "6":  {"councilmember": "Thomas Meadows", "email": "district6@fortworthtexas.gov"},
            "7":  {"councilmember": "Tiffany D. Chase", "email": "district7@fortworthtexas.gov"},
            "8":  {"councilmember": "(verify current)", "email": "district8@fortworthtexas.gov"},
            "9":  {"councilmember": "(verify current)", "email": "district9@fortworthtexas.gov"},
            "10": {"councilmember": "(verify current — 2025 election)", "email": "district10@fortworthtexas.gov"},
            "1":  {"councilmember": "(verify current — 2025 election)", "email": "district1@fortworthtexas.gov"},
        }
        info = COUNCIL_INFO.get(str(cd), {})
        council_info = {
            "district_number": int(cd) if cd else None,
            "source": "FWPD Crime Data (authoritative)" if cd_from_fwpd else "City KML boundary (point-in-polygon)",
            "kml_available": cd_from_kml is not None,
            **info,
        }

    result["council_district"] = council_info if council_info else None
    result["_meta"]["cd_lookup"] = (
        f"kml={cd_from_kml}"
        if cd_from_kml else "not_found"
    )

    if not cd:
        result["_caveats"].append("Council district not determined — Districts 1 & 10 have broken KML links; all 10 districts need TCGIS shapefile for precision")
    if not cd:
        result["_caveats"].append("Council district could not be determined")

    # 4. Utilities
    parcel_city = parcels[0].get("situs_city", "FORT WORTH") if parcels else "FORT WORTH"
    result["utilities"] = resolve_utilities(address, parcel_city)

    # 5. State Representative — via TCGIS StateRepresentative layer (EPSG:2276)
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
            if _district_polygons is None:
                pass  # loaded on demand below
            found_district = None
            if _district_polygons:
                for d, poly in _district_polygons.items():
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
                        _district_polygons[d] = poly_d
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
