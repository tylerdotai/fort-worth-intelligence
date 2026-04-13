#!/usr/bin/env python3
"""
Fort Worth 3D Twin — Full Enrichment Pipeline
1. Fetch all zoom-15 Mapbox tiles covering Fort Worth (42 tiles)
2. Extract building heights from each tile
3. For each Microsoft building, find height from nearest Mapbox building
4. Output enriched GeoJSON for viewer
"""
import gzip, io, json, math, os, sys, time
import mapbox_vector_tile
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

TOKEN_PATH = Path("/home/tyler/.config/fort-worth-intelligence/.env")
HEIGHTS_CACHE = Path("/home/tyler/fort-worth-intelligence/data/3d/mapbox_heights.json")
ENRICHED_OUT = Path("/home/tyler/fort-worth-intelligence/data/3d/fw-buildings-enriched.geojson")
FW_BLDGS = Path("/home/tyler/fort-worth-intelligence/data/3d/fw-buildings.ndjson")

# ── Tile math ──────────────────────────────────────────────────────────────
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

def all_fw_tiles(zoom=15):
    """All zoom-N tiles covering Fort Worth bbox."""
    tiles = set()
    lat_steps = [32.55, 32.65, 32.75, 32.85, 32.95, 33.02]
    lon_steps = [-97.55, -97.45, -97.35, -97.25, -97.15, -97.05, -96.95]
    for lat in lat_steps:
        for lon in lon_steps:
            tx, ty = lat_lon_to_tile(lat, lon, zoom)
            tiles.add((tx, ty))
    return sorted(tiles)

# ── MVT decode ─────────────────────────────────────────────────────────────
def extract_heights_from_tile(x, y, zoom, token):
    """Return list of (lon, lat, height_m) for all buildings with heights."""
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

    b_lat_min, b_lat_max, b_lon_min, b_lon_max = tile_bounds(x, y, zoom)
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

        outer = coords[0] if isinstance(coords[0][0], list) else coords
        if not outer:
            continue

        cx = sum(c[0] for c in outer) / len(outer)
        cy = sum(c[1] for c in outer) / len(outer)

        lon = lon_min + (cx / 4096) * (lon_max - lon_min)
        lat = lat_max + (cy / 4096) * (lat_min - lat_max)

        results.append((lon, lat, height_m))

    return results

# ── Spatial join ──────────────────────────────────────────────────────────
class SimpleGrid:
    """Grid-based spatial index for lat/lon → nearest point lookup."""
    def __init__(self, points: list[tuple], cell_deg=0.001):
        self.cell_deg = cell_deg
        self.grid: dict[tuple, list] = {}
        for lon, lat, h in points:
            gx = round(lon / cell_deg)
            gy = round(lat / cell_deg)
            self.grid.setdefault((gx, gy), []).append((lon, lat, h))

    def nearest(self, lon, lat, max_dist=0.005) -> float | None:
        gx, gy = round(lon / self.cell_deg), round(lat / self.cell_deg)
        best_d, best_h = 1e9, None
        for dx in range(-3, 4):
            for dy in range(-3, 4):
                cell = self.grid.get((gx + dx, gy + dy))
                if not cell:
                    continue
                for plon, plat, ph in cell:
                    d = math.sqrt((lon - plon)**2 + (lat - plat)**2)
                    if d < best_d:
                        best_d, best_h = d, ph
        return best_h if best_d <= max_dist else None

# ── Height estimation ─────────────────────────────────────────────────────
# Estimate height from footprint area (sqmeters) and building type
# Based on: residential ~3m/floor, commercial ~4m/floor
def estimate_height_m(area_sqm: float, property_class: str = None) -> float:
    # Heuristic: taller per floor for commercial
    m_per_floor = 3.5 if property_class in ("C1", "C2", "B1", "B2", "Commercial") else 3.0
    # Rough floor count from area
    if area_sqm < 100:
        floors = 1
    elif area_sqm < 300:
        floors = 2
    elif area_sqm < 750:
        floors = 3
    elif area_sqm < 1500:
        floors = 5
    elif area_sqm < 3000:
        floors = 8
    else:
        floors = int(math.sqrt(area_sqm) / 10) + 1
    return max(floors * m_per_floor, 3.0)

