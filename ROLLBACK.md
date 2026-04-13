# Rollback Plan — Fort Worth Intelligence

**Last updated:** 2026-04-13
**Owner:** Flume SaaS Factory / Tyler

---

## What Can Go Wrong

| Failure mode | Impact | Rollback action |
|---|---|---|
| API returns wrong data | Wrong civic records served | Revert to previous commit |
| Data pipeline breaks | Stale data in responses | Re-run last-good extractor |
| Schema change breaks clients | API incompatibility | Revert to previous ONTOLOGY.md |
| Deploy to wrong host | Wrong environment | Kill process, redeploy correct branch |

---

## API Server Rollback

### FastAPI (port 8000)

```bash
# See what version is currently running
curl -s http://localhost:8000/health | jq .version

# Kill current process
pkill -f "uvicorn api_server:app"
sleep 2

# Revert to previous commit
git checkout HEAD~1
git pull

# Restart
python3 -m uvicorn api_server:app --host 0.0.0.0 --port 8000
```

### Verify rollback
```bash
curl -s http://localhost:8000/health
# Should return expected version
```

---

## Data Pipeline Rollback

Each extractor downloads from a canonical civic source. If a new run produces bad data, restore from the previous certified version:

```bash
# List recent extractor runs
ls -la data/

# Restore a specific file from git
git checkout HEAD~1 -- data/fw-permits.json

# Re-run specific extractor
python3 scripts/extract_fw_permits.py
```

**Key files and their sources:**

| File | Source | Cadence |
|---|---|---|
| `legistar-meetings.json` | fortworthgov.legistar.com | Weekly |
| `legistar-agenda-items.json` | fortworthgov.legistar.com | Weekly |
| `tad-parcels-fort-worth.json` | TAD certified roll | Quarterly (Jan/Apr/Jul/Oct) |
| `fw-permits.json` | City of Fort Worth Open Data | Monthly |
| `fw-crime.json` | Fort Worth PD open data | Monthly |

---

## Schema Rollback

ONTOLOGY.md is versioned. If a schema change breaks clients:

```bash
# Revert ontology
git checkout HEAD~1 -- ONTOLOGY.md
# Restart API to pick up old schema
pkill -f "uvicorn api_server:app"
python3 -m uvicorn api_server:app --host 0.0.0.0 --port 8000
```

---

## Environment Variables

```
FWI_DATA_DIR     = /home/tyler/fort-worth-intelligence/data
FWI_LOG_LEVEL    = INFO  # DEBUG for verbose
TAD_SNAPSHOT_URL = https://compressed.tad.gov/Tarrant_2026_04.zip
```

---

## Emergency Contacts

- **Civic sources:** Fort Worth ITD — https://fortworthgov.legistar.com
- **TAD data:** Tarrant Appraisal District — https://www.tad.org
- **Deploy lead:** Tyler (Flume) — @tylerdotai on Discord
