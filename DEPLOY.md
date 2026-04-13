# Deploy Plan — Fort Worth Intelligence API

**Last updated:** 2026-04-13

---

## Environments

| Environment | Host | Command |
|---|---|---|
| Local dev | clawbox :8000 | `python3 -m uvicorn api_server:app --host 0.0.0.0 --port 8000` |
| Production | fly.io (fort-os) | `flyctl deploy` |

---

## Local Deploy

```bash
cd /home/tyler/fort-worth-intelligence

# Verify tests and coverage first
node scripts/run_release_gates.js

# Start the API
python3 -m uvicorn api_server:app --host 0.0.0.0 --port 8000 --workers 2

# Verify
curl -s http://localhost:8000/health | jq .
curl -s "http://localhost:8000/resolve?address=704%20E%20Weatherford%20St%2C%20Fort%20Worth%2C%20TX%2076102" | jq .
```

---

## Production Deploy (Fly.io)

```bash
# From the fort-worth-intelligence repo root
flyctl deploy --imageRegistry ghcr.io/tylerdotai/fort-worth-intelligence

# Verify
curl -s https://fort-worth-intelligence.fly.dev/health | jq .
```

---

## Data Refresh

Run extractors before deploy to ensure fresh data:

```bash
# Full refresh (run in order)
python3 scripts/extract_legistar.py       # ~5 min
python3 scripts/extract_tad_parmels.py     # ~20 min (large file)
python3 scripts/extract_fw_permits.py     # ~3 min
python3 scripts/extract_fw_crime.py         # ~2 min
python3 scripts/build_cache.py             # rebuild address index
```

---

## Smoke Test After Deploy

```bash
# Health
curl -sf https://fort-worth-intelligence.fly.dev/health

# Resolve
curl -sf "https://fort-worth-intelligence.fly.dev/resolve?address=704%20E%20Weatherford%20St%2C%20Fort%20Worth%2C%20TX%2076102"

# Graph
curl -sf https://fort-worth-intelligence.fly.dev/graph/fw:council:2

# Schema
curl -sf https://fort-worth-intelligence.fly.dev/meta/schema | jq .ontology_version
```

All should return HTTP 200 with non-empty JSON.
