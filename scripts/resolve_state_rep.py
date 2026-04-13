#!/usr/bin/env python3
"""
Fort Worth State Representative Lookup via TCGIS polygon + static rep lookup.

Uses pyproj + shapely for point-in-polygon against TCGIS StateRepresentative
MapServer polygons (EPSG:2276), then resolves representative name from
the current member roster (88th Legislature, 2023-2026).

No API key required. TCGIS layer: public access.

Usage:
  python3 scripts/resolve_state_rep.py "704 E Weatherford St"
"""
import json, sys, os, re
from pathlib import Path
from datetime import datetime, timezone

try:
    from pyproj import Transformer
    HAS_PYPROJ = True
except ImportError:
    HAS_PYPROJ = False
    print("[WARN] pyproj not installed — state rep lookup will be skipped", file=sys.stderr)

try:
    from shapely.geometry import Point
    from shapely import contains
    HAS_SHAPELY = True
except ImportError:
    HAS_SHAPELY = False

import urllib.request, urllib.parse

# ─── Fort Worth TX House Districts (88th Legislature, 2023-2026) ─────────────
# Source: Fort Worth Chamber + TX House website
TX_HOUSE_REPS = {
    90: {
        "name": "Ramon Romero, Jr.",
        "party": "Democratic",
        "address": "1100 Congress Ave, Austin, TX 78701",
        "phone": "(512) 463-0608",
        "email": "ramon.romero@house.texas.gov",
        "district": "90",
        "occupation": "Businessman",
        "in_office_since": 2015,
    },
    91: {
        "name": "Stephanie Klick",
        "party": "Republican",
        "address": "1100 Congress Ave, Austin, TX 78701",
        "phone": "(512) 463-0656",
        "email": "stephanie.klick@house.texas.gov",
        "district": "91",
        "occupation": "Nurse",
        "in_office_since": 2013,
    },
    92: {
        "name": "Salman Bhojani",
        "party": "Democratic",
        "address": "1100 Congress Ave, Austin, TX 78701",
        "phone": "(512) 463-0714",
        "email": "salman.bhojani@house.texas.gov",
        "district": "92",
        "occupation": "Attorney / Businessman",
        "in_office_since": 2023,
    },
    93: {
        "name": "Nate Schatzline",
        "party": "Republican",
        "address": "1100 Congress Ave, Austin, TX 78701",
        "phone": "(512) 463-0682",
        "email": "nate.schatzline@house.texas.gov",
        "district": "93",
        "occupation": "Ministry",
        "in_office_since": 2023,
    },
    94: {
        "name": "Tony Tinderholt",
        "party": "Republican",
        "address": "1100 Congress Ave, Austin, TX 78701",
        "phone": "(512) 463-0724",
        "email": "tony.tinderholt@house.texas.gov",
        "district": "94",
        "occupation": "Businessman / Retired Military",
        "in_office_since": 2015,
    },
    95: {
        "name": "Nicole Collier",
        "party": "Democratic",
        "address": "1100 Congress Ave, Austin, TX 78701",
        "phone": "(512) 463-0710",
        "email": "nicole.collier@house.texas.gov",
        "district": "95",
        "occupation": "Attorney / Small Business Owner",
        "in_office_since": 2013,
    },
    96: {
        "name": "David Cook",
        "party": "Republican",
        "address": "1100 Congress Ave, Austin, TX 78701",
        "phone": "(512) 463-0494",
        "email": "david.cook@house.texas.gov",
        "district": "96",
        "occupation": "Attorney",
        "in_office_since": 2021,
    },
    97: {
        "name": "Craig Goldman",
        "party": "Republican",
        "address": "1100 Congress Ave, Austin, TX 78701",
        "phone": "(512) 463-0688",
        "email": "craig.goldman@house.texas.gov",
        "district": "97",
        "occupation": "Businessman",
        "in_office_since": 2013,
    },
    98: {
        "name": "Giovanni Capriglione",
        "party": "Republican",
        "address": "1100 Congress Ave, Austin, TX 78701",
        "phone": "(512) 463-0622",
        "email": "giovanni.capriglione@house.texas.gov",
        "district": "98",
        "occupation": "Businessman",
        "in_office_since": 2013,
    },
    99: {
        "name": "Charlie Geren",
        "party": "Republican",
        "address": "1100 Congress Ave, Austin, TX 78701",
        "phone": "(512) 463-0616",
        "email": "charlie.geren@house.texas.gov",
        "district": "99",
        "occupation": "Rancher / Businessman",
        "in_office_since": 2001,
    },
    101: {
        "name": "Chris Turner",
        "party": "Democratic",
        "address": "1100 Congress Ave, Austin, TX 78701",
        "phone": "(512) 463-0696",
        "email": "chris.turner@house.texas.gov",
        "district": "101",
        "occupation": "Communications / PR",
        "in_office_since": 2013,
    },
}

