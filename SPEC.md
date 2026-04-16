# Fort Worth Intelligence — Completion Roadmap

**Status as of: 2026-04-16**
**Branch: `feat/completion-roadmap`**

---

## What This Document Is

A candid audit of the Fort Worth Intelligence project — what's working, what's broken, and what it takes to ship it as a production civic data platform. Organized by priority.

---

## Current Architecture

```
Fort Worth Intelligence
├── API (FastAPI) — http://192.168.0.59:8000
│   ├── /resolve          — address → full civic context
│   ├── /resolve/batch    — batch resolve
│   ├── /graph/{id}       — entity graph traversal
│   ├── /query/entities   — filtered entity search
│   ├── /query/aggregate  — group-by metrics
│   ├── /legistar/{district}
│   ├── /legistar/meeting/{id}
│   ├── /geocode          — Census proxy (CORS fix)
│   └── /citygml/{id}     — CityGML 3.0 XML
├── 2D Viewer (/viewer/)  — Leaflet + CARTO dark matter tiles
├── 3D Viewer (/viewer3d/) — CesiumJS (BROKEN — needs fix)
├── Data Pipeline
│   ├── TAD parcels: 283,808 Fort Worth properties ✅
│   ├── MS Building Footprints: 593,668 buildings ✅
│   ├── Mapbox heights: 141k matched, rest estimated ✅
│   └── Legistar: 429 council agenda items ✅
└── Scripts (18 extraction/ingestion scripts)
```

---

## Audit: What's Working vs. Broken

### ✅ Working

| Component | Status | Notes |
|-----------|--------|-------|
| `/resolve` endpoint | Working | Returns parcel, land use, utilities, council agenda |
| `/resolve/batch` | Presumed working | Not tested |
| `/legistar/{district}` | Working | Returns 3/31/2026 council meetings |
| `/geocode` | Working | Census proxy — fixes CORS |
| 2D Viewer | Working | Leaflet + CARTO tiles, address search, API live indicator |
| TAD Parcel data | Loaded | 283,808 parcels, owner + value + GIS link |
| MS Building footprints | 593,668 extracted | fw-buildings.ndjson (160MB) |
| Mapbox height enrichment | Done | 141k matched, avg ~8m, 173m max |
| CI/CD (harness) | 8/8 gates passing | But no automated gate enforcement on push |
| Redis cache | Wired | But not verified as live in current container |

### ❌ Broken

| Component | Severity | Root Cause |
|-----------|----------|------------|
| **3D Viewer** | High | `imageryProvider: false` killed base map — Cesium shows black screen |
| **Council district field** | High | TCGIS MapServer CORS blocked or unreachable from clawbox |
| **State rep field** | High | TCGIS StateRep layer — same CORS issue |
| **Graph edges** | Medium | `/graph/{id}` returns `kind: unknown` and 0 edges — index not built |
| **`/query/entities` count** | Low | Missing `count` field in response JSON |

---

## Priority 1: Fix the 3D Viewer

**Problem:** `imageryProvider: false` was set to stop Cesium from calling home, but it also removed all map imagery. The viewer shows a dark blue screen with no buildings or terrain.

**Fix:**
1. Add a free tile layer (OpenStreetMap via `UrlTemplateImageryProvider`) as the base map
2. Re-enable terrain with Cesium World Terrain (needs Cesium ion token — free at cesium.com/ion)
3. Verify 30k building polygons render and extrude correctly

**Files:** `viewer3d/index.html`, `api_server.py`

---

## Priority 2: Fix Council District + State Rep in `/resolve`

**Problem:** Both fields return `MISSING` when calling `/resolve`. Likely cause: TCGIS MapServer (`maps.fortworthtexas.gov`) is either blocking CORS or unreachable from clawbox's network.

**Diagnosis steps:**
1. Test TCGIS endpoint directly from clawbox: `curl -v "https://maps.fortworthtexas.gov/arcgis/rest/services/Additional_Info/MapServer/2/query?..."`
2. If blocked: implement server-side fetch in the API (already done for Census geocoding) instead of client-side
3. If unreachable: fallback to Turf.js polygon-in-polygon using Fort Worth council district GeoJSON (download once, store locally)

