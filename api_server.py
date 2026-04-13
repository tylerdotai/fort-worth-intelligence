#!/usr/bin/env python3
"""
FastAPI server for Fort Worth Address Resolution API.

Run:
  python3 -m uvicorn api_server:app --reload --port 8000

Endpoints:
  GET /resolve?address=704+E+Weatherford+St  — full address resolution
  GET /resolve/batch                        — batch resolve (POST with JSON body)
  GET /health                               — health check
"""
import json, time, sys
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Import the orchestrator
SCRIPTS_DIR = Path(__file__).parent / "scripts"
import sys
sys.path.insert(0, str(SCRIPTS_DIR))

# Import after path setup
from scripts.resolve_address_full import resolve_full

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
    - Council district
    - School district
    - Utility districts
    - TX House representative
    """
    start = time.time()
    result = resolve_full(address)
    elapsed_ms = int((time.time() - start) * 1000)
    result["_meta"]["elapsed_ms"] = elapsed_ms
    result["_meta"]["resolved_address"] = address
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

@app.get("/")
def root():
    return {
        "service": "Fort Worth Intelligence API",
        "version": "1.0.0",
        "endpoints": {
            "GET /resolve?address=...": "Resolve a single address",
            "POST /resolve/batch": "Batch resolve multiple addresses",
            "GET /health": "Health check",
        },
    }