# ─── TCGIS StateRepresentative Layer ─────────────────────────────────────────
TCG_SVC = (
    "https://mapit.tarrantcounty.com/arcgis/rest/services"
    "/Dynamic/StateRepresentative/MapServer/0"
)
TX_SP_EPSG = "EPSG:2276"  # NAD83(2011) / Texas State Plane North Central (US Survey Feet)


# ─── Polygon cache ─────────────────────────────────────────────────────────────

_district_polygons = None

def load_district_polygons():
    """
    Download all TX House district polygons from TCGIS StateRepresentative layer.
    Returns dict: district_number -> shapely Polygon (EPSG:2276 coordinates).
    """
    global _district_polygons
    if _district_polygons is not None:
        return _district_polygons

    if not HAS_PYPROJ or not HAS_SHAPELY:
        print("[WARN] pyproj or shapely missing — skipping polygon load", file=sys.stderr)
        _district_polygons = {}
        return {}

    from shapely.geometry import Polygon

    params = urllib.parse.urlencode({
        "f": "json",
        "where": "1=1",
        "outFields": "District",
        "returnGeometry": "true",
        "resultRecordCount": 200,
    })
    req = urllib.request.Request(
        f"{TCG_SVC}/query?{params}",
        headers={"User-Agent": "Mozilla/5.0 (FortWorthIntelligence/1.0)"}
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        data = json.loads(r.read())

    polygons = {}
    for feat in data.get("features", []):
        d = feat["attributes"].get("District")
        rings = feat.get("geometry", {}).get("rings", [])
        if d and rings:
            try:
                polygons[d] = Polygon(rings[0])
            except Exception:
                pass

    _district_polygons = polygons
    print(f"[INFO] Loaded {len(polygons)} TX House district polygons from TCGIS", file=sys.stderr)
    return polygons


# ─── Point-in-polygon state rep lookup ───────────────────────────────────────

def find_state_rep(lat: float, lon: float) -> dict | None:
    """
    Given lat/lon (EPSG:4326), find the TX House district and representative.
    Returns dict with district info + rep details, or None.
    """
    if not HAS_PYPROJ or not HAS_SHAPELY:
        return None

    polys = load_district_polygons()
    if not polys:
        return None

    # Transform lat/lon → TX State Plane EPSG:2276
    transformer = Transformer.from_crs("epsg:4326", TX_SP_EPSG, always_xy=True)
    x, y = transformer.transform(lon, lat)
    point = Point(x, y)

    for district_num, poly in polys.items():
        if poly.is_valid:
            try:
                if contains(poly, point):
                    rep = TX_HOUSE_REPS.get(district_num, {})
                    return {
                        "level": "state_house",
                        "district": str(district_num),
                        "name": rep.get("name", "Unknown"),
                        "party": rep.get("party"),
                        "address": rep.get("address"),
                        "phone": rep.get("phone"),
                        "email": rep.get("email"),
                        "occupation": rep.get("occupation"),
                        "in_office_since": rep.get("in_office_since"),
                        "tcgis_layer": TCG_SVC,
                        "boundary_source": "TCG​IS StateRepresentative MapServer",
                    }
            except Exception:
                pass
    return None


def find_state_rep_by_tract(census_tract: str) -> dict | None:
    """
    Fallback: look up state rep by census tract number.
    Census tract format: YYYYTNNNBbbb (e.g. 111302101001).
    """
    # No direct tract→district mapping without the polygon
    return None


# ─── CLI ─────────────────────────────────────────────────────────────────────

def main():
    import argparse
    p = argparse.ArgumentParser(description="TX House rep lookup via TCGIS polygon")
    p.add_argument("address", nargs="?")
    p.add_argument("--lat", type=float)
    p.add_argument("--lon", type=float)
    args = p.parse_args()

    if not args.address and (args.lat is None or args.lon is None):
        p.print_help()
        return

    if args.address:
        # First: geocode via Census
        from resolve_address import geocode
        geo = geocode(args.address)
        if not geo or geo.get("lat") is None:
            print("[ERROR] Could not geocode address", file=sys.stderr)
            return
        lat, lon = geo["lat"], geo["lon"]
        print(f"Address: {geo.get('matched_address', args.address)}", file=sys.stderr)
        print(f"Coords: {lat:.6f}, {lon:.6f}", file=sys.stderr)
    else:
        lat, lon = args.lat, args.lon
        print(f"Coords: {lat:.6f}, {lon:.6f}", file=sys.stderr)

    result = find_state_rep(lat, lon)
    if result:
        print(f"\nState House District {result['district']} — {result['name']} ({result['party']})")
        print(f"  Phone: {result.get('phone', 'N/A')}")
        print(f"  Email: {result.get('email', 'N/A')}")
        print(f"  Occupation: {result.get('occupation', 'N/A')}")
        print(f"  In office since: {result.get('in_office_since', 'N/A')}")
        print(f"  Austin address: {result.get('address', 'N/A')}")
    else:
        print("\nState representative not found — address may be outside Tarrant County TX House districts.")


if __name__ == "__main__":
    main()
