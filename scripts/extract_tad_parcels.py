#!/usr/bin/env python3
"""
TAD Certified Appraisal Data Extractor
Tarrant Appraisal District — Fort Worth residential properties

Source: https://www.tad.org/content/data-download/PropertyData_R_2025(Certified).ZIP
Format: Pipe-delimited TXT, 56 fields per row

Usage:
  python extract_tad_parcels.py                      # full run
  python extract_tad_parcels.py --limit 1000        # first 1000 rows for testing
  python extract_tad_parcels.py --city "FORT WORTH" # filter by city
  python extract_tad_parcels.py --account 00001309  # single account lookup
"""

import json, zipfile, re, sys, time, argparse
from pathlib import Path

SOURCE_ZIP  = Path(__file__).parent.parent / "data" / "tad" / "PropertyData_R_2025(Certified).ZIP"
SOURCE_FILE = "PropertyData_R_2025.txt"
OUTPUT_FILE = Path(__file__).parent.parent / "data" / "tad-parcels.json"

# ── column indices (0-based) ──────────────────────────────────────────────────
COLS = {
    "record_type":      0,
    "appraisal_year":   1,
    "account_num":      2,
    "record_type_full": 3,
    "sequence_no":      4,
    "pidn":             5,
    "owner_name":       6,
    "owner_address":    7,
    "owner_citystate":  8,
    "owner_zip":        9,
    "situs_address":   12,
    "property_class":  13,
    "tad_map":         14,
    "mapsco":          15,
    "exemption_code":  16,
    "state_use":       17,
    "legal_desc":      18,
    "notice_date":     19,
    "county_cd":       20,
    "city_cd":         21,
    "school_cd":       22,
    "num_special_dist":23,
    "spec1":           24,
    "spec2":           25,
    "spec3":           26,
    "spec4":           27,
    "spec5":           28,
    "deed_date":       29,
    "deed_book":       30,
    "deed_page":       31,
    "land_value":      32,
    "improvement_value":33,
    "total_value":     34,
    "garage_capacity": 35,
    "num_bedrooms":    36,
    "num_bathrooms":   37,
    "year_built":      38,
    "living_area":     39,
    "swimming_pool":   40,
    "arb_indicator":   41,
    "ag_code":         42,
    "land_acres":      43,
    "land_sqft":       44,
    "ag_acres":        45,
    "ag_value":        46,
    "central_heat":    47,
    "central_air":     48,
    "structure_count": 49,
    "appraisal_date":  51,
    "appraised_value": 52,
    "gis_link":        53,
    "instrument_no":   54,
    "overlap_flag":    55,
}

SCHOOL_CODES = {
    "905": "FORT WORTH ISD",
    "220": "ARLINGTON ISD",
    "184": "BIRDVILLE ISD",
    "790": "WHITE SETTLEMENT ISD",
    "220A":"ARLINGTON ISD",
    "111": "EULESS ISD",
    "720": "KELLER ISD",
    "121": "GRAPEVINE-COLLEYVILLE ISD",
    "220B":"MANSFIELD ISD",
}

CITY_CODES = {
    "026": "FORT WORTH",
    "000": "UNKNOWN",
}

COUNTY_CODES = {
    "220": "TARRANT",
}