# ── Main pipeline ──────────────────────────────────────────────────────────
def main():
    t0 = time.time()

    # 1. Load token
    token = os.environ.get("MAPBOX_TOKEN", "")
    if not token and TOKEN_PATH.exists():
        for line in TOKEN_PATH.read_text().splitlines():
            if "MAPBOX_TOKEN" in line:
                token = line.split("=", 1)[1].strip()
    if not token:
        print("[ERROR] MAPBOX_TOKEN not set")
        sys.exit(1)

    # 2. Fetch all zoom-15 tiles
    tiles = all_fw_tiles(15)
    print(f"[1/4] Fetching {len(tiles)} zoom-15 tiles from Mapbox...")

    all_points = []
    done = 0
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = {pool.submit(extract_heights_from_tile, tx, ty, 15, token): (tx, ty) for tx, ty in tiles}
        for future in as_completed(futures):
            done += 1
            if done % 10 == 0:
                print(f"  [{done}/{len(tiles)}] tiles fetched, {len(all_points):,} height points")
            try:
                pts = future.result()
                all_points.extend(pts)
            except Exception:
                pass

    print(f"[2/4] {len(all_points):,} height points collected")

    # Save heights cache
    heights_dict = {f"{lon:.6f},{lat:.6f}": h for lon, lat, h in all_points}
    cache = {"meta": {"tiles": len(tiles), "points": len(heights_dict)}, "heights": heights_dict}
    with open(HEIGHTS_CACHE, "w") as f:
        json.dump(cache, f)
    print(f"[2/4] Heights cached → {HEIGHTS_CACHE}")

    # Build spatial index
    index = SimpleGrid(all_points, cell_deg=0.001)
    print(f"[3/4] Spatial index built, max height={max(h for _,_,h in all_points):.1f}m")

    # 3. Load Microsoft footprints and join heights
    print(f"[3/4] Joining heights to {593668} Microsoft footprints...")

    enriched = []
    matched = 0
    estimated = 0
    batch = []

    with open(FW_BLDGS) as f:
        for i, line in enumerate(f):
            if i % 100_000 == 0:
                elapsed = time.time() - t0
                print(f"  [{i:,}/593668] matched={matched} estimated={estimated} ({elapsed:.0f}s elapsed)")

            feat = json.loads(line)
            geom = feat.get("geometry", {})
            coords = geom.get("coordinates", [])
            if not coords:
                continue

            # Compute centroid from outer ring
            outer = coords[0][0] if isinstance(coords[0][0], list) else coords[0]
            if not outer:
                continue
            lons = [c[0] for c in outer]
            lats = [c[1] for c in outer]
            cx = sum(lons) / len(lons)
            cy = sum(lats) / len(lats)

            # Try to find height from Mapbox
            height_m = index.nearest(cx, cy)

            if height_m is not None:
                matched += 1
            else:
                # Estimate from footprint area
                area_sqm = geom.get("area_sqm")
                if not area_sqm:
                    # Approximate from polygon
                    try:
                        import shapely.geometry
                        poly = shapely.geometry.Polygon(outer)
                        area_sqm = poly.area * 1e10  # rough conversion
                    except Exception:
                        area_sqm = 500  # default
                height_m = estimate_height_m(area_sqm)
                estimated += 1

            # Properties
            props = feat.get("properties", {})
            feat["properties"]["_3d_height_m"] = round(height_m, 2)
            feat["properties"]["_3d_height_source"] = "mapbox" if matched and height_m is not None else "estimated"
            batch.append(feat)

            if len(batch) >= 50_000:
                enriched.extend(batch)
                batch = []

        enriched.extend(batch)

    elapsed = time.time() - t0
    print(f"\n[DONE] {len(enriched):,} enriched buildings in {elapsed:.1f}s")
    print(f"       Mapbox-matched: {matched:,} ({100*matched/len(enriched):.1f}%)")
    print(f"       Estimated:     {estimated:,} ({100*estimated/len(enriched):.1f}%)")

    # 4. Write output
    fc = {"type": "FeatureCollection", "features": enriched}
    with open(ENRICHED_OUT, "w") as f:
        json.dump(fc, f)
    print(f"[4/4] Written → {ENRICHED_OUT} ({len(enriched):,} features)")


if __name__ == "__main__":
    main()
