#!/usr/bin/env python3
"""
Fort Worth Development Permits extractor.

Source: ArcGIS Hub — City of Fort Worth Open Data
  https://open-data-cfw.hub.arcgis.com/datasets/cfw-development-permits-table

Feature service (public, no token required):
  https://services5.arcgis.com/3ddLCBXe1bRt7mzj/arcgis/rest/services/CFW_Open_Data_Development_Permits_View/FeatureServer/0

Fields: Permit_No, Permit_Type, Permit_SubType, Permit_Category,
        B1_SPECIAL_TEXT, B1_WORK_DESC, Addr_No, Direction, Street_Name,
        Street_Suffix, Street_Suffix_Dir, Full_Street_Address, Zip_Code,
        Owner_Full_Name, File_Date, Current_Status, Status_Date,
        JobValue, Use_Type, Specific_Use, Units, SqFt, Location_1 (lat/lon)

Rate limit: None known; be respectful (sleep 1s between requests).
"""
import json, urllib.request, urllib.parse, sys, time, os, re
from datetime import datetime, timezone, timedelta

SVC = (
    "https://services5.arcgis.com/3ddLCBXe1bRt7mzj/arcgis/rest/services"
    "/CFW_Open_Data_Development_Permits_View/FeatureServer/0"
)
FIELDS = "*"
BATCH  = 100   # max records per request (ArcGIS default limit)
OUT_DIR = "data"


# ─── fetch ───────────────────────────────────────────────────────────────────

def fetch(query_params, min_delay=1):
    """Query the ArcGIS feature service and return JSON."""
    params = {
        "f": "json",
        "outFields": FIELDS,
        "returnGeometry": "true",
    }
    params.update(query_params)
    url = f"{SVC}/query?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (FortWorthIntelligence/1.0)"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def get_total_count():
    """Return estimated total record count."""
    data = fetch({"where": "1=1", "returnCountOnly": "true", "resultRecordCount": 1})
    return data.get("count", 0)


# ─── parse ────────────────────────────────────────────────────────────────────

def parse_permit_record(attrs):
    """
    Normalize one permit record into a clean dict.
    ArcGIS returns Unix ms timestamps for date fields.
    Address is split across fields; reassemble when Full_Street_Address is empty.
    """
    # Reassemble address from components
    full_addr = (attrs.get("Full_Street_Address") or "").strip()
    if not full_addr:
        def s(v):
            """Safely convert field to string, skip None/0."""
            if v is None or v == 0:
                return ""
            return str(v).strip()
        parts = [
            s(attrs.get("Addr_No")),
            s(attrs.get("Direction")),
            s(attrs.get("Street_Name")),
            s(attrs.get("Street_Suffix")),
            s(attrs.get("Street_Suffix_Dir")),
        ]
        full_addr = " ".join(p for p in parts if p)

    # Parse timestamps (ArcGIS returns ms since epoch)
    def parse_date(ts):
        if ts:
            return datetime.fromtimestamp(ts / 1000, tz=timezone.utc).isoformat()
        return None

    # Parse location string "(lat, lon)"
    loc_str = attrs.get("Location_1") or ""
    lat = lon = None
    m = re.search(r"\(([+-]?[\d.]+),\s*([+-]?[\d.]+)\)", str(loc_str))
    if m:
        lon, lat = float(m.group(1)), float(m.group(2))

    # JobValue may have $ or be numeric
    raw_val = attrs.get("JobValue") or ""
    job_value = None
    m2 = re.search(r"[\d,.]+", str(raw_val))
    if m2:
        try:
            job_value = float(m2.group().replace(",", ""))
        except ValueError:
            job_value = None

    return {
        "unique_id":       attrs.get("Unique_ID"),
        "permit_no":       attrs.get("Permit_No"),
        "permit_type":     attrs.get("Permit_Type"),
        "permit_subtype":  attrs.get("Permit_SubType"),
        "permit_category":  attrs.get("Permit_Category"),
        "project_name":    attrs.get("B1_SPECIAL_TEXT"),
        "work_description": attrs.get("B1_WORK_DESC"),
        "address":         full_addr.strip() or None,
        "zip_code":        attrs.get("Zip_Code"),
        "owner_name":      attrs.get("Owner_Full_Name"),
        "file_date":       parse_date(attrs.get("File_Date")),
        "current_status":  attrs.get("Current_Status"),
        "status_date":      parse_date(attrs.get("Status_Date")),
        "job_value":       job_value,
        "use_type":        attrs.get("Use_Type"),
        "specific_use":    attrs.get("Specific_Use"),
        "units":           attrs.get("Units"),
        "sqft":            attrs.get("SqFt"),
        "coordinates":     {"lat": lat, "lon": lon} if lat and lon else None,
    }


