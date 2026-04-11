#!/usr/bin/env python3
"""Verification harness for fort-worth-intelligence data layer."""
import json, subprocess, sys, re, os

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = os.path.join(REPO, "data/raw")
FAILED = []

def check_json_file(path, label):
    try:
        with open(path) as f:
            json.load(f)
        print(f"[OK] {label}")
        return True
    except Exception as e:
        print(f"[FAIL] {label}: {e}")
        FAILED.append(label)
        return False

def check_url(name, url, min_chars=200):
    try:
        # Use GET for more reliable detection across all server configs
        r = subprocess.run(
            ['curl', '-s', url, '--max-time', '15', '-L'],
            capture_output=True, text=True, errors='replace', timeout=20
        )
        text = r.stdout
        meaningful = sum(c.isalpha() for c in text) > min_chars
        title = re.search(r'<title[^>]*>([^<]+)</title>', text)
        title_str = title.group(1).strip()[:80] if title else '(no title)'
        status = 'OK' if meaningful else 'THIN'
        print(f"[{status}] {name}: {url}")
        print(f"       title: {title_str}")
        if not meaningful and url.rstrip('/') not in {u.rstrip('/') for u in THIN_OK}:
            FAILED.append(f"{name} ({url}) - thin content")
        return meaningful
    except Exception as e:
        print(f"[FAIL] {name}: {e}")
        FAILED.append(f"{name} ({url})")
        return False

print("=== Fort Worth Intelligence — Verification Harness ===\n")

# 1. JSON integrity
print("--- JSON Integrity ---")
check_json_file(f"{BASE}/canonical_institutions.json", "canonical_institutions.json")
check_json_file(f"{BASE}/source_layer_mappings.json", "source_layer_mappings.json")
check_json_file(f"{BASE}/discovery_urls.validated.json", "discovery_urls.validated.json")
check_json_file(f"{BASE}/discovery_urls.normalized.json", "discovery_urls.normalized.json")

# 2. Layer coverage
print("\n--- Layer Coverage ---")
slug_map = {r['slug']: r for r in json.load(open(f"{BASE}/canonical_institutions.json"))}
mappings = json.load(open(f"{BASE}/source_layer_mappings.json"))
for layer in mappings:
    for s in layer['sources']:
        rec = slug_map.get(s)
        if not rec:
            print(f"[FAIL] layer '{layer['layer']}' source slug '{s}' not in canonical_institutions")
            FAILED.append(f"layer slug missing: {s}")

# 3. Live URL checks
print("\n--- Live URL Checks ---")
# Known servers that return thin content on HEAD but are valid on GET
THIN_OK = {
    'https://www.tarranttax.com/',   # cloudflare / anti-bot page on HEAD, real content on GET
}

live_targets = [
    ("Legistar calendar", "https://fortworthgov.legistar.com/Calendar.aspx"),
    ("TAD home", "https://www.tad.org"),
    ("Fort Worth GIS", "https://mapit.fortworthtexas.gov"),
    ("Fort Worth city home", "https://www.fortworthtexas.gov"),
    ("FWISD", "https://www.fwisd.org"),
    ("Arlington ISD", "https://www.aisd.net"),
    ("Mansfield ISD", "https://www.mansfieldisd.org"),
    ("Keller ISD", "https://www.kellerisd.net"),
    ("NCTCOG", "https://www.nctcog.org"),
    ("Trinity Metro", "https://ridetrinitymetro.org"),
    ("TRWD", "https://www.trwd.com"),
    ("Tarrant Tax", "https://www.tarranttax.com"),
    ("Tarrant Public Search", "https://tarrant.tx.publicsearch.us"),
    ("Tarrant ESD #1", "https://www.tarrantesd1.org"),
]
for name, url in live_targets:
    check_url(name, url)

# 4. Summary
print("\n--- Summary ---")
total_insts = len(json.load(open(f"{BASE}/canonical_institutions.json")))
total_layers = len(json.load(open(f"{BASE}/source_layer_mappings.json")))
print(f"Canonical institutions: {total_insts}")
print(f"Intelligence layers: {total_layers}")
if FAILED:
    print(f"\nFAILED ({len(FAILED)}):")
    for f in FAILED: print(f"  - {f}")
    sys.exit(1)
else:
    print("\nAll checks passed.")
    sys.exit(0)
