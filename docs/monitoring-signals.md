# Live Monitoring Signals

Defines change-frequency signals, polling logic, and alert triggers for each data layer in the Fort Worth Intelligence graph.

## Change Signal Matrix

| Layer | Source | Frequency | Signal | Alert Threshold |
|-------|--------|-----------|--------|-----------------|
| **City Council Calendar** | Legistar | Every 6h | New meetings posted, cancellations | New meeting detected |
| **Council Agenda Items** | MeetingDetail.aspx | Every 6h | New M&C/ordinance/zoning items | New items since last check |
| **Zoning Cases** | Legistar + FWPD | Daily | New zoning cases, decisions | Case # new or status=dECISION |
| **TAD Parcels** | tad.org certified roll | Monthly | New construction, ownership changes | year_built = current_cert_year |
| **Real Estate Transactions** | Tarrant County Clerk | Weekly | Deed recordings, mortgage filings | New transactions since last run |
| **Permits** | Fort Worth Open Data | Daily | New construction, demolition permits | permit_type = NEW_CONSTRUCTION |
| **Council District Boundaries** | fortworthtexas.gov | Annually | District boundary changes | Election cycle (Nov of odd years) |
| **School District Boundaries** | ISD boards + TCGIS | Annually | Annexations, consolidations | Board action + TCGIS update |
| **City Councilmembers** | fortworthtexas.gov | On election | New rep elected | Election date |
| **State Representatives** | Texas Legislature | On session | Committee assignments, sponsored bills | Bill filed in relevant committee |

## Layer Signal Definitions

---

### 1. City Council Calendar — LEGISTAR

**What to monitor:** `https://fortworthgov.legistar.com/Calendar.aspx`

**Signal:** New meetings appearing in the calendar grid

**Change logic:**
```
compare new_calendar.scraped_at
  vs previous_calendar.scraped_at
new_meetings = [m for m in new_calendar if m.id not in previous_calendar.ids]
cancelled = [m for m in previous_calendar if m.id in new_calendar.ids and m.cancelled == True]
```

**Alert trigger:** `len(new_meetings) > 0` OR `len(cancelled) > 0`

**Polling interval:** Every 6 hours (city council meets every 2 weeks, agendas posted ~7 days before)

**Known behavior:**
- Meetings appear in calendar ~2-4 weeks before the meeting date
- Cancellation flags appear when a meeting is cancelled, not when it passes

---

### 2. Council Agenda Items — LEGISTAR MEETINGDETAIL

**What to monitor:** Each meeting's `MeetingDetail.aspx` page

**Signal:** New M&C items, ordinances, resolutions, zoning cases

**Change logic:**
```
for each upcoming_meeting in calendar:
    compare new_detail.items vs cached_items[meeting.id]
    new_items = [i for i in new_items if i.file_number not in cached.file_numbers]
    status_changes = [i for i in items if i.status != cached.status(i.file_number)]
```

**Alert triggers:**
- `len(new_items) > 0` — new items published
- Any item with `type = "Zoning Case"` and `status = "Approved" | "Denied"`
- Any item with `council_districts` matching a tracked district
- `status = "Continued"` on an item that was previously pending

**Polling interval:** Every 6 hours for meetings in the next 30 days

**Key item types to watch:**
- `Award of Contract` — city spending signals
- `Zoning Case` — development activity
- `Ordinance` — regulatory changes
- `Land Consent` — eminent domain, right-of-way
- `Resolution` — policy positions

---

### 3. Zoning Cases — LEGISTAR + FWPOLICE DEPARTMENT

**What to monitor:**
- Legistar: items with `type = "Zoning Case"`
- Fort Worth Planning & Development: zoning case search

**Signal:** New zoning applications, case decisions, public hearing dates

**Change logic:**
```
new_zoning = [i for i in agenda_items
              if i.type == "Zoning Case"
              and i.file_number not in cached_zoning]
decisioned = [i for i in new_zoning if i.status in APPROVED + DENIED]
```

**Alert trigger:**
- New zoning case for council district X
- Case status changed to Approved/Denied
- Continued hearing scheduled

**Polling interval:** Daily

---

### 4. TAD New Construction — TARRANT APPRAISAL DISTRICT

**What to monitor:** Certified roll + monthly supplemental extracts

**Signal:** New parcels with `year_built = current_year` or recent sales above median

