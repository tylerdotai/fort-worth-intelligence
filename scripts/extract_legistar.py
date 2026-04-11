#!/usr/bin/env python3
"""
Legistar / Fort Worth City Council agenda extractor.

Data sources:
  - Calendar page: https://fortworthgov.legistar.com/Calendar.aspx
    (Telerik RadGrid, table rows with body name, date, time, location, etc.)
  - iCal feed per meeting: https://fortworthgov.legistar.com/View.ashx?M=IC&ID=...&GUID=...
  - Agenda: View.ashx?M=A&ID=...&GUID=...
  - Minutes: View.ashx?M=M&ID=...&GUID=...

Rate limit: max 1 request / 30 seconds.
"""
import json, subprocess, re, sys, time, os, html as htmlmod
from datetime import datetime, timezone
from urllib.parse import urlparse

CAL_BASE = "https://fortworthgov.legistar.com"
CAL_URL  = f"{CAL_BASE}/Calendar.aspx"
MEET_URL = f"{CAL_BASE}/MeetingDetail.aspx"
ICAL_BASE = f"{CAL_BASE}/View.ashx"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; FortWorthIntelligence/1.0; "
        "+https://github.com/tylerdotai/fort-worth-intelligence"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

# ─── low-level fetch ───────────────────────────────────────────────────────────

def fetch(url):
    cmd = [
        "curl", "-s", "--max-time", "20", "-L",
        "-H", f"User-Agent: {HEADERS['User-Agent']}",
        "-H", f"Accept-Language: {HEADERS['Accept-Language']}",
    ]
    cmd.append(url)
    r = subprocess.run(cmd, capture_output=True, text=True, errors="replace", timeout=25)
    return r.stdout


# ─── parse calendar page ───────────────────────────────────────────────────────

ICAL_RE    = re.compile(r'M=IC&ID=(\d+)&GUID=([A-F0-9-]+)', re.IGNORECASE)
MEET_RE    = re.compile(r'MeetingDetail\.aspx\?ID=(\d+)&GUID=([A-F0-9-]+)', re.IGNORECASE)
BODY_RE    = re.compile(r'DepartmentDetail\.aspx\?ID=\d+&GUID=[^"]+"[^>]*>([^<]+)</a>', re.IGNORECASE)
DATE_RE    = re.compile(r'(\d{1,2}/\d{1,2}/\d{4})')
TIME_RE    = re.compile(r'(\d{1,2}:\d{2}\s*[APap][Mm])')
LOC_BR_RE  = re.compile(r'<br\s*/?>.*?(?:<em>([^<]*)</em>)?', re.DOTALL)
NOT_AVAIL  = re.compile(r'Not\s* ?available', re.IGNORECASE)
MEET_DETAIL_RE = re.compile(r'MeetingDetail\.aspx\?ID=(\d+)&GUID=([A-F0-9-]+)', re.IGNORECASE)
ICAL_URL_RE  = re.compile(r'View\.ashx\?M=IC&ID=(\d+)&GUID=([A-F0-9-]+)', re.IGNORECASE)

# Columns in the RadGrid table (0-indexed):
# 0: Body/Dept name (with dept link)
# 1: Meeting date
# 2: iCal link
# 3: Meeting time
# 4: Location (with optional <em>)
# 5: Meeting details link
# 6: Agenda status
# 7: Agenda packet status
# 8: Minutes status
# 9: Video status

def parse_table_row(body_html):
    """Extract meeting data from one RadGrid table row. Returns dict or None."""
    # Strip all tags, keep text
    def text_only(html):
        return re.sub(r'<[^>]+>', ' ', html).strip()

    def strip_tags(html):
        return re.sub(r'<[^>]+>', '', html).strip()

    cells = re.findall(r'<td[^>]*>(.*?)</td>', body_html, re.DOTALL|re.IGNORECASE)
    if len(cells) < 10:
        return None

    # Cell 0: body name
    body_name = text_only(cells[0])

    # Cell 1: meeting date
    date_text = text_only(cells[1])

    # Cell 2: iCal URL (M=IC)
    ical_match = ICAL_URL_RE.search(cells[2])
    if not ical_match:
        return None
    mid, guid = ical_match.group(1), ical_match.group(2)

    # Cell 3: time
    time_text = text_only(cells[3])

    # Cell 4: location
    loc_text = text_only(cells[4])
    # Remove trailing <br> artifacts
    loc_text = re.sub(r'\s+', ' ', loc_text).strip()

    # Cell 5: meeting details link
    meet_match = MEET_DETAIL_RE.search(cells[5])
    meet_detail_url = ""
    if meet_match:
        meet_detail_url = f"{MEET_URL}?ID={meet_match.group(1)}&GUID={meet_match.group(2)}&Options=info|&Search="

    # Cell 6: agenda status (available / not available)
    agenda_available = "not" not in text_only(cells[6]).lower()

    # Cell 7: agenda packet
    packet_available = "not" not in text_only(cells[7]).lower()

    # Cell 8: minutes
    minutes_available = "not" not in text_only(cells[8]).lower()

    # Cell 9: video
    video_available = "not" not in text_only(cells[9]).lower()

    return {
        "id":               int(mid),
        "guid":             guid.upper(),
        "body":             body_name,
        "meeting_date":    date_text,
        "meeting_time":    time_text,
        "location":         loc_text,
        "meeting_url":      meet_detail_url,
        "ical_url":         f"{ICAL_BASE}?M=IC&ID={mid}&GUID={guid}",
        "agenda_url":       f"{ICAL_BASE}?M=A&ID={mid}&GUID={guid}",
        "minutes_url":     f"{ICAL_BASE}?M=M&ID={mid}&GUID={guid}",
        "agenda_available": agenda_available,
        "packet_available": packet_available,
        "minutes_available": minutes_available,
        "video_available":  video_available,
    }