def parse_row(line, line_no):
    """Parse one pipe-delimited row. Returns dict or None if invalid."""
    try:
        fields = line.rstrip(b"\r\n").split(b"|")
        if len(fields) < 56:
            return None
        # Decode bytes to strings for all field comparisons and extractions
        try:
            fields = [f.decode("latin-1") for f in fields]
        except Exception:
            return None
    except Exception:
        return None

    if fields[COLS["record_type"]] != "R":
        return None  # skip header / non-residential

    def f(key):
        return fields[COLS[key]].strip()

    # Parse numeric fields
    def num(key, default=0):
        try: return int(f(key).strip())
        except: return default

    def flt(key, default=0.0):
        try: return float(f(key).strip())
        except: return default

    account = f("account_num").lstrip("0")
    city_cd  = f("city_cd")
    school_cd = f("school_cd")
    deed_date = f("deed_date")

    return {
        "account_num":      account,
        "pidn":             f("pidn"),
        "owner_name":       f("owner_name"),
        "owner_address":    f("owner_address"),
        "owner_citystate":  f("owner_citystate"),
        "owner_zip":        f("owner_zip"),
        "situs_address":    f("situs_address"),
        "property_class":   f("property_class"),
        "tad_map":          f("tad_map"),
        "mapsco":           f("mapsco"),
        "exemption_code":   f("exemption_code"),
        "state_use":        f("state_use"),
        "legal_desc":       f("legal_desc"),
        "deed_date":        deed_date,
        "deed_book":        f("deed_book"),
        "deed_page":        f("deed_page"),
        "land_value":       num("land_value"),
        "improvement_value":num("improvement_value"),
        "total_value":      num("total_value"),
        "year_built":       num("year_built"),
        "living_area":      num("living_area"),
        "num_bedrooms":     num("num_bedrooms"),
        "num_bathrooms":    num("num_bathrooms"),
        "land_acres":       flt("land_acres"),
        "land_sqft":        num("land_sqft"),
        "arb_indicator":    f("arb_indicator"),
        "swimming_pool":    f("swimming_pool"),
        "central_heat":     f("central_heat"),
        "central_air":      f("central_air"),
        "gis_link":         f("gis_link"),
        "appraised_value":  num("appraised_value"),
        "city_cd":          city_cd,
        "school_cd":        school_cd,
        "city_name":        CITY_CODES.get(city_cd, f"UNKNOWN({city_cd})"),
        "school_name":      SCHOOL_CODES.get(school_cd, f"UNKNOWN({school_cd})"),
        "appraisal_year":   int(f("appraisal_year")) if f("appraisal_year").isdigit() else 2025,
        "source_line":      line_no,
    }


def run(city=None, school=None, account=None, limit=None, output_file=None):
    """Extract TAD residential parcels from the certified export."""

    if not SOURCE_ZIP.exists():
        print(f"[ERROR] Source file not found: {SOURCE_ZIP}")
        print("  Download from: https://www.tad.org/content/data-download/PropertyData_R_2025(Certified).ZIP")
        sys.exit(1)

    output_file = output_file or OUTPUT_FILE
    output_file = Path(output_file)
    output_file.parent.mkdir(parents=True, exist_ok=True)

    matches = []
    seen_accounts = set()
    total_rows = 0
    skipped = 0

    print(f"Reading: {SOURCE_ZIP}")

    with zipfile.ZipFile(SOURCE_ZIP) as z:
        with z.open(SOURCE_FILE) as fh:
            for line_no, raw in enumerate(fh, 1):
                total_rows += 1
                if limit and total_rows > limit + 1:
                    break

                # skip header
                if raw.startswith(b"RP|"):
                    continue

                row = parse_row(raw, line_no)
                if row is None:
                    skipped += 1
                    continue

                # filter
                if account:
                    if row["account_num"] != account:
                        continue

                if city:
                    c = row.get("city_name", "").upper()
                    if city.upper() not in c:
                        continue

                if school:
                    s = row.get("school_name", "").upper()
                    if school.upper() not in s:
                        continue

                # deduplicate by account
                if row["account_num"] in seen_accounts:
                    continue
                seen_accounts.add(row["account_num"])
                matches.append(row)

                if limit and len(matches) >= limit:
                    break

                if len(matches) % 10000 == 0:
                    print(f"  ... {len(matches)} matches so far")

    print(f"\nTotal rows read: {total_rows-1}")
    print(f"Skipped (invalid/non-res): {skipped}")
    print(f"Matched: {len(matches)}")

    result = {
        "meta": {
            "source": str(SOURCE_ZIP),
            "appraisal_year": 2025,
            "record_type": "residential_certified",
            "pipe_delimited": True,
            "scraped_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "filters": {
                "city": city,
                "school": school,
                "account": account,
                "limit": limit,
            },
            "total_rows_read": total_rows - 1,
            "matched": len(matches),
        },
        "parcels": matches,
    }

    with open(output_file, "w") as fh:
        json.dump(result, fh, indent=2)

    print(f"\nWrote {len(matches)} parcels → {output_file}")
    return result


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Extract TAD Fort Worth residential parcels")
    p.add_argument("--city",    help="Filter by city name (partial match)")
    p.add_argument("--school",  help="Filter by school district name (partial match)")
    p.add_argument("--account", help="Single account number (no leading zeros)")
    p.add_argument("--limit",   type=int, help="Max rows to process (for testing)")
    p.add_argument("--output",  help="Output JSON path")
    args = p.parse_args()

    run(city=args.city, school=args.school, account=args.account,
        limit=args.limit, output_file=args.output)
