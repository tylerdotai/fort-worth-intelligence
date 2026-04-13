#!/usr/bin/env python3
"""
Convert TAD certified roll TXT to JSON Lines for Fort Worth parcels.
Reads PropertyData_R_2025.txt (pipe-delimited, latin-1).
"""
import json, sys, time
from pathlib import Path

IN_PATH = Path("/app/data/tad/PropertyData_R_2025.txt")
OUT_JSONL = Path("/app/data/tad-parcels-fort-worth.jsonl")
OUT_JSON = Path("/app/data/tad/tad-parcels-fort-worth.json")
FW_CITY_CODE = "026"  # Fort Worth in TAD's city code system

SCHOOL_CODES = {
    "905": "FORT WORTH ISD",
    "220": "ARLINGTON ISD",
    "184": "BIRDVILLE ISD",
    "790": "WHITE SETTLEMENT ISD",
    "111": "EULESS ISD",
    "720": "KELLER ISD",
    "121": "GRAPEVINE-COLLEYVILLE ISD",
    "220A": "ARLINGTON ISD",
    "220B": "MANSFIELD ISD",
    "000": "UNKNOWN",
}

# Correct column indices (0-based) from PropertyData_R_2025.txt header
COLS = {
    "account_num":         2,
    "record_type":         3,
    "pidn":                5,
    "owner_name":          6,
    "owner_address":       7,
    "owner_citystate":     8,
    "owner_zip":           9,
    "situs_address":      12,
    "property_class":     13,
    "state_use":          17,
    "county":             20,
    "city":               21,
    "school":             22,
    "land_value":         32,
    "improvement_value":  33,
    "total_value":        34,
    "year_built":         38,
    "living_area":        39,
    "mapsco":             15,
    "exemption_code":     16,
    "gis_link":           53,
    "deed_date":          29,
    "deed_book":          30,
    "deed_page":          31,
    "land_acres":         43,
    "land_sqft":          44,
    "swimming_pool":      40,
    "central_heat":       47,
    "central_air":        48,
}


def parse_row(line):
    fields = line.rstrip("\r\n").split("|")
    if len(fields) < 50:
        return None
    try:
        return {k: fields[v].strip() for k, v in COLS.items()}
    except Exception:
        return None


def main():
    if not IN_PATH.exists():
        print(f"[ERROR] TAD file not found: {IN_PATH}", file=sys.stderr)
        sys.exit(1)

    fw_count = 0
    t0 = time.time()
    with open(IN_PATH, encoding="latin-1") as fin, \
         open(OUT_JSONL, "w") as fout:
        for i, line in enumerate(fin):
            if i == 0:
                continue  # skip header
            if i % 100_000 == 0 and i > 0:
                elapsed = time.time() - t0
                rate = i / elapsed
                print(f"[{i:,}] {fw_count:,} FW, {rate:.0f} rows/sec", file=sys.stderr)

            row = parse_row(line)
            if not row:
                continue

            # Only Fort Worth parcels (city code 026)
            if row.get("city", "").strip() != FW_CITY_CODE:
                continue

            # Normalize numeric fields
            for num_field in ["land_value", "improvement_value", "total_value", "year_built", "living_area", "land_sqft"]:
                v = row.get(num_field, "").strip()
                row[num_field] = int(v) if v.isdigit() else 0

            # Resolve school name from code
            school_code = row.get("school", "").strip()
            row["school_name"] = SCHOOL_CODES.get(school_code, f"UNKNOWN({school_code})")
            row["school_district"] = row["school_name"]  # alias for API

            # Exemptions as list
            exc = row.get("exemption_code", "").strip()
            row["exemptions"] = [e.strip() for e in exc.split(",") if e.strip()] if exc else []

            # Acres as float
            acres = row.get("land_acres", "").strip()
            row["land_acres"] = float(acres) if acres else 0.0

            fout.write(json.dumps(row, ensure_ascii=False) + "\n")
            fw_count += 1

    elapsed = time.time() - t0
    print(f"[DONE] {fw_count:,} Fort Worth parcels -> {OUT_JSONL} ({elapsed:.1f}s)", file=sys.stderr)

    # Convert JSONL → JSON for resolve_address_full.py
    print(f"Converting JSONL -> JSON...")
    out = {"parcels": []}
    with open(OUT_JSONL) as f:
        for line in f:
            line = line.strip()
            if line:
                out["parcels"].append(json.loads(line))
    with open(OUT_JSON, "w") as f:
        json.dump(out, f)
    print(f"Wrote {len(out['parcels']):,} parcels -> {OUT_JSON}")


if __name__ == "__main__":
    main()
