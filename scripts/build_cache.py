#!/usr/bin/env python3
"""
Pre-geocode TAD parcels to SQLite for instant address resolution.

Workflow:
  1. Load all 283,808 Fort Worth TAD parcels
  2. For each unique normalized situs address, geocode via Census TIGER/Line
     (with rate limiting: 1 req/sec, ~79 hours for all)
  3. Store in fw_cache.db: address_normalized, lat, lon, council_district,
     school_district, tad_pidn
  4. Background fill — first pass: top 10K most-queried addresses (~3 hrs)

Usage:
  python3 scripts/build_cache.py --limit 10000    # first pass: 10K addresses
  python3 scripts/build_cache.py --fill          # background fill: all remaining
  python3 scripts/build_cache.py --query "704 E WEATHERFORD ST"  # test lookup
"""
import sqlite3, json, time, sys, requests, re
from pathlib import Path
from statistics import mean

DB_PATH = "/tmp/fort-worth-intelligence/data/fw_cache.db"
TAD_PATH = "/tmp/fort-worth-intelligence/data/tad/tad-parcels-fort-worth.json"
GEOCODER = "https://geocoding.geo.census.gov/geocoder/geographies/onelineaddress"

# ── Normalize an address for cache lookup ─────────────────────────────────────
def normalize(addr: str) -> str:
    """Canonical form for TAD + Census address matching."""
    if not addr:
        return ""
    a = addr.upper().strip()
    a = re.sub(r'\s+', ' ', a)
    a = re.sub(r'\bST\b', 'STREET', a)
    a = re.sub(r'\bDR\b', 'DRIVE', a)
    a = re.sub(r'\bAVE\b', 'AVENUE', a)
    a = re.sub(r'\bBLVD\b', 'BOULEVARD', a)
    a = re.sub(r'\bRD\b', 'ROAD', a)
    a = re.sub(r'\bLN\b', 'LANE', a)
    a = re.sub(r'\bCT\b', 'COURT', a)
    a = re.sub(r'\bPL\b', 'PLACE', a)
    a = re.sub(r'\bFW\b', 'FORT WORTH', a)
    a = re.sub(r'\bTX\b', '', a)
    a = re.sub(r'\s+\d{5}.*$', '', a)  # strip zip
    a = re.sub(r'[.,]', '', a)
    a = a.strip()
    return a

# ── Census geocoder ────────────────────────────────────────────────────────────
def geocode_census(addr: str) -> dict | None:
    """Geocode via Census TIGER/Line. Returns {lat, lon, matched_address} or None."""
    params = {
        "address": addr,
        "benchmark": "Public_AR_Current",
        "vintage": "Current_Current",
        "format": "json",
    }
    try:
        r = requests.get(GEOCODER, params=params, timeout=15,
                         headers={"User-Agent": "FortWorthIntelligence/1.0"})
        if r.status_code != 200:
            return None
        data = r.json()
        matches = data.get("result", {}).get("addressMatches", [])
        if not matches:
            return None
        m = matches[0]
        coords = m["coordinates"]
        return {
            "lat": coords["y"],
            "lon": coords["x"],
            "matched_address": m["matchedAddress"],
        }
    except Exception:
        return None

# ── SQLite schema ──────────────────────────────────────────────────────────────
SCHEMA = """
CREATE TABLE IF NOT EXISTS geocode_cache (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    addr_normalized TEXT    NOT NULL UNIQUE,
    addr_raw        TEXT,
    lat             REAL,
    lon             REAL,
    matched_address TEXT,
    council_district INTEGER,
    school_district  TEXT,
    tad_pidn        TEXT,
    geocoded_at     TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_addr_normalized ON geocode_cache(addr_normalized);
CREATE INDEX IF NOT EXISTS idx_tad_pidn ON geocode_cache(tad_pidn);
"""

# ── Build from TAD parcels ─────────────────────────────────────────────────────
def build_cache(limit: int | None = None):
    print(f"Loading TAD parcels from {TAD_PATH}...")
    with open(TAD_PATH) as f:
        tad = json.load(f)

    parcels = tad["parcels"]
    if limit:
        parcels = parcels[:limit]

    seen = set()
    total = len(parcels)
    cached = 0
    geocoded = 0
    errors = 0

    conn = sqlite3.connect(DB_PATH)
    conn.executescript(SCHEMA)
    conn.commit()

    print(f"Processing {total} parcels...")
    for i, p in enumerate(parcels):
        norm = normalize(p["situs_address"])
        if not norm or norm in seen:
            continue
        seen.add(norm)

        # Check if already cached
        row = conn.execute(
            "SELECT id FROM geocode_cache WHERE addr_normalized = ?", (norm,)
        ).fetchone()
        if row:
            cached += 1
            continue

        result = geocode_census(f"{norm}, FORT WORTH, TX")
        if result:
            conn.execute(
                """INSERT OR IGNORE INTO geocode_cache
                   (addr_normalized, addr_raw, lat, lon, matched_address, tad_pidn)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (norm, p["situs_address"], result["lat"], result["lon"],
                 result.get("matched_address", ""), p.get("account_num", ""))
            )
            geocoded += 1
        else:
            errors += 1
            conn.execute(
                """INSERT OR IGNORE INTO geocode_cache
                   (addr_normalized, addr_raw) VALUES (?, ?)""",
                (norm, p["situs_address"])
            )

        # Rate limit: 1 req/sec
        time.sleep(1.1)

        if (i + 1) % 100 == 0:
            conn.commit()
            print(f"  [{i+1}/{total}] geocoded={geocoded} errors={errors} cached={cached}")

    conn.commit()
    conn.close()
    print(f"\nDone. geocoded={geocoded} errors={errors} cached_already={cached}")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, help="Limit parcels to process")
    parser.add_argument("--fill", action="store_true", help="Fill all remaining")
    parser.add_argument("--query", type=str, help="Query the cache")
    args = parser.parse_args()

    if args.query:
        conn = sqlite3.connect(DB_PATH)
        row = conn.execute(
            "SELECT * FROM geocode_cache WHERE addr_normalized = ?",
            (normalize(args.query),)
        ).fetchone()
        cols = [d[0] for d in conn.execute("PRAGMA table_info(geocode_cache)").fetchall()]
        print(dict(zip(cols, row)) if row else "Not found")
        conn.close()
    else:
        build_cache(limit=args.limit)
