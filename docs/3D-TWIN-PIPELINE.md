# Fort Worth Intelligence — 3D Digital Twin Pipeline

**Status:** Design spec — not yet built
**Last updated:** 2026-04-13

---

## 1. What We're Building

A real 3D digital twin of Fort Worth at LOD1 (extruded footprints):
- Building polygons extruded to actual or estimated height
- Terrain elevation for ground truth
- Layered Fort Worth civic data (parcels, permits, crime, zoning)
- Interactive CesiumJS viewer — explorable by address, district, or parcel

---

## 2. Data Sources

### 2.1 Building Footprints — Microsoft USBuildingFootprints (PRIMARY)
**License:** Open Database License (ODbL) — free, no API key
**Coverage:** 129,591,852 buildings across the US
**Format:** GeoJSON, EPSG:4326 (WGS84)
**Source:** https://github.com/microsoft/USBuildingFootprints

**State files:** https://minedbuildings.z5.web.core.windows.net/legacy/usbuildings-v2/{State}.geojson.zip

**Texas file:** ~394MB zip, ~2.5GB unzipped
**Fort Worth filter bbox:** lat 32.55–33.02, lon -97.55–-97.05
**Estimated FW buildings:** ~200,000–300,000

**Limitation:** Polygon footprints only — NO height attribute

### 2.2 Building Heights — Multiple Enrichment Sources

#### Option A: Mapbox Buildings Layer (RECOMMENDED — requires free token)
**What:** Real 3D building height data in Mapbox Streets vector tiles
**Coverage:** Major metro areas (Fort Worth is covered)
**Access:** Mapbox free tier — 50,000 map loads/month, free token from mapbox.com
**Data:** `building_height` attribute in Mapbox Streets v8
**Pros:** Actual building heights, no estimation needed
**Cons:** Requires free Mapbox account (Tyler signs up, 30 seconds)
**API call example:**
```
https://api.mapbox.com/v4/mapbox.mapbox-streets-v8/{z}/{x}/{y}.mvt
```
But easier: use the **Mapbox GL JS `setFillExtrudeHeight`** approach with address lookup via geocoding.

#### Option B: OSM building:levels (FALLBACK)
**What:** `building:levels` tag on OSM ways/nodes
**Coverage:** Incomplete — downtown/landmark buildings tagged, most residential not
**Access:** Overpass API (currently slow — need to retry)
**Height formula:** `height_m = levels × 3.5m` (average floor height)
**Pros:** Free, no account
**Cons:** Incomplete coverage for residential neighborhoods

#### Option C: USGS 3DEP Elevation (GROUND TRUTH)
**What:** 1/3 arc-second (≈10m) digital elevation model
**Access:** Free, works from clawbox via USGS TNM Elevation API
**Endpoint:** `https://epqs.nationalmap.gov/v1/json`
**Use:** Ground elevation at any lat/lon — used for terrain surface + shadow analysis
**Example:** `704 E Weatherford St` → ground elevation 184.5m

#### Option D: TCGIS SceneServer (VERIFY ACCESS)
**What:** Fort Worth's own ArcGIS SceneServer with `BLDGHEIGHT`, `EAVEHEIGHT`, `BASEELEV`
**Coverage:** Likely Fort Worth corporate limits
**Access:** `https://services5.arcgis.com/3ddLCBXe1bRt7mzj/ArcGIS/rest/services/Buildings/SceneServer`
**Issue:** Currently returns 0 features — may need ArcGIS authentication or limited availability
**Status:** Needs verification — if it works, this is the best data

### 2.3 Civic Data Layers (Already Built)
- TAD parcels: 283,808 Fort Worth parcels (owner, value, school)
- Council district polygons with geometry
- Zoning / future land use
- Building permits (via TCGIS)
- Crime incidents
- Legistar council meetings

---

## 3. Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  CesiumJS Viewer (self-hosted, no Cesium ion)               │
│  - MapLibre GL JS base map (dark style)                     │
│  - Microsoft footprint polygons (3D extruded)               │
│  - Mapbox height enrichment (where available)               │
│  - Layer panel: parcels, zoning, permits, crime heatmap     │
│  - Address search → fly-to + info panel                    │
└─────────────────────────────────────────────────────────────┘
                            ↑
                    3D Tileset / GeoJSON
                            ↑
