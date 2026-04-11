# Real Estate Transactions — Tarrant County Clerk Official Records

## Access Status: BARRIER — Subscription Required

### CountyFusion (Tarrant County Official Records)
**URL:** https://countyfusion.tarrantcounty.com/

The Tarrant County Clerk's official records search is hosted on the **CountyFusion** platform (Vital Statistics Group / Tyler Technologies). This is the authoritative source for:
- Warranty deeds
- Deed recordings
- Mortgage filings / releases
- Lien activity
- Abstracts

**Access model:** Requires login. Public visitor access redirects to login page. No guest/search-only tier available.

**Subscription options:**
- CountyFusion offers subscription accounts for title companies, realtors, and researchers
- Individual search may be available via walk-in at the County Clerk's office (100 N. Calhoun St., 2nd Floor, Fort Worth)

### Tarrant Appraisal District (TAD) — Partial Alternative
**URL:** https://www.tad.org/

TAD maintains a property search that includes recent sales data. The **certified residential roll** (which we already have at `data/tad-parcels-fort-worth.json`) includes:
- `deed_date` — date of most recent deed filing
- `owner_name` — current owner of record
- `market_value` — assessed market value

**Limitation:** Historical only — the certified roll reflects the 2025 appraisal year. Transactions after the lien date (typically January) may not be reflected until the next supplemental roll.

**Free TAD data available:**
- Certified residential roll: downloadable ZIP from tad.org (pipe-delimited, ~283K Fort Worth parcels)
- Supplemental rolls: published monthly on the TAD website

## Recommended Path

**Option A — CountyFusion subscription** (for production use):
- Tyler acquires a CountyFusion subscription if ongoing transaction monitoring is needed
- Cost: typically $75-200/month for commercial research access
- After acquiring credentials: script login + search using Playwright session management

**Option B — TAD certified roll as proxy** (for current snapshot):
- The `deed_date` field in the existing parcel data is the best available free signal
- Supplement with monthly re-downloads of the TAD certified roll
- Detect "new" transactions by comparing `deed_date` against last download date
- Limitation: only captures transactions recorded before the lien date; misses recent flips

**Option C — Title company data** (for real-time):
- Title companies maintain proprietary transaction feeds
- May be accessible via API for commercial partnerships
- Lower priority for civic intelligence purposes

## Implementation Notes

If/when CountyFusion access is obtained:

```python
# Pseudocode — requires valid credentials
from playwright.sync_api import sync_playwright

def search_countyfusion(owner_name=None, address=None, date_from=None):
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page()
        
        # Login
        page.goto("https://countyfusion.tarrantcounty.com/countyweb/login.jsp")
        page.fill("#username", CREDS["username"])
        page.fill("#password", CREDS["password"])
        page.click("button[type='submit']")
        page.wait_for_url("**/home**", timeout=30000)
        
        # Navigate to real estate search
        page.goto("https://countyfusion.tarrantcounty.com/countyweb/search/realEstate")
        page.wait_for_load_state("networkidle")
        
        if address:
            page.fill("#propertyAddress", address)
        if owner_name:
            page.fill("#grantorGrantee", owner_name)
        if date_from:
            page.fill("#recordDateFrom", date_from)
        
        page.click("#searchButton")
        page.wait_for_selector(".results-grid", timeout=30000)
        
        # Parse results...
```

## Data Available Once Access Obtained

Per deed record:
- Document type (Warranty Deed, Deed of Trust, Release, etc.)
- Grantor / Grantee names
- Property address
- Recording date
- Instrument number
- Volume / page
- Consideration (sale price)
- Property description (lot/block/subdivision)

**Alert signals:**
- New warranty deed > $500K (institutional buyer activity)
- Corporate grantee (LLC, Inc, LP) acquiring in residential zone (flip signal)
- Notice of foreclosure (distressed property)
- Multi-parcel acquisition (developer accumulating lots)
- Sheriff's deed / tax sale (distressed pipeline)
