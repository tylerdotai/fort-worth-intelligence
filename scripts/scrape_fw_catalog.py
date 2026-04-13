#!/usr/bin/env python3
"""
Fort Worth Open Data Catalog Scraper.

Uses Playwright to load the JavaScript-rendered ArcGIS Hub catalog page,
wait for the dataset cards to load, then extract all dataset metadata.

Usage:
  python3 scripts/scrape_fw_catalog.py
"""
import json, sys, os, time, re
from pathlib import Path
from playwright.sync_api import sync_playwright

CATALOG_URL = "https://data.fortworthtexas.gov"


def scrape_catalog():
    """Load the browse page, extract all dataset cards."""
    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=True,
            args=['--no-sandbox', '--disable-dev-shm-usage', '--disable-gpu']
        )
        context = browser.new_context(
            user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        print(f"Loading {CATALOG_URL}/browse...", file=sys.stderr)
        page.goto(f"{CATALOG_URL}/browse", timeout=60000, wait_until="domcontentloaded")

        # Wait for the dataset items to appear
        # ArcGIS Hub uses React — items appear in a grid after JS loads
        time.sleep(3)

        # Scroll to trigger lazy loading (items load on scroll)
        last_height = 0
        scroll_count = 0
        while scroll_count < 10:
            page.evaluate("window.scrollBy(0, 800)")
            page.wait_for_timeout(1500)
            new_height = page.evaluate("document.body.scrollHeight")
            if new_height == last_height:
                break
            last_height = new_height
            scroll_count += 1
            print(f"  Scroll {scroll_count}: height={new_height}", file=sys.stderr)

        # Now get all the dataset cards
        # ArcGIS Hub uses data-testid attributes on cards
        cards = page.query_selector_all("[data-testid='card-container']")
        print(f"Found {len(cards)} cards with data-testid", file=sys.stderr)

        # Alternative: look for links with /dataset/ pattern
        dataset_links = []
        all_links = page.query_selector_all("a[href*='/dataset/']")
        seen = set()
        for link in all_links:
            href = link.get_attribute("href") or ""
            text = link.inner_text().strip()[:100]
            if href and href not in seen:
                seen.add(href)
                # Extract slug from URL
                slug = href.split('/dataset/')[-1].split('?')[0]
                dataset_links.append({
                    "slug": slug,
                    "url": href,
                    "title": text,
                })

        print(f"Found {len(dataset_links)} unique dataset links", file=sys.stderr)

        # Now try to get more metadata for each dataset
        datasets = []
        for ds in dataset_links:
            slug = ds["slug"]
            # Try to access the dataset page to find the feature service URL
            detail_url = f"{CATALOG_URL}/dataset/{slug}"
            # Just store what we have for now
            datasets.append({
                "slug": slug,
                "url": f"{CATALOG_URL}/dataset/{slug}",
                "title": ds["title"],
            })

        browser.close()
        return datasets


def get_feature_service_urls():
    """
    For each dataset, try to find the ArcGIS feature service or API endpoint.
    Uses the ArcGIS Hub API.
    """
    pass


def main():
    datasets = scrape_catalog()

    out_path = Path(__file__).parent.parent / "data" / "raw" / "fw-open-data-catalog.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    result = {
        "meta": {
            "source": f"{CATALOG_URL}/browse",
            "scraped_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "method": "Playwright DOM extraction",
        },
        "datasets": datasets,
    }

    with open(out_path, "w") as f:
        json.dump(result, f, indent=2)

    print(f"Wrote {len(datasets)} datasets → {out_path}", file=sys.stderr)
    print("\nDatasets found:")
    for ds in datasets:
        print(f"  {ds['title'][:70]}")


if __name__ == "__main__":
    main()
