#!/bin/bash
# start.sh — Fort Worth Intelligence container start script
# Handles TAD certified roll download + extraction, then starts the API.

set -e

DATA_DIR="/app/data"
TAD_DIR="${DATA_DIR}/tad"
TAD_ZIP="${TAD_DIR}/PropertyData_R_2025(Certified).ZIP"
TAD_URL="${TAD_URL:-https://www.tad.org/content/data-download/PropertyData_R_2025(Certified).ZIP}"
OUT_JSON="${DATA_DIR}/tad/tad-parcels-fort-worth.json"
OUT_JSONL="${DATA_DIR}/tad-parcels-fort-worth.jsonl"

echo "[start] Fort Worth Intelligence — starting up"
echo "[start] DATA_DIR=${DATA_DIR}"

# Ensure data directories exist
mkdir -p "${TAD_DIR}"

# ── TAD Certified Roll ──────────────────────────────────────────────────────
if [ ! -f "${TAD_ZIP}" ]; then
    echo "[start] Downloading TAD certified roll (~46MB)..."
    if ! curl -fsSL "${TAD_URL}" -o "${TAD_ZIP}"; then
        echo "[start] WARNING: TAD download failed. Parcel lookup will be limited."
    fi
else
    echo "[start] TAD ZIP already present"
fi

# Extract ZIP if raw TXT is not yet extracted
if [ -f "${TAD_ZIP}" ] && [ ! -f "${TAD_DIR}/PropertyData_R_2025.txt" ]; then
    echo "[start] Extracting TAD ZIP..."
    unzip -o -q "${TAD_ZIP}" -d "${TAD_DIR}/"
fi

# Convert JSONL → JSON if JSONL exists but JSON does not
if [ -f "${OUT_JSONL}" ] && [ ! -f "${OUT_JSON}" ]; then
    echo "[start] Converting JSONL to JSON..."
    python3 -c "
import json
out = {'parcels': []}
with open('${OUT_JSONL}') as f:
    for line in f:
        line = line.strip()
        if line:
            out['parcels'].append(json.loads(line))
with open('${OUT_JSON}', 'w') as f:
    json.dump(out, f)
print(f'Wrote {len(out[\"parcels\"]):,} parcels')
"
fi

# Pre-warm Redis cache (background)
if [ -f "${OUT_JSON}" ]; then
    echo "[start] Pre-warming Redis cache (background, ~2000 addresses)..."
    python3 scripts/build_cache.py --limit 2000 &
fi

# ── Start API ──────────────────────────────────────────────────────────────
PORT=${PORT:-8000}
echo "[start] Starting uvicorn on ${PORT}..."
exec python3 -m uvicorn api_server:app --host 0.0.0.0 --port "${PORT}"
