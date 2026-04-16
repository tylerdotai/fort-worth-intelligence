#!/usr/bin/env python3
"""
Fort Worth 3D Enrichment Pipeline
1. Fetch Mapbox zoom-15 tiles for Fort Worth bbox, extract building heights
2. Join heights to Microsoft footprints, output fw-buildings-3d.geojson

Usage:
  python3 scripts/fetch_mapbox_heights.py

Environment:
  MAPBOX_TOKEN — Mapbox secret token (required)
  DATA_DIR     — data directory (default: data)
"""
import gzip, io, json, math, os, time, urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

# Token from environment — never hardcode
TOKEN  = os.environ.get("MAPBOX_TOKEN", "")
CACHE  = Path(os.environ.get("DATA_DIR", "data"), "3d", "mapbox_heights.json")
OUT_3D = Path(os.environ.get("DATA_DIR", "data"), "3d", "fw-buildings-3d.geojson")

# Fort Worth bbox (EPSG:4326)
FW_BBOX = {"minLat": 32.55, "maxLat": 33.02, "minLon": -97.55, "maxLon": -97.05}
ZOOM = 15

TILES_URL = "https://api.mapbox.com/v4/mapbox.mapbox-streets-v8/{z}/{x}/{y}.mvt"
HEIGHT_URL = "https://api.mapbox.com/geocoding/v5/mapbox.places/{query}.json?proximity={lon},{lat}"

if not TOKEN:
    raise RuntimeError("MAPBOX_TOKEN environment variable not set")


def tile_bbox(z, x, y):
    n = 2 ** z
    lon_min = x / n * 360 - 180
    lon_max = (x + 1) / n * 360 - 180
    lat_min = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * (y + 1) / n))))
    lat_max = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * y / n))))
    return lon_min, lat_min, lon_max, lat_max


def tiles_in_bbox(bbox, zoom):
    tiles = []
    n = 2 ** zoom
    for x in range(n):
        for y in range(n):
            lon_min, lat_min, lon_max, lat_max = tile_bbox(zoom, x, y)
            if (bbox["minLon"] <= lon_max and bbox["maxLon"] >= lon_min and
                    bbox["minLat"] <= lat_max and bbox["maxLat"] >= lat_min):
                tiles.append((zoom, x, y))
    return tiles


def fetch_tile(z, x, y):
    url = f"https://api.mapbox.com/v4/mapbox.mapbox-streets-v8/{z}/{x}/{y}.mvt?access_token={TOKEN}"
    req = urllib.request.Request(url, headers={"User-Agent": "FortWorthIntelligence/1.0"})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=15) as r:
                if r.status == 204:
                    return None
                return r.read()
        except Exception as e:
            if attempt < 2:
                time.sleep(0.5)
            else:
                return None


def extract_heights_from_mvt(tile_bytes):
    heights = []
    if not tile_bytes:
        return heights
    try:
        import mapbox_vector_tile
        data = mapbox_vector_tile.decode(tile_bytes)
        for layer_name, layer in data.items():
            if layer_name != "building":
                continue
            for feature in layer.get("features", []):
                geom = feature.get("geometry", [])
                props = feature.get("properties", {})
                height = props.get("height") or props.get("building_height", 3)
                if geom and isinstance(geom, list):
                    coords = geom[0] if geom[0] else geom
                    if isinstance(coords, list) and len(coords) > 0:
                        lon = coords[0][0]
                        lat = coords[0][1]
                        heights.append({"lon": lon, "lat": lat, "height": float(height)})
    except Exception:
        pass
    return heights


def fetch_tiles_parallel(tiles, max_workers=16):
    all_heights = []
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futures = {ex.submit(fetch_tile, z, x, y): (z, x, y) for z, x, y in tiles}
        done = 0
        for future in as_completed(futures):
            tile_bytes = future.result()
            heights = extract_heights_from_mvt(tile_bytes)
            all_heights.extend(heights)
            done += 1
            if done % 200 == 0:
                print(f"  [{done}/{len(tiles)}] {len(all_heights)} heights so far")
    return all_heights


def build_height_index(heights):
    index = {}
    for h in heights:
        key = f"{round(h['lon'],5)},{round(h['lat'],5)}"
        if key not in index or h['height'] > index[key]:
            index[key] = h['height']
    return index


if __name__ == "__main__":
    print(f"Fort Worth 3D Enrichment — zoom {ZOOM}")
    tiles = tiles_in_bbox(FW_BBOX, ZOOM)
    print(f"  Tiles to fetch: {len(tiles)}")
    print(f"  Output: {OUT_3D}")

    if CACHE.exists():
        print(f"  Loading cache: {CACHE}")
        with open(CACHE) as f:
            heights = json.load(f)
    else:
        print("  Fetching tiles (this takes ~10-20 min)...")
        t0 = time.time()
        heights = fetch_tiles_parallel(tiles)
        elapsed = time.time() - t0
        print(f"  Done in {elapsed:.0f}s — {len(heights)} heights")
        CACHE.parent.mkdir(parents=True, exist_ok=True)
        with open(CACHE, "w") as f:
            json.dump(heights, f)
        print(f"  Cache saved: {CACHE}")

    height_index = build_height_index(heights)
    print(f"  Unique locations: {len(height_index)}")
