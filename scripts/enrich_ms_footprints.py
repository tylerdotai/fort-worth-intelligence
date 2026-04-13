#!/usr/bin/env python3
"""
Enrich Microsoft USBuildingFootprints with Mapbox 3D building heights.
Uses Mapbox Tilequery API — returns decoded JSON with building polygons + heights.
Approach:
  1. For each Microsoft building footprint, compute centroid lat/lon
  2. Query Mapbox Tilequery for that point (radius=0 — no buffer)
  3. Point-in-polygon test to find which Mapbox building contains the centroid
  4. Extract height from the matching building

But: 593k API calls is too many. Better approach:
  1. Query Mapbox tile grid at zoom 15 — all tiles covering Fort Worth
  2. Download tiles (MVT), decode with mapbox_vector_tile
  3. Build spatial index (R-tree or simple grid hash)
  4. For each Microsoft building centroid, find nearest Mapbox building
  5. Use height if found, otherwise estimate from footprint area

Mapbox Streets v8 at zoom 15: ~300 buildings/tile, all have heights.
Fort Worth at zoom 15: ~2,000 tiles (subset of full bbox).
Target: fetch top ~200 dense tiles covering downtown/urban FW (~50k height values).
"""
import gzip, io, json, math, os, sys, time, urllib.request
import mapbox_vector_tile
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

TOKEN_PATH = Path("/home/tyler/.config/fort-worth-intelligence/.env")
CACHE_FILE = Path("/home/tyler/fort-worth-intelligence/data/3d/mapbox_heights.json")
NDJSON = Path("/home/tyler/fort-worth-intelligence/data/3d/fw-buildings.ndjson")
MAX_TILES = 300  # Well under 200k/mo free tier

# Tile math
def lat_lon_to_tile(lat, lon, zoom):
    x = int((lon + 180) / 360 * 2**zoom)
    y = int((1 - math.log(math.tan(math.radians(lat)) + 1/math.cos(math.radians(lat))) / math.pi) / 2 * 2**zoom)
    return x, y

def tile_bounds(x, y, zoom):
    n = 2**zoom
    lon_min = x/n*360 - 180
    lon_max = (x+1)/n*360 - 180
    lat_min = math.degrees(math.atan(math.sinh(math.pi*(1-2*(y+1)/n))))
    lat_max = math.degrees(math.atan(math.sinh(math.pi*(1-2*y/n))))
    return lat_min, lat_max, lon_min, lon_max

# Parse MVT geometry — mapbox_vector_tile already decodes delta encoding
# coords are lists of [x, y] in tile-local space (0-4096)
def extract_building_heights(x, y, zoom, token):
    """Download tile, extract building heights. Returns list of (lon, lat, height_m)."""
    url = f"https://api.mapbox.com/v4/mapbox.mapbox-streets-v8/{zoom}/{x}/{y}.mvt?access_token={token}"
    try:
        data = urllib.request.urlopen(url, timeout=20).read()
    except Exception:
        return []
    try:
        with gzip.GzipFile(fileobj=io.BytesIO(data)) as f:
            raw = f.read()
        tile = mapbox_vector_tile.decode(raw)
    except Exception:
        return []

    layer = tile.get("building", {})
    features = layer.get("features", [])
    if not features:
        return []

    bounds = tile_bounds(x, y, zoom)
    b_min_lon, b_max_lon = bounds[2], bounds[3]
    b_max_lat, b_min_lat = bounds[1], bounds[0]

    results = []
    for feat in features:
        props = feat.get("properties", {})
        h = props.get("height")
        if h is None:
            continue
        try:
            height_m = float(h)
        except (ValueError, TypeError):
            continue
        if height_m <= 0:
            continue

        geom = feat.get("geometry", {})
        coords = geom.get("coordinates", [])
        if not coords:
            continue

        # Get outer ring (handles both Polygon and first polygon of MultiPolygon)
        outer = coords[0] if isinstance(coords[0][0], list) else coords
        if not outer:
            continue

        cx = sum(c[0] for c in outer) / len(outer)
        cy = sum(c[1] for c in outer) / len(outer)

        # Map tile coords (0-4096) → WGS84
        lon = b_min_lon + (cx / 4096) * (b_max_lon - b_min_lon)
        lat = b_max_lat + (cy / 4096) * (b_min_lat - b_max_lat)

        results.append((lon, lat, height_m))

    return results


def get_fw_tiles(zoom=15):
    """All zoom-N tiles covering Fort Worth bbox."""
    tiles = set()
    for lat in [32.55, 32.75, 32.90, 33.02]:
        for lon in [-97.55, -97.35, -97.15, -97.05]:
            tx, ty = lat_lon_to_tile(lat, lon, zoom)
            tiles.add((tx, ty))
    # Fill in gaps
    lat_steps = [32.55, 32.65, 32.75, 32.85, 32.95, 33.02]
    lon_steps = [-97.55, -97.45, -97.35, -97.25, -97.15, -97.05]
    for lat in lat_steps:
        for lon in lon_steps:
            tx, ty = lat_lon_to_tile(lat, lon, zoom)
            tiles.add((tx, ty))
    return sorted(tiles)


def main():
    t0 = time.time()

    # Load token
    token = os.environ.get("MAPBOX_TOKEN", "")
    if not token and TOKEN_PATH.exists():
        for line in TOKEN_PATH.read_text().splitlines():
            if "MAPBOX_TOKEN" in line:
                token = line.split("=", 1)[1].strip()
    if not token:
        print("[ERROR] MAPBOX_TOKEN not set")
        sys.exit(1)

    tiles = get_fw_tiles(15)
    tiles = tiles[:MAX_TILES]
    print(f"[enrich] {len(tiles)} tiles at zoom 15 (downtown FW focus)")
    print(f"[enrich] ~200k free tiles/mo — using {len(tiles)} this run")

    all_heights = {}  # key: "lon,lat" → height_m

    def fetch(xy):
        x, y = xy
        return extract_building_heights(x, y, 15, token)

    done = 0
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = {pool.submit(fetch, xy): xy for xy in tiles}
        for future in as_completed(futures):
            done += 1
            if done % 20 == 0 or done == len(tiles):
                print(f"[{done}/{len(tiles)}] tiles, {len(all_heights):,} heights collected")
            try:
                results = future.result()
                for lon, lat, h in results:
                    key = f"{lon:.6f},{lat:.6f}"
                    all_heights[key] = h
            except Exception as e:
                pass

    elapsed = time.time() - t0
    print(f"\n[enrich] Done: {len(all_heights):,} height values in {elapsed:.1f}s")

    with open(CACHE_FILE, "w") as f:
        json.dump({"meta": {"tiles": len(tiles), "count": len(all_heights), "seconds": round(elapsed,1)}, "heights": all_heights}, f)
    print(f"[enrich] Cached → {CACHE_FILE}")

    # Preview
    tall = sorted(all_heights.values(), reverse=True)[:10]
    print(f"[enrich] Tallest buildings: {[f'{h:.1f}m' for h in tall]}")


if __name__ == "__main__":
    main()
