#!/usr/bin/env python3
"""
Legistar agenda item extractor for Fort Worth City Council.

Fetches MeetingDetail.aspx for each meeting and parses agenda items
into structured JSON.

Cells in agenda table (10 columns):
  [0] File #  (e.g. M&C 26-0206, ZC-25-172, 26-5865)
  [1] Version (e.g. 1)
  [2] Item #  (e.g. 1., 2., 3.)
  [3] BL      (usually empty - bulletin flag?)
  [4] Type    (e.g. General Consent, Ordinance, Resolution, Zoning Case)
  [5] Title   (e.g. "(CD 7) Ratify Waiver of...")
  [6] Status  (e.g. Approved, Adopted, Continued, etc.)
  [7] Attachments (e.g. Video or empty)
  [8] Action details (link text, usually "Action details")
  [9] Attachment availability (e.g. "Not available", "Video")

Rate limit: 1 request / 5 seconds per meeting.
"""
import json, subprocess, re, sys, time, os, html as htmlmod
from datetime import datetime, timezone
from pathlib import Path

CAL_BASE     = "https://fortworthgov.legistar.com"
MEET_BASE    = f"{CAL_BASE}/MeetingDetail.aspx"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; FortWorthIntelligence/1.0; +https://github.com/tylerdotai/fort-worth-intelligence)",
    "Accept-Language": "en-US,en;q=0.9",
}


# ─── fetch ───────────────────────────────────────────────────────────────────

def fetch(url, cookie_path="/tmp/legistar_cookies.txt"):
    cmd = [
        "curl", "-s", "--max-time", "20", "-L",
        "-c", cookie_path,
        "-b", cookie_path,
        "-H", f"User-Agent: {HEADERS['User-Agent']}",
        "-H", f"Accept-Language: {HEADERS['Accept-Language']}",
        url,
    ]
    r = subprocess.run(cmd, capture_output=True, text=True, errors="replace", timeout=25)
    return r.stdout


# ─── parse meeting header ────────────────────────────────────────────────────

def parse_meeting_header(content):
    """Extract meeting-level fields from MeetingDetail.aspx HTML."""
    text = htmlmod.unescape(content)

    result = {
        "meeting_name": "",
        "meeting_date": "",
        "meeting_time": "",
        "meeting_location": "",
        "agenda_status": "",
        "minutes_status": "",
        "agenda_published": "",
        "minutes_published": "",
        "video_available": "",
        "agenda_note": "",
    }

    # Title: "City of Fort Worth - Meeting of CITY COUNCIL on 4/28/2026"
    m = re.search(r"Meeting of\s+([^<]+)\s+on\s+(\d{1,2}/\d{1,2}/\d{4})", text)
    if m:
        result["meeting_name"] = m.group(1).strip()
        result["meeting_date"] = m.group(2).strip()

    # Extract key-value pairs from the info table
    kv_pattern = re.compile(r"<span[^>]*id=[^>]*>([^<]+)</span>\s*</td>\s*<td[^>]*>([^<]+)</td>", re.IGNORECASE)
    for label_m, value_m in re.findall(r"<td[^>]*>([^<]+)</td>\s*<td[^>]*>(.*?)</td>", text, re.DOTALL | re.IGNORECASE):
        label = re.sub(r"<[^>]+>", "", label_m).strip().lower()
        value = re.sub(r"<[^>]+>", " ", value_m).strip()
        if "meeting name" in label:
            result["meeting_name"] = value
        elif "meeting date" in label or "date" in label and "time" in label:
            dt_match = re.match(r"(\d{1,2}/\d{1,2}/\d{4})\s*(.*)", value)
            if dt_match:
                result["meeting_date"] = dt_match.group(1)
                result["meeting_time"] = dt_match.group(2).strip()
            else:
                result["meeting_date"] = value
        elif "meeting location" in label:
            result["meeting_location"] = value
        elif "agenda status" in label:
            result["agenda_status"] = value
        elif "minutes status" in label:
            result["minutes_status"] = value
        elif "published agenda" in label:
            result["agenda_published"] = value
        elif "published minutes" in label:
            result["minutes_published"] = value
        elif "meeting video" in label:
            result["video_available"] = value

    # Agenda note (e.g. "Please note: The agenda for this meeting has not been published.")
    note_match = re.search(r"Please note:[^<]*(.*?)(?:</p>|</div>)", text, re.IGNORECASE | re.DOTALL)
    if note_match:
        result["agenda_note"] = re.sub(r"<[^>]+>", "", note_match.group(0)).strip()

    return result


# ─── parse agenda items ──────────────────────────────────────────────────────

def parse_agenda_items(content):
    """Parse all agenda item rows from MeetingDetail.aspx HTML."""
    text = htmlmod.unescape(content)

    # Rows with 10 cells contain agenda items
    all_rows = re.findall(r"<tr[^>]*>(.*?)</tr>", text, re.DOTALL | re.IGNORECASE)

    items = []
    current_section = ""

    for row in all_rows:
        cells = re.findall(r"<td[^>]*>(.*?)</td>", row, re.DOTALL | re.IGNORECASE)
        if len(cells) != 10:
            continue

        def clean(t):
            return re.sub(r"<[^>]+>", " ", t).strip().replace("\n", " ").replace("\r", "")

        file_num   = clean(cells[0])
        version    = clean(cells[1])
        item_num   = clean(cells[2])
        bl         = clean(cells[3])         # BL flag, usually empty
        item_type  = clean(cells[4])
        title      = clean(cells[5])
        status     = clean(cells[6])
        attach     = clean(cells[7])          # "Video" or empty
        action_lbl = clean(cells[8])          # "Action details"
        avail      = clean(cells[9])          # "Not available" or "Video"

        # Skip header rows and empty rows
        if not file_num or file_num in ["File #", "Attachments", ""]:
            continue
        # Skip section header rows (they have type but no file number)
        if not file_num and item_type:
            current_section = item_type
            continue

        # Extract council district from title, e.g. "(CD 7)" or "(CD 3, CD 7)"
        cd_match = re.search(r"\(CD\s*([^)]+)\)", title)
        council_districts = cd_match.group(1).strip() if cd_match else ""

        items.append({
            "file_number":       file_num,
            "version":           version,
            "item_number":       item_num,
            "type":              item_type,
            "section":           current_section,
            "title":             title,
            "council_districts": council_districts,
            "status":            status,
            "attachments":       attach,
            "attachment_available": avail,
            "action_link_text":  action_lbl,
        })

    return items


