# Civic Digital Twin — Skill Suite

**Project:** Fort Worth Intelligence  
**Suite:** digital-twin v0.1.0  
**Manifest:** `skills/digital-twin-suite.yaml`

This project is built using a 6-skill suite that sequences from raw civic sources to a shipped digital twin. All skills live at:

```
/home/tyler/.openclaw/workspace/skills/
```

## Skill Suite

| # | Skill | Purpose |
|---|-------|---------|
| 1 | `civic-source-registry` | Discover, verify, normalize, and prioritize civic data sources |
| 2 | `civic-ingestion-pipeline` | Pull, snapshot, dedupe, and track source data ingestion runs |
| 3 | `civic-ontology-maintainer` | Maintain entity, relationship, and ID contracts |
| 4 | `civic-graph-api` | Expose resolve, graph, and aggregate query surfaces |
| 5 | `civic-spatial-temporal` | Add geometry, time, diffs, and replay semantics |
| 6 | `civic-twin-ops` | Harden, validate, package, and ship the system |

## Orchestration Entry Point

Use `civic-twin-builder` to drive the full sequence:

```bash
# Check what would run
node /home/tyler/.openclaw/workspace/skills/civic-twin-builder/scripts/twin-build-harness.js \
  --dry-run --project-root /home/tyler/fort-worth-intelligence

# See current state (which steps are done)
node /home/tyler/.openclaw/workspace/skills/civic-twin-builder/scripts/twin-build-harness.js \
  --status --project-root /home/tyler/fort-worth-intelligence

# Advance to next incomplete step
node /home/tyler/.openclaw/workspace/skills/civic-twin-builder/scripts/twin-build-harness.js \
  --next --project-root /home/tyler/fort-worth-intelligence
```

## Build State

State file: `.twin-build-state.yaml` in this project root.

Tracks: completed steps, timestamps, coverage %, last run result.

## Skill Resources

Each skill has:
- `SKILL.md` — triggering description and workflow
- `references/` — YAML contracts and shape definitions
- `scripts/` — executable utilities (Python + Node.js)

## Ship Targets

See `references/ship-targets.yaml` inside the `civic-twin-builder` skill for:
- coverage minimums (80%)
- required graph API endpoints
- required ingestion layers
- production gate checklist

## Current Status

This file is the landing point. When starting work on this project:

1. Read this file
2. Run the harness status check
3. Continue from the next incomplete step

Do not skip ahead in the sequence. Each step feeds the next.
