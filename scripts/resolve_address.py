#!/usr/bin/env python3
"""
Fort Worth Address Resolver — Census Geocoder + TAD Parcel Join

Takes an address string → returns Fort Worth city council district,
school district, appraisal record, and owner info from TAD data.

Usage:
  python3 resolve_address.py "704 E Weatherford St"
  python3 resolve_address.py "313 N Harding St" --tad tad-parcels-fort-worth.json
"""

import json, sys, time, argparse, urllib.parse, urllib.request, re
from pathlib import Path

# ── Config ────────────────────────────────────────────────────────────────────
CENSUS_BASE = "https://geocoding.geo.census.gov/geocoder/locations/onelineaddress"
BENCHMARK   = "Public_AR_Current"

TAD_PATH    = Path(__file__).parent.parent / "data" / "tad" / "tad-parcels-fort-worth.json"
OUTPUT_DIR  = Path(__file__).parent.parent / "data" / "geocoded"


# ── TAD load (lazy, cached) ───────────────────────────────────────────────────
_tad_cache = None

def load_tad():
    global _tad_cache
    if _tad_cache is None:
        if not TAD_PATH.exists():
            print(f"[WARN] TAD data not found: {TAD_PATH}", file=sys.stderr)
            _tad_cache = {}
            return _tad_cache
        with open(TAD_PATH) as f:
            d = json.load(f)
        # Index by normalized situs address
        _tad_cache = {}
        for p in d.get("parcels", []):
            addr = p.get("situs_address", "").upper().strip()
            if addr:
                # Normalize: strip trailing spaces, collapse multiple spaces
                norm = re.sub(r"\s+", " ", addr)
                if norm not in _tad_cache:
                    _tad_cache[norm] = []
                _tad_cache[norm].append(p)
        print(f"[OK] Loaded {len(d.get('parcels',[])):,} TAD parcels → {len(_tad_cache):,} unique addresses", file=sys.stderr)
    return _tad_cache


def normalize_address(raw: str) -> str:
    """Normalize an address for TAD matching."""
    return re.sub(r"\s+", " ", raw.upper().strip())


