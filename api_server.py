#!/usr/bin/env python3
"""
FastAPI server for Fort Worth Address Resolution API.

Run:
  python3 -m uvicorn api_server:app --host 0.0.0.0 --port 8000 --workers 2

Endpoints:
  GET /resolve?address=...              — full address resolution
  GET /resolve/batch                   — batch resolve (POST with JSON body)
  GET /graph/{id}                      — civic entity graph by stable ID
  GET /query/entities                  — filter + search across all entities
  GET /query/aggregate                 — group-by metrics across entities
  GET /meta/schema                     — active ontology schema version
  GET /citygml?address=...        — CityGML 3.0 XML encoding of resolved address
  GET /legistar/{district}             — council agenda items by district (1-11, or "all")
  GET /legistar/meeting/{id}           — all agenda items for a specific meeting
  GET /health                          — health check
"""
import json, time, sys
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Query, HTTPException, Path as PathParam, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import hashlib
import os
import json

# ── Sentry error tracking ─────────────────────────────────────────────────────
# Set SENTRY_DSN env var to enable. Without it, Sentry is disabled silently.
_sentry_initialized = False
if os.environ.get("SENTRY_DSN"):
    try:
        import sentry_sdk
        from sentry_sdk.integrations.fastapi import FastApiIntegration
        sentry_sdk.init(
            dsn=os.environ["SENTRY_DSN"],
            integrations=[FastApiIntegration()],
            environment=os.environ.get("ENVIRONMENT", "development"),
            release=os.environ.get("VERSION", "dev"),
            traces_sample_rate=0.1,
        )
        _sentry_initialized = True
        print("[INFO] Sentry initialized", file=sys.stderr)
    except Exception as e:
        print(f"[WARN] Sentry init failed: {e}", file=sys.stderr)

# Redis caching — connect if REDIS_URL is set
_redis = None
def get_redis():
    global _redis
    if _redis is None:
        redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
        try:
            import redis
            _redis = redis.from_url(redis_url, decode_responses=True)
            _redis.ping()
        except Exception as e:
            print(f"[WARN] Redis unavailable: {e}", file=sys.stderr)
            _redis = None
    return _redis

FWI_CACHE_TTL = 60 * 60 * 24  # 24 hours

def _cache_key(address: str) -> str:
    """Address hash as Redis key."""
    h = hashlib.sha256(address.lower().encode()).hexdigest()[:24]
    return f"fwi:resolve:{h}"

def _cache_get(address: str):
    r = get_redis()
    if r is None:
        return None
    try:
        raw = r.get(_cache_key(address))
        if raw:
            return json.loads(raw)
    except Exception:
        pass
    return None

def _cache_set(address: str, data: dict):
    r = get_redis()
    if r is None:
        return
    try:
        r.setex(_cache_key(address), FWI_CACHE_TTL, json.dumps(data))
    except Exception:
        pass

# Import the orchestrator
SCRIPTS_DIR = Path(__file__).parent / "scripts"
import sys
sys.path.insert(0, str(SCRIPTS_DIR))

# Import after path setup
from scripts.resolve_address_full import resolve_full
from scripts.citygml_encoder import citygml_document
from scripts.citygml_encoder import citygml_document

# ─── Legistar data loader ───────────────────────────────────────────────────

LEGISTAR_MEETINGS_FILE = Path(__file__).parent / "data" / "legistar-meetings.json"
LEGISTAR_AGENDA_FILE   = Path(__file__).parent / "data" / "legistar-agenda-items.json"

_legistar_cache = {}

def load_legistar():
    global _legistar_cache
    if _legistar_cache:
        return _legistar_cache
    if not LEGISTAR_AGENDA_FILE.exists():
        return {"error": "legistar agenda data not found"}
    with open(LEGISTAR_AGENDA_FILE) as f:
        agenda_data = json.load(f)
    if not LEGISTAR_MEETINGS_FILE.exists():
        meetings_data = {"meetings": []}
    else:
        with open(LEGISTAR_MEETINGS_FILE) as f:
            meetings_data = json.load(f)
    # Build meeting lookup
    meeting_map = {str(m["id"]): m for m in meetings_data.get("meetings", [])}
    _legistar_cache = {"agenda": agenda_data, "meeting_map": meeting_map}
    return _legistar_cache