# ─── scrape single meeting ───────────────────────────────────────────────────

def scrape_meeting(meeting_id, guid, meeting_date=None, body=None, cookie_path="/tmp/legistar_cookies.txt"):
    """Fetch one meeting's agenda and return structured dict."""
    url = f"{MEET_BASE}?ID={meeting_id}&GUID={guid}&Options=info|&Search="
    content = fetch(url, cookie_path)

    if len(content) < 500:
        return {
            "id": meeting_id,
            "guid": guid,
            "meeting_date": meeting_date,
            "body": body,
            "error": "thin response (possible unpublished agenda)",
            "items": [],
        }

    header = parse_meeting_header(content)
    items = parse_agenda_items(content)

    return {
        "id":              meeting_id,
        "guid":            guid,
        "meeting_date":    header.get("meeting_date", meeting_date),
        "meeting_time":    header.get("meeting_time", ""),
        "meeting_name":    header.get("meeting_name", body or ""),
        "meeting_location": header.get("meeting_location", ""),
        "agenda_status":   header.get("agenda_status", ""),
        "minutes_status":  header.get("minutes_status", ""),
        "agenda_published": header.get("agenda_published", ""),
        "minutes_published": header.get("minutes_published", ""),
        "video_available": header.get("video_available", ""),
        "agenda_note":     header.get("agenda_note", ""),
        "items":           items,
        "item_count":      len(items),
        "source_url":      url,
    }


# ─── batch scrape from meetings JSON ────────────────────────────────────────

def scrape_all(input_path, output_path, min_delay=5, max_meetings=None):
    """
    Read meetings from data/legistar-meetings.json and fetch
    agenda items for each.
    """
    with open(input_path) as f:
        src = json.load(f)

    meetings = src.get("meetings", [])
    if max_meetings:
        meetings = meetings[:max_meetings]

    results = []
    total = len(meetings)

    for i, m in enumerate(meetings):
        sid = m.get("id")
        guid = m.get("guid")
        body = m.get("body", "")
        date = m.get("meeting_date", "")

        print(f"[{i+1}/{total}] {body} {date} (ID={sid})...", end=" ", flush=True, file=sys.stderr)
        result = scrape_meeting(sid, guid, date, body)
        results.append(result)

        if result.get("error"):
            print(f"ERROR: {result['error']}", file=sys.stderr)
        else:
            print(f"OK: {result['item_count']} items", file=sys.stderr)

        time.sleep(min_delay)

    # Save
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    out = {
        "meta": {
            "scraped_at":  datetime.now(timezone.utc).isoformat(),
            "source":      input_path,
            "total_meetings_scrape_attempted": total,
            "meetings_with_items": sum(1 for r in results if r.get("item_count", 0) > 0),
        },
        "meetings": results,
    }
    with open(output_path, "w") as f:
        json.dump(out, f, indent=2, default=str)
    print(f"\nWrote {len(results)} meetings → {output_path}", file=sys.stderr)
    return results


# ─── init session ────────────────────────────────────────────────────────────

def init_session(cookie_path="/tmp/legistar_cookies.txt"):
    """Fetch the calendar page once to establish ASP.NET session cookies."""
    url = f"{CAL_BASE}/Calendar.aspx"
    cmd = [
        "curl", "-s", "--max-time", "20", "-L",
        "-c", cookie_path,
        "-H", f"User-Agent: {HEADERS['User-Agent']}",
        "-H", f"Accept-Language: {HEADERS['Accept-Language']}",
        url,
    ]
    r = subprocess.run(cmd, capture_output=True, text=True, errors="replace", timeout=25)
    return r.stdout


# ─── main ─────────────────────────────────────────────────────────────────────

def main():
    import argparse
    p = argparse.ArgumentParser(description="Fort Worth Legistar agenda item extractor")
    p.add_argument("--input",  default="data/legistar-meetings.json")
    p.add_argument("--output", default="data/legistar-agenda-items.json")
    p.add_argument("--max-meetings", type=int, default=None)
    p.add_argument("--min-delay", type=int, default=5)
    args = p.parse_args()

    repo = Path(__file__).parent.parent.resolve()
    in_path  = repo / args.input
    out_path = repo / args.output

    print("Initializing session...", file=sys.stderr)
    init_session()

    print(f"Scraping agenda items from {in_path}...", file=sys.stderr)
    results = scrape_all(
        str(in_path),
        str(out_path),
        min_delay=args.min_delay,
        max_meetings=args.max_meetings,
    )
    print(f"Done. {sum(r.get('item_count',0) for r in results)} total agenda items scraped.")


if __name__ == "__main__":
    main()