def parse_calendar_page(html_content):
    """Parse all meeting rows from the Legistar calendar page HTML."""
    decoded = htmlmod.unescape(html_content)
    row_pattern = re.compile(
        r'<tr[^>]*class="rg(Row|AltRow)"[^>]*>(.*?)</tr>',
        re.DOTALL|re.IGNORECASE
    )
    meetings = []
    for cls, body in row_pattern.findall(decoded):
        rec = parse_table_row(body)
        if rec:
            meetings.append(rec)
    return meetings


# ─── parse iCal record ────────────────────────────────────────────────────────

def parse_ical(text, meeting_id=None, guid=None):
    """Parse View.ashx?M=IC vCal/iCal response into a dict."""
    result = {
        "id":          meeting_id,
        "guid":        guid,
        "dtstart":     "",
        "dtend":       "",
        "summary":     "",
        "location":    "",
        "description":  "",
    }
    key_map = {
        "DTSTART":    "dtstart",
        "DTEND":      "dtend",
        "SUMMARY":    "summary",
        "LOCATION":   "location",
        "DESCRIPTION":"description",
    }
    current_key = None
    for line in text.split('\n'):
        line = line.strip()
        if not line or line.startswith(("BEGIN", "END")):
            current_key = None
            continue
        if ':' in line:
            key, _, value = line.partition(':')
            key = key.strip()
            if key in key_map:
                result[key_map[key]] = value.strip()
                current_key = key
        elif current_key and line:
            result[key_map[current_key]] += line.strip()

    # Format dtstart/dtend from YYYYMMDDTHHMMSS to YYYY-MM-DDTHH:MM:SS
    for fld in ("dtstart", "dtend"):
        val = result[fld]
        if val and len(val) >= 15:
            result[fld] = f"{val[:4]}-{val[4:6]}-{val[6:11]}:{val[11:13]}:{val[13:15]}"
        elif val and len(val) == 8:
            result[fld] = f"{val[:4]}-{val[4:6]}-{val[6:8]}"

    result["cancelled"] = "CANCELLED" in text.upper()
    return result


# ─── scrape ───────────────────────────────────────────────────────────────────

def scrape_calendar(max_pages=3, min_delay=5):
    """Walk up to max_pages of the Legistar calendar."""
    all_meetings = []
    for page in range(1, max_pages + 1):
        url = f"{CAL_URL}?page={page}" if page > 1 else CAL_URL
        page_html = fetch(url)
        if not page_html or len(page_html) < 500:
            print(f"[WARN] calendar page {page} returned thin/empty content", file=sys.stderr)
            continue

        meetings = parse_calendar_page(page_html)
        if not meetings:
            break

        all_meetings.extend(meetings)
        print(f"[OK] page {page}: {len(meetings)} meetings", file=sys.stderr)
        time.sleep(min_delay)

    return all_meetings


def enrich_with_ical(meeting, min_delay=3):
    """Fetch iCal for a single meeting and merge."""
    text = fetch(meeting["ical_url"])
    if not text or len(text) < 10:
        meeting["_enrich_error"] = "empty iCal response"
        return meeting

    ical = parse_ical(text, meeting["id"], meeting["guid"])
    return {**meeting, **ical}


def enrich_all(meetings, min_delay=3):
    """Sequentially enrich all meetings."""
    enriched = []
    for i, m in enumerate(meetings):
        e = enrich_with_ical(m, min_delay=min_delay)
        enriched.append(e)
        cancelled = " [CANCELLED]" if e.get("cancelled") else ""
        print(f"[OK] {i+1}/{len(meetings)}: {e.get('body','?')} on {e.get('meeting_date','?')}{cancelled}", file=sys.stderr)
        time.sleep(min_delay)
    return enriched


# ─── save ─────────────────────────────────────────────────────────────────────

def save(meetings, out_path):
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    result = {
        "meta": {
            "scraped_at":     datetime.now(timezone.utc).isoformat(),
            "source":         CAL_URL,
            "total_meetings": len(meetings),
        },
        "meetings": meetings,
    }
    with open(out_path, "w") as f:
        json.dump(result, f, indent=2, default=str)
    print(f"Wrote {len(meetings)} meetings → {out_path}", file=sys.stderr)


# ─── main ─────────────────────────────────────────────────────────────────────

def main():
    import argparse
    p = argparse.ArgumentParser(description="Fort Worth Legistar agenda extractor")
    p.add_argument("--max-pages", type=int, default=3)
    p.add_argument("--enrich", action="store_true", help="Also fetch iCal records")
    p.add_argument("--output", default="data/legistar-meetings.json")
    p.add_argument("--min-delay", type=int, default=5)
    opts = p.parse_args()

    repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    out_path = os.path.join(repo, opts.output)

    print("Scraping Legistar calendar...", file=sys.stderr)
    meetings = scrape_calendar(max_pages=opts.max_pages, min_delay=opts.min_delay)
    print(f"\nTotal meetings found: {len(meetings)}", file=sys.stderr)

    if meetings and opts.enrich:
        print("\nFetching iCal records...", file=sys.stderr)
        meetings = enrich_all(meetings, min_delay=opts.min_delay)

    save(meetings, out_path)
    return meetings


if __name__ == "__main__":
    main()
