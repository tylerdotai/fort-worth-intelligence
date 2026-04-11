# TAD Parcel / Appraisal Data Ingestion

## What TAD publishes

Tarrant Appraisal District (TAD) provides a full certified appraisal data export — the same format used to transfer appraisal data to tax offices across Texas. This is a bulk download, not a web query. It contains every property in Tarrant County.

**Source:** https://www.tad.org → Resources → Data Downloads

## Export file layout

The complete layout is documented in:
`TP_Legacy8.0.32-AppraisalExportLayout.xlsx` (extracted from TAD's data downloads)

This is a fixed-width format with 21 file types:

### File overview

| File | Short name | Description |
|------|-----------|-------------|
| `APPRAISAL_HEADER.TXT` | `APPR_HDR.TXT` | Run date, entity, operator, year, version |
| **`APPRAISAL_INFO.TXT`** | `PROP.TXT` | **Core property/owner record** |
| **`APPRAISAL_ENTITY_INFO.TXT`** | `PROP_ENT.TXT` | **Property-entity taxable value links** |
| `APPRAISAL_ENTITY_TOTALS.TXT` | `TOTALS.TXT` | Entity-level aggregated totals |
| `APPRAISAL_ABSTRACT_SUBDV.TXT` | `ABS_SUBD.TXT` | Abstract/subdivision code lookups |
| `APPRAISAL_STATE_CODE.TXT` | `STATE_CD.TXT` | State property tax code definitions |
| `APPRAISAL_IMPROVEMENT_INFO.TXT` | `IMP_INFO.TXT` | Improvement records per property |
| `APPRAISAL_IMPROVEMENT_DETAIL.TXT` | `IMP_DET.TXT` | Improvement detail (yr built, sqft, value) |
| `APPRAISAL_IMPROVEMENT_DETAIL_ATTR.TXT` | `IMP_ATR.TXT` | Improvement attributes (finish, roofing, HVAC) |
| `APPRAISAL_LAND_DETAIL.TXT` | `LAND_DET.TXT` | Land segments, type, acres, value |
| `APPRAISAL_AGENT.TXT` | `AGENT.TXT` | Agent information |
| `APPRAISAL_ARB.TXT` | `ARB.TXT` | Active ARB (protest) properties |
| `APPRAISAL_LAWSUIT.TXT` | `LAWSUIT.TXT` | Active lawsuit properties |
| `APPRAISAL_ENTITY.TXT` | `ENTITY.TXT` | Entity definitions |
| `APPRAISAL_MOBILE_HOME_INFO.TXT` | `MOBILE_HOME_INFO.TXT` | Mobile home records |
| `APPRAISAL_TAX_DEFERRAL_INFO.TXT` | `TAX_DEFERRAL_INFO.TXT` | OV65/DP/DV tax deferral records |
| `APPRAISAL_SKETCH_INFO.TXT` | `SKETCH.TXT` | Sketch data (Legacy + Enhanced JSON) |
| `APPRAISAL_SB12.TXT` | `SB12.TXT` | SB12 compression calculation details |

## Core fields (APPRAISAL_INFO.TXT)

Key fields in the main property file:

```
prop_id          — Property ID (primary key)
prop_type_cd     — R=Real, P=Business Personal, M=Mobile Home, MN=Mineral, A=Auto
prop_val_yr     — Appraisal year
sup_num         — Supplement version (0 = certified)
geo_id          — Geographic ID
py_owner_name   — Property year owner name
py_addr_line1/2/3, city, state, zip — Owner mailing address
situs_street, situs_city, situs_zip — Property location address
legal_desc      — Legal description
land_hstd_val    — Land homestead value
land_non_hstd_val
imprv_hstd_val   — Improvement homestead value
imprv_non_hstd_val
appraised_val    — Appraised value
assessed_val     — Assessed value (after cap)
deed_book_id, deed_book_page, deed_dt — Deed reference
market_value     — Market value
hs_exempt        — Homestead exemption flag
ov65_exempt      — Over 65 exemption flag
arb_protest_flag — ARB protest filed
entities        — Comma-separated entities list
```

## Entity association (APPRAISAL_ENTITY_INFO.TXT)

Links properties to taxing entities. Key fields:
```
prop_id          — Property ID
owner_id         — Owner ID
entity_id        — Entity ID
entity_cd        — 10-char entity code
entity_name      — e.g. "FORT WORTH ISD"
taxable_val      — Taxable value
hs_amt, ov65_amt, dv_amt — Exemption amounts
```

## Ingestion approach

### Step 1 — Download the certified export
Available from TAD data downloads. Naming convention:
`YYYY-MM-DD_<dataset_id>_APPRAISAL_INFO.TXT`

Certified residential is typically ~46 MB compressed (ZIP).

### Step 2 — Parse the fixed-width records
Each record is fixed-width. Field positions are in the layout spreadsheet.

### Step 3 — Filter to Fort Worth
Filter by `situs_city = 'FORT WORTH'` or by GIS boundary overlap.

### Step 4 — Enrich with owner + entity data
Join with `APPRAISAL_ENTITY_INFO.TXT` to get per-entity taxable values.

### Step 5 — Build address resolution index
For each property, store:
- `prop_id`
- situs address → canonical address string
- lat/lon (via GIS boundary cross-reference if available)
- school district, council district, utility district (from entity links)

## Product opportunities from this data

- **Address → appraisal record resolver** (the core)
- **Tax burden analysis** per address
- **Protest tracking** via ARB file
- **Exemption analysis** (HS, OV65, DV, etc.) across Fort Worth
- **Lawsuit risk** flagging for properties in litigation
- **Value change detection** by comparing year-over-year exports
- **School district boundary verification** via entity links

## Notes

- Data files use OEM/ASCII encoding; handle line endings carefully
- Files are pipe-delimited header + fixed-width data rows
- Multiple owners per property → multiple rows with same `prop_id`
- Supplement roll updates are noted with `sup_num > 0` and `sup_action` (A/M/D)