def get_district_items(district: str, max_meetings: int = 5):
    """Return recent agenda items mentioning a council district."""
    data = load_legistar()
    if "error" in data:
        return data
    results = []
    for meeting in data["agenda"]["meetings"]:
        if meeting.get("item_count", 0) == 0:
            continue
        matching = []
        for item in meeting["items"]:
            cd = item.get("council_districts", "") or ""
            if cd == "ALL" or district.upper() == "ALL":
                matching.append(item)
            elif cd == district:
                matching.append(item)
            else:
                # Handle "2 and CD 9" style values
                if district in cd:
                    matching.append(item)
        if matching:
            results.append({
                "id": meeting["id"],
                "meeting_date": meeting.get("meeting_date", ""),
                "meeting_time": meeting.get("meeting_time", ""),
                "meeting_name": meeting.get("meeting_name", ""),
                "meeting_location": meeting.get("meeting_location", ""),
                "agenda_status": meeting.get("agenda_status", ""),
                "video_available": meeting.get("video_available", ""),
                "source_url": meeting.get("source_url", ""),
                "items": matching,
                "item_count": len(matching),
            })
    # Sort by date descending
    results.sort(key=lambda x: x["meeting_date"], reverse=True)
    return results[:max_meetings]

def get_meeting_items(meeting_id: int):
    """Return all agenda items for a specific meeting."""
    data = load_legistar()
    if "error" in data:
        return data
    for meeting in data["agenda"]["meetings"]:
        if str(meeting["id"]) == str(meeting_id):
            return meeting
    return {"error": f"meeting {meeting_id} not found"}