**Change logic:**
```
# Full certified roll: downloaded annually in April
# Monthly supplements: check tad.org for "supplemental" exports
new_construction = [p for p in tad_parcels
                    if p.year_built >= (current_year - 1)
                    and p.city in FORT_WORTH_ZIPS]
high_value_sales = [p for p in tad_parcels
                     if p.market_value > 1_000_000
                     and p.sale_date > last_check]
```

**Alert triggers:**
- `year_built >= 2025` for Fort Worth address
- Sale price > $1M on residential
- Ownership change from corporate to individual (flip signal)

**Polling interval:** Monthly (supplemental rolls are monthly; certified is annual)

---

### 5. Real Estate Transactions — TARRANT COUNTY CLERK

**What to monitor:** Official public record search (Tarrant County Clerk)

**Signal:** Deed recordings, mortgage filings, lien releases

**Change logic:**
```
# Check Tarrant County Clerk's online search for recordings since last_check
recent_recordings = search_recording_database(
    date_from = last_check_date,
    property_city = "FORT WORTH"
)
```

**Alert triggers:**
- New warranty deed > $500K (institutional buyer activity)
- Notice of foreclosure (distressed property signal)
- Multi-parcel acquisition (developer accumulating lots)

**Polling interval:** Weekly (deeds are recorded in batches)

---

### 6. Building Permits — FORT WORTH OPEN DATA

**What to monitor:** Fort Worth open data portal — building permits dataset

**Signal:** New construction starts, major renovations, demolitions

**Change logic:**
```
# Fort Worth publishes permit data via open data portal
# ArcGIS feature service or CSV export
new_permits = query_permits(
    issued_date > last_check,
    permit_type in [NEW_CONSTRUCTION, DEMOLITION, MAJOR_RENOVATION]
)
```

**Alert triggers:**
- `permit_type = "NEW CONSTRUCTION"` in a tracked council district
- `work_description` contains "MULTI-FAMILY" (5+ units) or "COMMERCIAL"
- Demolition in historically significant zone

**Polling interval:** Daily (permits are issued daily)

---

## Monitoring Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    MONITORING ORCHESTRATOR                   │
│                  (cron-triggered Python script)              │
└──────────────────────┬──────────────────────────────────────┘
                       │
     ┌─────────────────┼──────────────────┐
     ▼                 ▼                  ▼
┌─────────┐     ┌─────────────┐    ┌──────────────┐
│ LEGISTAR │     │ TAD        │    │ FW OPEN DATA │
│ CALENDAR │     │ CERTIFIED  │    │ PERMITS      │
│ every 6h │     │ ROLL       │    │ daily        │
└────┬─────┘     │ monthly    │    └──────┬───────┘
     │           └─────┬──────┘           │
     │                 │                  │
     └────────┬────────┴──────────────────┘
              ▼
     ┌─────────────────┐
     │  CHANGE DETECT  │
     │  Compare vs      │
     │  last snapshot   │
     └────────┬────────┘
              ▼
     ┌─────────────────┐
     │  ALERT          │
     │  Discord webhook│
     │  + JSON diff    │
     └─────────────────┘
```

## Alert Output Format

```json
{
  "alerted_at": "2026-04-11T06:00:00Z",
  "layer": "legistar_agenda_items",
  "change_type": "new_items",
  "meeting_id": 1386685,
  "meeting_date": "2026-03-31",
  "new_items": [
    {
      "file_number": "M&C 26-0261",
      "type": "Award of Contract",
      "title": "(CD 7) Authorize Professional Services Agreement...",
      "council_districts": "7",
      "status": "Pending"
    }
  ],
  "previous_item_count": 78,
  "current_item_count": 79,
  "delta": 1
}
```

## Alert Channel

- **Primary:** Discord webhook → `#fw-intelligence-alerts` (to be created)
- **Format:** Plain text summary + JSON attachment
- **Deduplication:** Alert keyed on `layer + meeting_id + change_type + file_number`

## Known Gaps (Monitoring Limitations)

1. **Legistar requires session cookies** — the ASP.NET session times out; must re-fetch calendar page periodically to refresh cookies
2. **TAD supplemental rolls** — monthly, but not published on a fixed schedule
3. **Tarrant County Clerk search** — requires human verification for bulk queries
4. **Council district boundaries** — no automated change feed; verify on election cycles only
5. **FW Open Data permits** — ArcGIS feature service may be rate-limited; use bulk CSV export when available