┌─────────────────────────────────────────────────────────────┐
│  3D Pipeline (Python / scripts/)                            │
│  1. Download/filter Microsoft footprints for FW bbox        │
│  2. Query Mapbox for building heights (or estimate)         │
│  3. Enrich with USGS ground elevation                      │
│  4. Merge with Fort Worth civic data (gis_link join)        │
│  5. Output: GeoJSON + 3D tileset + tilesdb                 │
└─────────────────────────────────────────────────────────────┘
```

---

## 4. 3D Tile Pipeline — Step by Step

### Step 1: Get Mapbox Token (Tyler — 30 seconds)
1. Go to https://account.mapbox.com/access-tokens/
2. Create free account (GitHub or email)
3. Copy default public token
4. Give token to Dexter (set in `MAPBOX_TOKEN` env var or `.env`)
5. Free tier: 50,000 map loads/month — enough for heavy prototype use

### Step 2: Download Microsoft Footprints for Fort Worth
```python
# Filter Texas.geojson.zip → Fort Worth bounding box only
# Bbox: lat [32.55, 33.02], lon [-97.55, -97.05]

# Option A: Stream filter (don't need to download full Texas file)
# Use curl + python streaming ndjson approach
# Download size: ~50-100MB for Fort Worth bbox (vs 394MB full Texas)

# Option B: Pre-filtered regional extract
# Check if Microsoft has DFW/North Texas extract
```

### Step 3: Enrich with Building Heights
```python
# For each building footprint:
# 1. Try Mapbox Streets vector tile at centroid → get building_height
# 2. If no Mapbox data: estimate from footprint area by building type
#    - Residential: height = sqrt(area) × 1.2 (roughly 1-2 stories)
#    - Commercial: height = sqrt(area) × 2.5 (taller per floor)
#    - Use property_class from TAD to refine (A1=residential, etc.)
```

### Step 4: Merge with Civic Data
```python
# Join on spatial intersection:
# Microsoft footprint centroid → lat/lon → Census geocode →
# → TAD parcel by address → Fort Worth GIS by gis_link
# Enriches building with: owner, value, school district, zoning
```

### Step 5: Output Formats
```python
# Format A: GeoJSON (for MapLibre GL JS)
#   - Simple, works in browser
#   - Good for <100k features

# Format B: 3D Tiles (for CesiumJS)
#   - Tile-based, handles millions of features
#   - Use py3dtilers or custom tiling script
#   - Serve from: /3d/ directory on API server

# Format C: MBTiles (for MapLibre offline)
#   - Single file, easy to host
```

---

## 5. Viewer Architecture

### CesiumJS (Primary — real 3D)
```javascript
// CesiumJS without ion (self-hosted terrain + imagery)
const viewer = new Cesium.Viewer('cesiumContainer', {
  imageryProvider: new Cesium.MapboxImageryProvider({
    mapboxId: 'mapbox/dark-v11',
    accessToken: MAPBOX_TOKEN  // from env
  }),
  terrainProvider: Cesium.createWorldTerrain(), // USGS 3DEP terrain
  baseLayerPicker: false,
  geocoder: false
});

// Add building layer from GeoJSON/3D Tiles
const buildings = viewer.dataSources.add(
  Cesium.GeoJsonDataSource.load('buildings-fw.geojson', {
    fill: new Cesium.ColorMaterialProperty(Color.WHITE.withAlpha(0.8)),
    extrudedHeight: 'height_field',  // from enrichment
    height: 'ground_elevation'
  })
);
```

### MapLibre GL JS (Fallback — 2D with extrusion)
```javascript
// MapLibre GL JS with fill-extrusion for 3D
const map = new maplibregl.Map({
  style: 'mapbox://styles/mapbox/dark-v11', // requires token
  center: [-97.328, 32.759],
  zoom: 15
});

