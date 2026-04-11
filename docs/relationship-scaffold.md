# Relationship Scaffold

Starter relationship model for turning the Fort Worth source registry into a civic intelligence graph.

## Core entities
- address
- parcel
- institution
- district
- official
- meeting
- agenda-item
- ordinance
- project
- school-district
- utility-district
- tax-body
- records-portal

## Key relationships

### Address-centric
- address -> located_in -> city
- address -> located_in -> county
- address -> located_in -> council-district
- address -> served_by -> school-district
- address -> served_by -> transit-body
- address -> served_by -> utility-district
- address -> taxed_by -> tax-body
- address -> represented_by -> official

### Parcel-centric
- parcel -> assessed_by -> appraisal-district
- parcel -> taxed_by -> tax-office
- parcel -> linked_to -> address
- parcel -> affected_by -> zoning-case
- parcel -> affected_by -> project

### Governance-centric
- institution -> publishes -> meeting
- meeting -> contains -> agenda-item
- agenda-item -> references -> ordinance
- agenda-item -> references -> project
- agenda-item -> affects -> district
- agenda-item -> affects -> neighborhood
- official -> serves_on -> institution

### District-centric
- district -> represented_by -> official
- district -> includes -> address
- district -> overlaps -> school-district
- district -> overlaps -> utility-district

## Suggested next implementation files
- `data/model/relationships.json`
- `data/model/entity-types.json`
- **`docs/address-resolution-schema.md`** — canonical schema for address → district pipeline (AVAILABLE)
- `scripts/resolve_address_full.py` — orchestrates full pipeline

## Why this matters

Without relationships, the source catalog is just a list.
With relationships, it becomes a civic reasoning system.
