#!/usr/bin/env python3
"""
Fort Worth Police Department Crime Data extractor.

Source: ArcGIS Hub — City of Fort Worth Open Data
  https://open-data-cfw.hub.arcgis.com/datasets/cfw-police-crime-data-table

Feature service (public, no token required):
  https://services5.arcgis.com/3ddLCBXe1bRt7mzj/arcgis/rest/services/
      CFW_Open_Data_Police_Crime_Data_Table_view/FeatureServer/0

Fields: Case_No, Reported_Date, Nature_Of_Call, From_Date, Offense,
        Offense_Desc, BLOCK_ADDRESS, City, State, Beat, Division,
        CouncilDistrict, Attempt_Complete, Location_Type,
        LocationTypeDescription

Note: Addresses are redacted to 100-block level for privacy.
      Council district and police beat are included.

Rate limit: None known; be respectful (sleep 1s between requests).
"""
import json, urllib.request, urllib.parse, sys, time, os, re
from datetime import datetime, timezone, timedelta

SVC = (
    "https://services5.arcgis.com/3ddLCBXe1bRt7mzj/arcgis/rest/services"
    "/CFW_Open_Data_Police_Crime_Data_Table_view/FeatureServer/0"
)
FIELDS = "*"
BATCH  = 100
OUT_DIR = "data"


# ─── fetch ───────────────────────────────────────────────────────────────────

def fetch(query_params, min_delay=1):
    params = {"f": "json", "outFields": FIELDS, "returnGeometry": "true"}
    params.update(query_params)
    url = f"{SVC}/query?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (FortWorthIntelligence/1.0)"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def get_count(where_clause="1=1"):
    data = fetch({"where": where_clause, "returnCountOnly": "true", "resultRecordCount": 1})
    return data.get("count", 0)


# ─── parse ────────────────────────────────────────────────────────────────────

def parse_date(val):
    """Parse From_Date / Reported_Date — stored as ISO string 'YYYY-MM-DDTHH:MM:SS'."""
    if not val:
        return None
    try:
        if isinstance(val, str):
            if "T" in val:
                return val
            # Maybe it's an ms timestamp
            return datetime.fromtimestamp(int(val) / 1000, tz=timezone.utc).isoformat()
        return None
    except (ValueError, OSError, OverflowError):
        return None


OFFENSE_CATEGORIES = {
    "PC 30": "Burglary",
    "PC 31": "Theft",
    "PC 42": "Assault",
    "PC 22": "Robbery",
    "PC 19": "Homicide",
    "PC 20": "Homicide",
    "PC 21": "Homicide",
    "PC 13": "Homicide",
    "PC 14": "Homicide",
    "PC 15": "Homicide",
    "PC 28": "Theft/Auto",
    "PC 30.04": "Vehicle Crime",
    "PC 30.05": "Criminal Trespass",
    "PC 30.02": "Burglary",
    "PC 30.03": "Burglary",
    "PC 32": "Vehicle Crime",
    "PC 33": "Vehicle Crime",
    "PC 35": "Drug/Narcotics",
    "PC 38": "Vandalism",
    "PC 46": "Weapon",
    "PC 49": "Weapon",
    "PC 50": "Weapon",
    "PC 51": "Weapon",
    "GC 80": "Public Order",
    "GC 90": "Public Order",
    "HC 80": "Health/Safety",
}


def categorize(offense_desc):
    """Coarse category from offense description."""
    for prefix, cat in OFFENSE_CATEGORIES.items():
        if prefix in str(offense_desc):
            return cat
    return "Other"


def parse_record(attrs):
    """Normalize one crime record."""
    offense_desc = attrs.get("Offense_Desc") or ""

    return {
        "case_no":              attrs.get("Case_No"),
        "reported_date":       parse_date(attrs.get("Reported_Date")),
        "from_date":           parse_date(attrs.get("From_Date")),
        "nature_of_call":       attrs.get("Nature_Of_Call"),
        "offense":             attrs.get("Offense"),
        "offense_desc":        offense_desc,
        "category":            categorize(offense_desc),
        "block_address":       (attrs.get("BLOCK_ADDRESS") or "").strip() or None,
        "city":                attrs.get("City"),
        "state":               attrs.get("State"),
        "beat":                attrs.get("Beat"),
        "division":            attrs.get("Division"),
        "council_district":    str(attrs.get("CouncilDistrict") or "").strip() or None,
        "attempt_complete":    attrs.get("Attempt_Complete"),
        "location_type":        attrs.get("Location_Type"),
        "location_desc":       attrs.get("LocationTypeDescription"),
    }


