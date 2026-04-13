#!/usr/bin/env python3
"""
FastAPI server for Fort Worth Address Resolution API.

Run:
  python3 -m uvicorn api_server:app --host 0.0.0.0 --port 8000 --workers 2

Endpoints:
  GET /resolve?address=...              — full address resolution
  GET /resolve/batch                    — batch resolve (POST with JSON body)
  GET /legistar/{district}             — council agenda items by district (1-11, or "all")
  GET /legistar/meeting/{id}           — all agenda items for a specific meeting
  GET /health                           — health check
"""
import json, time, sys
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Query, HTTPException, Path as PathParam
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Import the orchestrator
SCRIPTS_DIR = Path(__file__).parent / "scripts"
import sys
sys.path.insert(0, str(SCRIPTS_DIR))

# Import after path setup
from scripts.resolve_address_full import resolve_full

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

# ─── Models ──────────────────────────────────────────────────────────────────

class BatchResolveRequest(BaseModel):
    addresses: list[str]

class BatchResolveResponse(BaseModel):
    results: list[dict]
    meta: dict

# ─── Helpers ─────────────────────────────────────────────────────────────────

REPO = Path(__file__).parent.parent
META_FILE = REPO / "data" / "meta.json"

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
    """
    start = time.time()
    result = resolve_full(address)
    elapsed_ms = int((time.time() - start) * 1000)
    result["_meta"]["elapsed_ms"] = elapsed_ms
    result["_meta"]["resolved_address"] = address

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

@app.get("/")
def root():
    return {
        "service": "Fort Worth Intelligence API",
        "version": "1.0.0",
        "endpoints": {
            "GET /resolve?address=...": "Resolve a single address",
            "POST /resolve/batch": "Batch resolve multiple addresses",
            "GET /legistar/{district}": "Council agenda items by district",
            "GET /legistar/meeting/{id}": "Agenda items for a specific meeting",
            "GET /health": "Health check",
        },
    }