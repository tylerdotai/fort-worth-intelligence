#!/usr/bin/env python3
"""
Fort Worth Open Data Catalog Scraper.

Uses the ArcGIS FeatureServer root index (services5.arcgis.com) to enumerate
all available datasets, then cross-references against priority public-facing
catalogs.

Usage:
  python3 scripts/scrape_fw_catalog.py
"""
import json, requests, sys
from pathlib import Path
from datetime import datetime, timezone

BASE = "https://services5.arcgis.com/3ddLCBXe1bRt7mzj/arcgis/rest/services"
OUT  = "data/raw/fw-open-data-catalog.json"

# Priority datasets — manually curated from the 210-service FeatureServer index.
# These are the high-value, actively maintained public-facing datasets.
PRIORITY_NAMES = {
    "CFW_Current_Traffic_Accidents",
    "CFW_Open_Data_Police_Crime_Data_Table_view",
    "CFW_Open_Data_Development_Permits_View",
    "CFW_Open_Data_Code_Violations_Table_view",
    "CFW_Open_Data_Certificates_of_Occupancy_Table_view",
    "CFW_Open_Data_Nearby_Facilities_Table_view",
    "CFW_Parcels_View",
    "CFW_Park_Boundaries_view",
    "CFW_FutureLandUse",
    "Neighborhoods_24_03_25",
    "Neighborhood_Boundaries",
    "city_boundary",
    "Designated_Investment_Zones",
    "Floodplain_CFW_ETJ",
    "ServiceDistricts_Simple_view",
    "Neighborhood_Empowerment_Zones",
}

LABELS = {
    "CFW_Current_Traffic_Accidents": "CFW Traffic Accidents",
    "CFW_Open_Data_Police_Crime_Data_Table_view": "FWPD Crime Data",
    "CFW_Open_Data_Development_Permits_View": "Development Permits",
    "CFW_Open_Data_Code_Violations_Table_view": "Code Violations",
    "CFW_Open_Data_Certificates_of_Occupancy_Table_view": "Certificates of Occupancy",
    "CFW_Open_Data_Nearby_Facilities_Table_view": "Nearby Facilities",
    "CFW_Parcels_View": "FW Parcels",
    "CFW_Park_Boundaries_view": "Park Boundaries",
    "CFW_FutureLandUse": "Future Land Use",
    "Neighborhoods_24_03_25": "Neighborhoods",
    "Neighborhood_Boundaries": "Neighborhood Boundaries",
    "city_boundary": "City Boundary",
    "Designated_Investment_Zones": "Designated Investment Zones",
    "Floodplain_CFW_ETJ": "Floodplain (ETJ)",
    "ServiceDistricts_Simple_view": "Service Districts",
    "Neighborhood_Empowerment_Zones": "Neighborhood Empowerment Zones",
}


def get_count(svc_name, svc_type):
    """Get feature count for a service."""
    if "FeatureServer" in svc_type:
        url = f"{BASE}/{svc_name}/FeatureServer/0"
    else:
        url = f"{BASE}/{svc_name}/MapServer/0"
    try:
        r = requests.get(url + "/query", params={
            "f": "json", "where": "1=1", "returnCountOnly": "true"
        }, timeout=15, headers={"User-Agent": "FortWorthIntelligence/1.0"})
        d = r.json()
        return d.get("count", -1)
    except Exception:
        return -1


def main():
    print(f"Fetching FeatureServer index from {BASE}...", file=sys.stderr)
    r = requests.get(BASE, params={"f": "json"}, timeout=30,
                     headers={"User-Agent": "FortWorthIntelligence/1.0"})
    all_services = r.json().get("services", [])
    print(f"Total services: {len(all_services)}", file=sys.stderr)

    datasets = {}
    matched = 0

    for svc in all_services:
        name = svc["name"]
        if name not in PRIORITY_NAMES:
            continue

        svc_type = svc["type"].lower().replace("featureserver", "feature server")
        url = svc.get("url", f"{BASE}/{name}/FeatureServer")
        count = get_count(name, svc["type"])

        datasets[name] = {
            "name":           LABELS.get(name, name),
            "type":           svc_type,
            "service_url":    url,
            "feature_server": f"{url}/0",
            "record_count":   count,
        }
        matched += 1
        print(f"  ✅ {name} ({svc_type}, {count:,} records)", file=sys.stderr)

    result = {
        "meta": {
            "source":       BASE,
            "scraped_at":   datetime.now(timezone.utc).isoformat(),
            "method":       "FeatureServer index enumeration",
            "total_services": len(all_services),
            "matched_priority": matched,
        },
        "datasets": datasets,
    }

    out_path = Path(__file__).parent.parent / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(result, f, indent=2)

    print(f"\nWrote {matched} datasets → {out_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