map.addLayer({
  'id': 'buildings-extruded',
  'type': 'fill-extrusion',
  'source': 'fw-buildings',
  'layout': {},
  'paint': {
    'fill-extrusion-height': ['get', 'height'],
    'fill-extrusion-base': ['get', 'elevation'],
    'fill-extrusion-opacity': 0.8
  }
});
```

---

## 6. Layer Specifications

### Layer 1: Buildings 3D (primary)
- Source: Microsoft footprints enriched with Mapbox heights
- Extrusion: height in meters above ground
- Color: white/gray with transparency
- Opacity: 0.7–0.9 depending on zoom level

### Layer 2: Terrain
- Source: Cesium World Terrain (USGS 3DEP SRTM)
- Self-hosted fallback: download USGS 3DEP tiles for Fort Worth bbox

### Layer 3: Parcel Polygons (TAD)
- Source: Fort Worth GIS parcel boundaries
- Join key: gis_link (section-township-range-lot)
- Display: outline only, color-coded by value or zoning

### Layer 4: Zoning / Future Land Use
- Source: CFW_FutureLandUse (ArcGIS FeatureServer)
- Display: semi-transparent fill, category-colored

### Layer 5: Crime Heatmap
- Source: FWPD crime stats (already in pipeline)
- Display: heatmap layer, recent 90 days

### Layer 6: Council Districts
- Source: TCGIS MapServer (already working)
- Display: outline with district number labels

---

## 7. Implementation Phases

### Phase 1: Baseline 3D (No new data sources needed)
**Goal:** Show extruded building footprints using Microsoft data + height estimation
1. Download Microsoft Texas footprints (filtered to FW bbox)
2. Estimate building heights from footprint area + building type heuristic
3. Serve via FastAPI + GeoJSON endpoint
4. Display in MapLibre GL JS with fill-extrusion
**Effort:** 2–3 hours
**Result:** Buildings visible as 3D blocks (not perfectly accurate heights, but works)

### Phase 2: Real Heights via Mapbox (Tyler signs up for free token)
**Goal:** Accurate building heights for Fort Worth
1. Tyler gets Mapbox free token (5 minutes)
2. Query Mapbox Streets vector tiles for building centroids in FW bbox
3. Download tile data, extract `building:height` values
4. Merge heights onto Microsoft footprints
5. Re-render with accurate extrusion heights
**Effort:** 2–4 hours
**Result:** Real 3D buildings — downtown FW skyline is accurate

### Phase 3: Full CesiumJS Viewer
**Goal:** Professional 3D twin viewer
1. Wire CesiumJS with MapLibre base map + Cesium terrain
2. 3D Tileset pipeline (py3dtilers or custom)
3. Layer toggles panel (parcels, zoning, permits, crime)
4. Address search → fly-to + info card
**Effort:** 4–6 hours
**Result:** Full civic twin experience

### Phase 4: TCGIS Height Verification
**Goal:** Check if FW ArcGIS SceneServer has real heights
1. Try authenticated ArcGIS request to SceneServer
2. If accessible: use as primary height source, supplement with Mapbox
3. If not accessible: document as blocked, use Mapbox
**Effort:** 1 hour
**Result:** Best available height data confirmed

---

## 8. Immediate Next Steps

1. **Tyler:** Sign up for Mapbox free account → give Dexter the token
2. **Dexter:** Write `scripts/download_ms_footprints.py` — stream-filter Texas GeoJSON to Fort Worth bbox
3. **Dexter:** Write `scripts/enrich_3d.py` — query Mapbox for heights, merge onto footprints
4. **Dexter:** Write `scripts/build_3d_tileset.py` — convert GeoJSON to 3D Tiles
5. **Dexter:** Build `viewer3d/` — CesiumJS viewer with all layers

---

## 9. Cost Summary

| Component | Cost |
|-----------|------|
| Microsoft USBuildingFootprints | Free (ODbL) |
| USGS Elevation API | Free |
| Mapbox free tier | Free (50k loads/mo) |
| CesiumJS | Free (self-hosted) |
| MapLibre GL JS | Free (BSD) |
| Hosting (Fly.io) | $0–5/mo (already deploying) |
| **Total** | **$0** |

No paid services required. Tyler signs up for Mapbox free token — that's the only account needed.