app = FastAPI(
    title="Fort Worth Intelligence API",
    description="Address → full civic context for Fort Worth, TX",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve the Civic Twin Viewer (after REPO is defined below)

# ─── Models ──────────────────────────────────────────────────────────────────

class BatchResolveRequest(BaseModel):
    addresses: list[str]

class BatchResolveResponse(BaseModel):
    results: list[dict]
    meta: dict

# ─── Helpers ─────────────────────────────────────────────────────────────────

REPO = Path(__file__).parent
META_FILE = REPO / "data" / "meta.json"
VIEWER_DIR = REPO / "viewer"
if VIEWER_DIR.exists():
    app.mount("/viewer", StaticFiles(directory=str(VIEWER_DIR), html=True), name="viewer")

def get_meta():
    if META_FILE.exists():
        with open(META_FILE) as f:
            return json.load(f)
    return {"version": "1.0.0", "repo": "fort-worth-intelligence"}

# ─── Endpoints ───────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok", "service": "fort-worth-intelligence", "version": "1.0.0"}

@app.get("/resolve")
def resolve(address: str = Query(..., description="Street address to resolve")):
    """
    Resolve a Fort Worth address to:
    - Census geocoded lat/lon
    - TAD parcel (owner, value, school district, exemptions)
    - Council district + recent agenda items from Legistar
    - School district
    - Utility districts
    - TX House representative

    Results are cached in Redis for 24 hours to avoid hitting external APIs.
    """
    # Check Redis cache first
    cached = _cache_get(address)
    if cached:
        cached["_meta"]["cache_hit"] = True
        cached["_meta"]["elapsed_ms"] = 0
        return cached

    start = time.time()
    result = resolve_full(address)
    elapsed_ms = int((time.time() - start) * 1000)
    result["_meta"]["elapsed_ms"] = elapsed_ms
    result["_meta"]["resolved_address"] = address
    result["_meta"]["cache_hit"] = False

    # Attach recent Legistar agenda items for the resolved council district
    cd = result.get("council_district") or {}
    district = cd.get("district_number")
    if district:
        try:
            legistar = get_district_items(str(district), max_meetings=3)
            result["council_agenda"] = {
                "district": str(district),
                "meetings": legistar,
                "total_items": sum(m["item_count"] for m in legistar),
            }
        except Exception:
            result["council_agenda"] = {"error": "legistar unavailable"}

    # Cache the result for 24 hours
    _cache_set(address, result)

    return result

@app.post("/resolve/batch", response_model=BatchResolveResponse)
def resolve_batch(body: BatchResolveRequest):
    """
    Resolve multiple addresses in one request.

    Body: {"addresses": ["704 E Weatherford St", "313 N Harding St"]}
    """
    results = []
    for addr in body.addresses:
        try:
            r = resolve_full(addr)
            r["_meta"]["elapsed_ms"] = r["_meta"].get("elapsed_ms", 0)
            results.append({"status": "success", "address": addr, "data": r})
        except Exception as e:
            results.append({"status": "error", "address": addr, "error": str(e)})

    return BatchResolveResponse(
        results=results,
        meta={
            "total": len(body.addresses),
            "successful": sum(1 for r in results if r["status"] == "success"),
            "failed": sum(1 for r in results if r["status"] == "error"),
        },
    )

@app.get("/legistar/{district}")
def legistar_district(
    district: str = PathParam(..., description="Council district number (1-11) or 'all')")
):
    """
    Return recent council agenda items relevant to a district.
    Items are drawn from city-wide meetings and filtered by the
    council_districts field parsed from each item's title.
    """
    valid = ["all"] + [str(i) for i in range(1, 12)]
    if district.lower() not in valid and district not in valid:
        raise HTTPException(status_code=400, detail=f"Invalid district. Use one of: {valid}")
    items = get_district_items(district)
    if "error" in items:
        raise HTTPException(status_code=500, detail=items["error"])
    return {
        "district": district.upper(),
        "meetings": items,
        "total_items": sum(m["item_count"] for m in items),
        "meta": {
            "source": "fortworthgov.legistar.com",
            "scraped_at": load_legistar()["agenda"]["meta"]["scraped_at"],
        },
    }

@app.get("/legistar/meeting/{meeting_id}")
def legistar_meeting(
    meeting_id: int = PathParam(..., description="Legistar meeting ID")
):
    """Return all agenda items for a specific council meeting."""
    result = get_meeting_items(meeting_id)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result

# ─── Graph traversal ─────────────────────────────────────────────────────────

@app.get("/graph/{entity_id}")
def graph_traverse(
    entity_id: str = PathParam(..., description="Stable entity ID (e.g. fw:address:3f4a9c)"),
    depth: int = Query(default=1, ge=0, le=3, description="Traversal depth (0–3)"),
):
    """
    Return the civic entity graph rooted at entity_id.

    Depth 0: root node only
    Depth 1: root + direct neighbours (default)
    Depth 2: + neighbours of neighbours
    Depth 3: full depth limit

    Every response includes provenance and freshness timestamps.
    """
    import hashlib, datetime

    # Load the address index for entity resolution
    ADDRESS_INDEX = REPO / "data" / "resolved" / "address-index.json"
    addr_idx = {}
    if ADDRESS_INDEX.exists():
        with open(ADDRESS_INDEX) as f:
            addr_idx = json.load(f)

    # Parse fw:<type>:<hash> IDs — resolve to a resolved record if available
    root_node = {"id": entity_id, "kind": "unknown", "label": entity_id}
    edges = []

    if entity_id.startswith("fw:address:"):
        # Look up resolved address
        addr_hash = entity_id.split(":")[2]
        for addr_entry in addr_idx.values():
            h = hashlib.md5(addr_entry.get("query_address", "").encode()).hexdigest()[:6]
            if h == addr_hash:
                resolved = resolve_full(addr_entry["query_address"])
                root_node = {
                    "id": entity_id,
                    "kind": "Address",
                    "label": resolved.get("query_address"),
                    "lat": resolved.get("coordinates", {}).get("lat"),
                    "lon": resolved.get("coordinates", {}).get("lon"),
                }
                # Build edges from resolved data
                cd = resolved.get("council_district", {})
                if cd.get("district_number"):
                    edges.append({
                        "source": entity_id,
                        "target": f'fw:council:{cd["district_number"]}',
                        "rel": "IN_COUNCIL_DISTRICT",
                    })
                parcel = resolved.get("parcel")
                if parcel:
                    edges.append({
                        "source": entity_id,
                        "target": f'fw:parcel:{parcel.get("pidn", "?")}',
                        "rel": "LOCATED_ON_PARCEL",
                    })
                school = resolved.get("school_district", {})
                if school.get("name"):
                    edges.append({
                        "source": entity_id,
                        "target": f'fw:school:{school["name"].replace(" ", "-")}',
                        "rel": "IN_SCHOOL_DISTRICT",
                    })
                break

    elif entity_id.startswith("fw:parcel:"):
        pidn = entity_id.split(":")[2]
        root_node = {"id": entity_id, "kind": "Parcel", "label": f"Parcel {pidn}"}
        # Parcel → address (reverse of above)
        edges.append({
            "source": entity_id,
            "target": f"fw:address:{hashlib.md5(root_node.get('label','').encode()).hexdigest()[:6]}",
            "rel": "HAS_ADDRESS",
        })

    elif entity_id.startswith("fw:council:"):
        district = entity_id.split(":")[2]
        root_node = {"id": entity_id, "kind": "CouncilDistrict", "label": f"District {district}"}
        # District → addresses in district (would need spatial join in production)
        # Placeholder edge for schema completeness
        edges.append({
            "source": entity_id,
            "target": f"fw:school:fort-worth-{district}",
            "rel": "SHARES_AREA_WITH",
        })

    elif entity_id.startswith("fw:school:"):
        school_name = entity_id.split(":", 2)[2].replace("-", " ")
        root_node = {"id": entity_id, "kind": "SchoolDistrict", "label": school_name}

    # Provenance: always attach source info
    freshness = datetime.datetime.now(datetime.timezone.utc).isoformat()
    provenance = {
        "source": "fort-worth-intelligence",
        "ontology_version": "1.0",
        "schema_version": "1.0",
    }

    return {
        "root": root_node,
        "nodes": [root_node],  # TODO: expand with neighbour nodes at depth > 0
        "edges": edges,
        "depth": depth,
        "provenance": provenance,
        "freshness": freshness,
    }

# ─── Entity query ─────────────────────────────────────────────────────────────

@app.get("/query/entities")
def query_entities(
    kind: str = Query(default=None, description="Filter by entity kind (Address, Parcel, etc.)"),
    district: str = Query(default=None, description="Council district number"),
    search: str = Query(default=None, description="Full-text search on labels"),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    """
    Filter and search across all indexed entities.
    Returns paginated items with total count.
    """
    ADDRESS_INDEX = REPO / "data" / "resolved" / "address-index.json"
    items = []
    if ADDRESS_INDEX.exists():
        with open(ADDRESS_INDEX) as f:
            addr_idx = json.load(f)
        for addr_key, rec in addr_idx.items():
            if kind and rec.get("kind") != kind:
                continue
            if district:
                cd = rec.get("council_district", {})
                if str(cd.get("district_number")) != str(district):
                    continue
            if search:
                label = rec.get("query_address", "").lower()
                if search.lower() not in label:
                    continue
            items.append(rec)

    total = len(items)
    items = sorted(items, key=lambda x: x.get("query_address", ""))[offset:offset + limit]
    return {
        "filters": {"kind": kind, "district": district, "search": search},
        "items": items,
        "total": total,
        "limit": limit,
        "offset": offset,
    }

# ─── Aggregation query ────────────────────────────────────────────────────────

@app.get("/query/aggregate")
def query_aggregate(
    group_by: str = Query(default="council_district", description="Field to group by"),
    metric: str = Query(default="count", description="Metric: count, avg_value"),
):
    """
    Aggregate statistics across resolved entities grouped by a field.

    group_by options: council_district, school_district, owner_type
    metric options: count, avg_value
    """
    ADDRESS_INDEX = REPO / "data" / "resolved" / "address-index.json"
    if not ADDRESS_INDEX.exists():
        return {"error": "no resolved address index found"}

    with open(ADDRESS_INDEX) as f:
        addr_idx = json.load(f)

    groups: dict = {}
    for rec in addr_idx.values():
        if group_by == "council_district":
            key = str(rec.get("council_district", {}).get("district_number", "unknown"))
        elif group_by == "school_district":
            key = str(rec.get("school_district", {}).get("name", "unknown"))
        elif group_by == "owner_type":
            key = str(rec.get("parcel", {}).get("owner_type", "unknown"))
        else:
            key = "all"

        if key not in groups:
            groups[key] = {"count": 0, "total_value": 0}
        groups[key]["count"] += 1
        val = rec.get("parcel", {}).get("market_value") or 0
        try:
            groups[key]["total_value"] += int(val)
        except (ValueError, TypeError):
            pass

    rows = []
    for k, v in sorted(groups.items()):
        rows.append({
            "group": k,
            "count": v["count"],
            "avg_value": v["total_value"] // v["count"] if v["count"] > 0 else 0,
        })

    return {
        "group_by": group_by,
        "metric": metric,
        "rows": rows,
        "total_entities": sum(r["count"] for r in rows),
    }

# ─── Schema meta ──────────────────────────────────────────────────────────────

@app.get("/meta/schema")
def meta_schema():
    """Return the active ontology schema version and entity types."""
    return {
        "ontology_version": "1.0",
        "schema_version": "1.0",
        "base_standard": "OGC CityGML 3.0 Conceptual Model",
        "namespace": "https://fwintelligence.city/ont/v1",
        "entity_types": [
            {"name": "Address", "id_pattern": "fw:address:<md5>", "description": "Resolved street address"},
            {"name": "Parcel", "id_pattern": "fw:parcel:<pidn>", "description": "TAD certified appraisal parcel"},
            {"name": "CouncilDistrict", "id_pattern": "fw:council:<number>", "description": "FW council district 1–10"},
            {"name": "SchoolDistrict", "id_pattern": "fw:school:<slug>", "description": "Tarrant County school district"},
            {"name": "UtilityProvider", "id_pattern": "fw:utility:<name>", "description": "Municipal utility service provider"},
            {"name": "Permit", "id_pattern": "fw:permit:<number>", "description": "City of Fort Worth issued permit"},
        ],
        "provenance_fields": ["source", "ontology_version", "schema_version", "ingested_at"],
    }

@app.get("/")
def root():
    return {
        "service": "Fort Worth Intelligence API",
        "version": "1.0.0",
        "endpoints": {
            "GET /resolve?address=...": "Resolve a single address",
            "POST /resolve/batch": "Batch resolve multiple addresses",
            "GET /graph/{entity_id}?depth=0-3": "Civic entity graph by stable ID",
            "GET /query/entities": "Filter/search all indexed entities",
            "GET /query/aggregate": "Group-by metrics across entities",
            "GET /meta/schema": "Active ontology schema version",
            "GET /legistar/{district}": "Council agenda items by district",
            "GET /legistar/meeting/{id}": "Agenda items for a specific meeting",
            "GET /citygml/{entity_id}": "CityGML 3.0 XML encoding",
            "GET /health": "Health check",
        },
    }

# ─── CityGML 3.0 export ──────────────────────────────────────────────────────

@app.get("/citygml")
def citygml_export(
    address: str = Query(..., description="Street address to encode as CityGML 3.0 XML"),
):
    """
    Return a resolved address as an OGC CityGML 3.0 XML document.

    Wraps the address in CityModel/Site with:
    - gml:id, validFrom/validTo temporal window
    - fw:parcelRef, fw:councilDistrictRef, fw:schoolDistrictRef
    - Address with EPSG:4326 point location
    - lod0Geometry polygon from council district GeoJSON
    - metaDataMetadata with schema version and snapshot ID
    """
    import hashlib
    from scripts.citygml_encoder import citygml_document

    resolved = resolve_full(address)
    coords = resolved.get("coordinates") or {}
    lat, lon = coords.get("lat"), coords.get("lon")
    addr_hash = hashlib.md5(address.encode()).hexdigest()[:6]
    entity_id = f"fw:address:{addr_hash}"

    xml_body = citygml_document(resolved, entity_id)
    return Response(
        content=xml_body,
        media_type="application/xml",
        headers={"Content-Disposition": f'attachment; filename="{entity_id}.xml"'},
    )