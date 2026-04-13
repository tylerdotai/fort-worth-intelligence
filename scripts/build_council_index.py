#!/usr/bin/env python3
"""
Build the council-districts/index.json from mapit.fortworthtexas.gov.

Uses curl (more reliable than urllib for this ArcGIS server).
"""
import json, subprocess, sys

SVC = "https://mapit.fortworthtexas.gov/ags/rest/services/CIVIC/OpenData_Boundaries/MapServer/2"
OUT = "/tmp/fort-worth-intelligence/data/council-districts/index.json"

cmd = [
    "curl", "-s",
    f"{SVC}/query?f=json&outFields=*&where=1%3D1&returnGeometry=true&resultRecordCount=100",
]
r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
data = json.loads(r.stdout)

features = data.get("features", [])
print(f"Fetched {len(features)} districts from MapServer")

EMAILS = {
    1: "district1@fortworthtexas.gov", 2: "district2@fortworthtexas.gov",
    3: "district3@fortworthtexas.gov", 4: "district4@fortworthtexas.gov",
    5: "district5@fortworthtexas.gov", 6: "district6@fortworthtexas.gov",
    7: "district7@fortworthtexas.gov", 8: "district8@fortworthtexas.gov",
    9: "district9@fortworthtexas.gov", 10: "district10@fortworthtexas.gov",
}

districts = {}
for feat in features:
    attrs = feat.get("attributes", {})
    geom = feat.get("geometry", {})
    name_raw = attrs.get("NAME", "")
    parts = name_raw.split(" - ", 1)
    dist_str = parts[0].strip() if parts else ""
    try:
        dist_num = int(dist_str)
    except (ValueError, TypeError):
        dist_num = dist_str
    member = parts[1].strip() if len(parts) > 1 else ""

    # Polygon rings → coordinates (EPSG:2276 projected → convert to EPSG:4326)
    rings = geom.get("rings", [[]])[0] if geom.get("rings") else []
    # Rings are in EPSG:2276 (US survey feet). Convert to EPSG:4326 (lat/lon).
    # Use pyproj if available, otherwise approximate.
    try:
        from pyproj import Transformer
        transformer = Transformer.from_crs("EPSG:2276", "EPSG:4326", always_xy=True)
        coords = [[round(x, 6), round(y, 6)] for x, y in rings]
        coords_4326 = []
        for x, y in coords:
            lon, lat = transformer.transform(x, y)
            coords_4326.append([round(lon, 6), round(lat, 6)])
    except Exception:
        # Fallback: just store raw coordinates (wrong projection, but has the shape)
        coords_4326 = [[round(x, 6), round(y, 6)] for x, y in rings]

    if coords_4326 and coords_4326[0] != coords_4326[-1]:
        coords_4326.append(coords_4326[0])

    districts[str(dist_num)] = {
        "name": dist_str,
        "district_number": dist_num,
        "member": member,
        "email": EMAILS.get(dist_num, ""),
        "geometry_2276": {"type": "Polygon", "coordinates": [[[round(x, 2), round(y, 2)] for x, y in rings]]},
        # Store as geojson (WGS84) for interoperability
        "geometry": {
            "type": "Polygon",
            "coordinates": [coords_4326],
        },
    }
    print(f"  District {dist_num}: {member or '(unknown)'}")

result = {
    "districts": districts,
    "meta": {
        "source": SVC,
        "scraped": "2026-04-13",
        "count": len(districts),
        "note": "District 1 (mayor at-large) not in this layer. Districts 2-11 are the 10 geographic seats.",
    }
}

with open(OUT, "w") as f:
    json.dump(result, f, indent=2)
print(f"\nWrote {len(districts)} districts → {OUT}")