**Files:** `scripts/resolve_address_full.py`, `api_server.py`

---

## Priority 3: Fix Graph Entity Indexing

**Problem:** `/graph/parcel:026-241421-001` returns `kind: unknown` and 0 edges. The graph traversal layer is structurally sound but has no indexed entities.

**Fix:** Build the entity index at startup:
1. Load TAD parcels → index by `gis_link` + `owner_name`
2. Load council districts → index by district number
3. Load school districts → index by district code
4. Wire edges: parcel → council district (via spatial join), parcel → school district (via `school_district` field), parcel → owner (via `owner_name` lookup)
5. Add entity kinds to graph response: `parcel`, `council_district`, `school_district`, `person`, `business`

**Files:** `api_server.py`, `scripts/build_council_index.py`

---

## Priority 4: Add `count` Field to `/query/entities`

**Problem:** Response returns `results[]` but no `count` field for pagination.

**Fix:** Add `count` field to the response that equals `len(results)` for now (total count is expensive to compute on 283k records).

**Files:** `api_server.py`

---

## Priority 5: Wire Redis for API Rate Limit Protection

**Problem:** Census and TCGIS APIs have rate limits. Without Redis caching, repeated `/resolve` calls hit those limits directly.

**Current state:** Redis is configured in the Docker container but not confirmed live. Redis commands in `resolve_address_full.py` may be failing silently.

**Fix:**
1. Add Redis health check at startup: `redis-cli ping` → should return `PONG`
2. Verify `/resolve` is writing to and reading from Redis cache
3. Add cache TTL: 24h for resolved addresses, 7d for graph traversals
4. Add cache hit/miss header to API responses: `X-Cache: HIT/MISS`

---

## Priority 6: Production Deploy (Fly.io)

**What's needed:**
1. `flyctl apps create fort-worth-intelligence`
2. Set secrets: `REDIS_URL`, `SENTRY_DSN`
3. Create persistent volume for TAD data
4. `fly deploy`

**Note:** TAD data (~280MB) needs to either fit in the persistent volume or be fetched at startup from the host bind mount.

---

## Priority 7: CI/CD Gate Enforcement

**Current state:** `scripts/run_release_gates.js` exists with 8 gates and 84% coverage. But it's not enforced on `git push`.

**Fix options:**
- GitHub Actions workflow: run gates on every PR, block merge if gates fail
- Pre-push hook: run gates before allowing `git push`
- Minimum: add `npm test` / `pytest` to GitHub Actions with coverage threshold

---

## Priority 8: Analytics / Observability

**Missing:**
- Request volume per endpoint
- Error rates
- P95/P99 latency
- Most-queried addresses

**Quick wins:**
- Add `prometheus-client` metrics to FastAPI
- Expose `/metrics` endpoint
- Scrape with Grafana or push to a free CloudWatch tier

---

## What's NOT in Scope

- User authentication (this is a public civic data tool)
- Mapbox token upgrade beyond free tier
- Mobile responsive design
- Data update pipeline (TAD releases new certified rolls ~February each year)
- TCGIS restricted layers (building footprints with BLDGHEIGHT — access locked by Tarrant County)

---

## Friday Todoist Tasks

1. **Fix 3D Viewer** — Add OSM tile layer, re-enable terrain, verify buildings render
2. **Diagnose TCGIS CORS** — Test from clawbox, implement server-side fallback
3. **Build graph entity index** — Wire parcel→council→school edges at startup
4. **Add `count` field** to `/query/entities` response
5. **Verify Redis caching** — Confirm cache hits/misses working end-to-end
6. **Write GitHub Actions CI** — Gates enforced on every PR
7. **Fly.io deploy checklist** — Create app, set secrets, persistent volume

---

## Coverage + Test Status

| File | Coverage |
|------|----------|
| `scripts/resolve_address_full.py` | 85% |
| `scripts/snapshot_diff.py` | 100% |
| `api_server.py` | 61% |
| **Overall** | **84%** |

Tests: 119 passed, 14 skipped

**Note:** Coverage was measured on the last pushed commit. Current container state may differ.