# ─── scrape ──────────────────────────────────────────────────────────────────

def scrape_all(where_clause="1=1", order_by="File_Date DESC", max_records=None,
              min_delay=1, progress=True):
    """
    Fetch all permits matching where_clause, ordered by order_by.
    Uses offset/limit pagination (ArcGIS-native approach for large datasets).
    """
    count_data = fetch({"where": "1=1", "returnCountOnly": "true", "resultRecordCount": 1})
    total = count_data.get("count", 0)
    if max_records:
        total = min(total, max_records)

    if progress:
        print(f"[INFO] Total permits matching: {total:,}", file=sys.stderr)

    records = []
    offset = 0

    while offset < total:
        batch_size = min(BATCH, total - offset)
        params = {
            "where":     where_clause,
            "resultOffset": str(offset),
            "resultRecordCount": str(batch_size),
            "orderByFields": order_by,
        }
        data = fetch(params, min_delay=min_delay)

        features = data.get("features", [])
        if not features:
            break

        for feat in features:
            parsed = parse_permit_record(feat["attributes"])
            parsed["_geometry"] = feat.get("geometry")
            records.append(parsed)

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
    """Fetch permits filed in the last `days` days."""
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")
    where = f"File_Date >= date '{cutoff}'"
    return scrape_all(where_clause=where, order_by="File_Date DESC", min_delay=min_delay)


def scrape_by_status(statuses=None, min_delay=1):
    """Fetch permits by status: Issued, Pending, Finaled, etc."""
    if not statuses:
        statuses = ["Issued", "Pending", "Finaled"]
    clauses = " OR ".join(f"Current_Status='{s}'" for s in statuses)
    return scrape_all(where_clause=f"({clauses})", order_by="File_Date DESC", min_delay=min_delay)


def scrape_by_type(permit_type, min_delay=1):
    """Fetch all permits of a specific type."""
    safe_type = permit_type.replace("'", "''")
    return scrape_all(
        where_clause=f"Permit_Type='{safe_type}'",
        order_by="File_Date DESC",
        min_delay=min_delay,
    )


def scrape_by_address(address, min_delay=1):
    """Fetch permits matching a street address (partial match)."""
    safe = address.replace("'", "''")
    return scrape_all(
        where_clause=f"Full_Street_Address LIKE '%{safe}%' OR B1_SPECIAL_TEXT LIKE '%{safe}%'",
        order_by="File_Date DESC",
        min_delay=min_delay,
    )


# ─── save ─────────────────────────────────────────────────────────────────────

def save(records, out_path):
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    result = {
        "meta": {
            "scraped_at":    datetime.now(timezone.utc).isoformat(),
            "source":         SVC,
            "total_records":  len(records),
            "sample_fields": list(records[0].keys()) if records else [],
        },
        "permits": records,
    }
    with open(out_path, "w") as f:
        json.dump(result, f, indent=2, default=str)
    print(f"[INFO] Wrote {len(records):,} permits → {out_path}", file=sys.stderr)


# ─── main ─────────────────────────────────────────────────────────────────────

def main():
    import argparse
    p = argparse.ArgumentParser(description="Fort Worth Development Permits extractor")
    p.add_argument("--output",  default="data/fw-permits.json")
    p.add_argument("--days",    type=int, default=None, help="Permits from last N days")
    p.add_argument("--type",     default=None, help="Permit type (e.g. Plumbing, Building, Mechanical)")
    p.add_argument("--status",  default=None, help="Status filter (e.g. Issued, Pending)")
    p.add_argument("--address", default=None, help="Address search (partial match)")
    p.add_argument("--max",     type=int, default=None, help="Max records to fetch")
    p.add_argument("--min-delay", type=float, default=1.0)
    args = p.parse_args()

    repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    out_path = os.path.join(repo, args.output)

    if args.days:
        print(f"[INFO] Fetching permits from last {args.days} days...", file=sys.stderr)
        records = scrape_recent(days=args.days, min_delay=args.min_delay)
    elif args.type:
        print(f"[INFO] Fetching permits of type: {args.type}", file=sys.stderr)
        records = scrape_by_type(args.type, min_delay=args.min_delay)
    elif args.status:
        print(f"[INFO] Fetching permits with status: {args.status}", file=sys.stderr)
        records = scrape_by_status([args.status], min_delay=args.min_delay)
    elif args.address:
        print(f"[INFO] Searching permits for address: {args.address}", file=sys.stderr)
        records = scrape_by_address(args.address, min_delay=args.min_delay)
    else:
        # Default: recent 30 days
        records = scrape_recent(days=30, min_delay=args.min_delay)

    if args.max:
        records = records[:args.max]

    save(records, out_path)


if __name__ == "__main__":
    main()