def geocode(address: str) -> dict | None:
    """
    Geocode via Census Bureau TIGER/Line service.
    Returns dict with matchedAddress, lat, lon, or None on failure.

    The Census API requires a full address (street, city, state, zip).
    We auto-append 'Fort Worth, TX' if the address doesn't include a state.
    """
    # Auto-complete Fort Worth addresses
    if not re.search(r',\s*[A-Z]{2}\s+\d{5}', address):
        address = address + ", Fort Worth, TX"

    params = urllib.parse.urlencode({
        "address": address,
        "benchmark": BENCHMARK,
        "format": "json",
    })
    url = f"{CENSUS_BASE}?{params}"

    req = urllib.request.Request(url, headers={"User-Agent": "FortWorth-Intelligence/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
    except Exception as e:
        print(f"[WARN] Geocode failed for '{address}': {e}", file=sys.stderr)
        return None

    matches = data.get("result", {}).get("addressMatches", [])
    if not matches:
        return None

    best = matches[0]
    coords = best.get("coordinates", {})
    return {
        "matchedAddress": best.get("matchedAddress"),
        "lat":  coords.get("y"),
        "lon":  coords.get("x"),
        "tigerLineId": best.get("tigerLine", {}).get("tigerLineId"),
        "zip": best.get("addressComponents", {}).get("zip"),
    }


def find_tad_parcel(address: str, tad_index: dict) -> list:
    """
    Find TAD parcel records by address.
    Returns list of matching parcels (usually 1, can be 2+ for multi-owner).
    """
    norm = normalize_address(address)
    # Try exact match first
    if norm in tad_index:
        return tad_index[norm]

    # Try without street suffix
    addr_short = re.sub(r"\s+(ST|AVE|DR|BLVD|RD|CT|CIR|LN|TER|WAY|PL)[\s.,]*$", "", norm, flags=re.IGNORECASE).strip()
    if addr_short != norm and addr_short in tad_index:
        return tad_index[addr_short]

    # Try contains match (TAD might have slightly different formatting)
    for tad_addr, parcels in tad_index.items():
        if tad_addr.startswith(norm) or norm.startswith(tad_addr):
            return parcels

    return []


def resolve(address: str, tad_index: dict = None) -> dict:
    """
    Full address resolution: geocode + TAD parcel join.
    """
    result = {
        "input": address,
        "geocode": None,
        "parcels": [],
        "meta": {"resolved": False},
    }

    # 1. Geocode
    geo = geocode(address)
    if geo:
        result["geocode"] = geo
        result["meta"]["geocode_source"] = "Census TIGER/Line"
    else:
        print(f"[WARN] Could not geocode: '{address}'", file=sys.stderr)
        return result

    # 2. Load TAD data
    if tad_index is None:
        tad_index = load_tad()

    # 3. Find parcel by address
    parcels = find_tad_parcel(address, tad_index)

    if parcels:
        result["parcels"] = parcels
        result["meta"]["tad_lookup"] = "address_match"
    else:
        # Try geocoded matched address
        matched = geo.get("matchedAddress", "")
        if matched:
            parcels = find_tad_parcel(matched, tad_index)
            if parcels:
                result["parcels"] = parcels
                result["meta"]["tad_lookup"] = "census_matched_address"

    result["meta"]["resolved"] = len(result["parcels"]) > 0
    return result


def format_result(r: dict) -> str:
    """Format resolution result for console output."""
    lines = []
    lines.append(f"\n{'='*60}")
    lines.append(f"Address: {r['input']}")
    lines.append(f"{'='*60}")

    if r["geocode"]:
        g = r["geocode"]
        lines.append(f"\n[GEOCODE] {g.get('matchedAddress', 'N/A')}")
        lines.append(f"  lat/lon: {g.get('lat', 'N/A'):.6f}, {g.get('lon', 'N/A'):.6f}")
        lines.append(f"  ZIP: {g.get('zip', 'N/A')}")
        lines.append(f"  TIGER Line: {g.get('tigerLineId', 'N/A')}")

    parcels = r.get("parcels", [])
    if parcels:
        lines.append(f"\n[TAD PARCEL] {len(parcels)} record(s) found")
        for p in parcels:
            lines.append(f"\n  Account: {p.get('account_num', 'N/A')}")
            lines.append(f"  Owner: {p.get('owner_name', 'N/A')}")
            lines.append(f"  Situs: {p.get('situs_address', 'N/A')}")
            lines.append(f"  Mailing: {p.get('owner_address', '').strip()}, {p.get('owner_citystate', '').strip()}")
            lines.append(f"  School: {p.get('school_name', 'N/A')}")
            lines.append(f"  Year Built: {p.get('year_built', 'N/A')}")
            lines.append(f"  Living Area: {p.get('living_area', 'N/A'):,} sqft" if p.get('living_area') else "  Living Area: N/A")
            lines.append(f"  Land Value: ${p.get('land_value', 0):,}")
            lines.append(f"  Improvement Value: ${p.get('improvement_value', 0):,}")
            lines.append(f"  Total Value: ${p.get('total_value', 0):,}")
            lines.append(f"  Appraised Value: ${p.get('appraised_value', 0):,}")
            lines.append(f"  GIS Link: {p.get('gis_link', 'N/A')}")
            lines.append(f"  Legal: {p.get('legal_desc', 'N/A')[:80]}")
            lines.append(f"  MAPSCO: {p.get('mapsco', 'N/A')}")
    else:
        lines.append("\n[TAD PARCEL] No matching parcel found")

    lines.append(f"\n  Resolved: {r['meta']['resolved']}")
    return "\n".join(lines)


def main():
    p = argparse.ArgumentParser(description="Resolve a Fort Worth address to parcel + appraisal data")
    p.add_argument("address", nargs="?", help="Address to resolve")
    p.add_argument("--file", "-f", help="Output JSON file for result")
    p.add_argument("--tad", default=str(TAD_PATH), help="Path to TAD parcels JSON")
    args = p.parse_args()

    if not args.address:
        p.print_help()
        return

    # Override TAD path if specified
    global TAD_PATH
    if args.tad:
        TAD_PATH = Path(args.tad)

    tad_index = load_tad()
    result = resolve(args.address, tad_index)

    # Output
    print(format_result(result))

    if args.file:
        Path(args.file).parent.mkdir(parents=True, exist_ok=True)
        with open(args.file, "w") as f:
            json.dump(result, f, indent=2)
        print(f"\n[WROTE] {args.file}")

    # Also print a CLI-friendly summary
    if result["meta"]["resolved"]:
        p0 = result["parcels"][0]
        print(f"\nSUMMARY | {p0.get('situs_address','')} | "
              f"Owner: {p0.get('owner_name','')} | "
              f"Value: ${p0.get('total_value',0):,} | "
              f"School: {p0.get('school_name','')}")


if __name__ == "__main__":
    main()