# ─── scrape ──────────────────────────────────────────────────────────────────

def scrape_all(where_clause="1=1", order_by="From_Date DESC", max_records=None,
               min_delay=1, progress=True):
    """
    Fetch all crime records matching where_clause.
    Uses offset pagination (ArcGIS resultOffset).
    """
    total = get_count(where_clause)
    if max_records:
        total = min(total, max_records)

    if progress:
        print(f"[INFO] Total records matching: {total:,}", file=sys.stderr)

    records = []
    offset = 0

    while offset < total:
        batch_size = min(BATCH, total - offset)
        params = {
            "where":              where_clause,
            "resultOffset":       str(offset),
            "resultRecordCount": str(batch_size),
            "orderByFields":      order_by,
        }
        data = fetch(params, min_delay=min_delay)
        features = data.get("features", [])
        if not features:
            break

        for feat in features:
            records.append(parse_record(feat["attributes"]))

        if progress:
            print(f"[OK] fetched {offset + len(features):,} / {total:,}", file=sys.stderr)

        offset += len(features)
        time.sleep(min_delay)

        if len(features) < batch_size:
            break
        if max_records and len(records) >= max_records:
            records = records[:max_records]
            break

    return records


def scrape_recent(days=30, min_delay=1):
    """Fetch crime records from the last N days."""
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")
    where = f"From_Date >= date '{cutoff}'"
    return scrape_all(where_clause=where, order_by="From_Date DESC", min_delay=min_delay)


def scrape_by_council_district(district, min_delay=1):
    """Fetch records for a specific council district."""
    where = f"CouncilDistrict='{district}'"
    return scrape_all(where_clause=where, order_by="From_Date DESC", min_delay=min_delay)


def scrape_by_category(category, min_delay=1):
    """Fetch records by category (must match offense_desc prefix)."""
    # Map category to offense prefixes
    prefix_map = {
        "Burglary":  "PC 30",
        "Theft":     "PC 31",
        "Assault":   "PC 42",
        "Vehicle":   "PC 32",
        "Drug":      "PC 35",
        "Weapon":    "PC 46",
    }
    prefix = prefix_map.get(category, category)
    where = f"Offense_Desc LIKE '%{prefix}%'"
    return scrape_all(where_clause=where, order_by="From_Date DESC", min_delay=min_delay)


# ─── save ─────────────────────────────────────────────────────────────────────

def save(records, out_path):
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    result = {
        "meta": {
            "scraped_at":    datetime.now(timezone.utc).isoformat(),
            "source":         SVC,
            "total_records":  len(records),
            "sample_fields":  list(records[0].keys()) if records else [],
        },
        "crimes": records,
    }
    with open(out_path, "w") as f:
        json.dump(result, f, indent=2, default=str)
    print(f"[INFO] Wrote {len(records):,} crime records → {out_path}", file=sys.stderr)


# ─── main ─────────────────────────────────────────────────────────────────────

def main():
    import argparse
    p = argparse.ArgumentParser(description="Fort Worth Police Crime Data extractor")
    p.add_argument("--output",   default="data/fw-crime.json")
    p.add_argument("--days",     type=int, default=7,  help="Records from last N days (default: 7)")
    p.add_argument("--district",  type=str,  default=None, help="Council district (e.g. 2, 5, 7)")
    p.add_argument("--category", type=str, default=None, help="Category: Burglary, Theft, Assault, Vehicle, Drug, Weapon")
    p.add_argument("--max",      type=int, default=None, help="Max records")
    p.add_argument("--min-delay", type=float, default=1.0)
    args = p.parse_args()

    repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    out_path = os.path.join(repo, args.output)

    if args.district:
        print(f"[INFO] Fetching crime records for district {args.district}...", file=sys.stderr)
        records = scrape_by_council_district(args.district, min_delay=args.min_delay)
    elif args.category:
        print(f"[INFO] Fetching crime records category: {args.category}", file=sys.stderr)
        records = scrape_by_category(args.category, min_delay=args.min_delay)
    else:
        print(f"[INFO] Fetching crime records from last {args.days} days...", file=sys.stderr)
        records = scrape_recent(days=args.days, min_delay=args.min_delay)

    if args.max:
        records = records[:args.max]

    save(records, out_path)


if __name__ == "__main__":
    main()
