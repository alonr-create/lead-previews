#!/usr/bin/env python3
"""
Free Google Maps photo scraper using Playwright.
Runs on Windows GPU server — zero API cost.

Usage:
  python scrape_photos_free.py [--limit 100] [--delay 5]

Extracts business photos from Google Maps search results page
by scraping the rendered HTML for lh3.googleusercontent.com URLs.
"""
import json
import os
import re
import sys
import time
import random
import urllib.request
import ssl
import asyncio
from pathlib import Path

# Fix Windows console encoding
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# --- Config ---
DELAY_MIN = 3  # seconds between searches (anti-ban)
DELAY_MAX = 7
MAX_PHOTOS = 4  # photos per business
TIMEOUT = 15000  # page load timeout ms

# Paths — will be set based on OS
if sys.platform == "win32":
    BASE_DIR = Path(r"C:\scrape_photos")  # working dir on Windows
else:
    BASE_DIR = Path(__file__).parent

BUSINESSES_FILE = BASE_DIR / "businesses_to_scrape.json"
RESULTS_FILE = BASE_DIR / "scrape_results.json"
PHOTOS_DIR = BASE_DIR / "photos"

ctx = ssl.create_default_context()


def download_photo(url, dest, timeout=15):
    """Download a photo URL to a local file."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            data = resp.read()
            if len(data) < 5000:  # skip tiny images (icons/avatars)
                return False
            with open(dest, "wb") as f:
                f.write(data)
            return True
    except Exception:
        return False


async def scrape_business_photos(page, name, city=""):
    """Search Google Maps for a business and extract photo URLs."""
    query = f"{name} {city} ישראל".strip()
    search_url = f"https://www.google.com/maps/search/{urllib.request.quote(query)}"

    try:
        await page.goto(search_url, wait_until="domcontentloaded", timeout=TIMEOUT)
        # Wait for photos to load
        await page.wait_for_timeout(2000)

        # Try clicking on the first result if it's a list
        try:
            first_result = page.locator('[role="feed"] > div').first
            if await first_result.count() > 0:
                await first_result.click()
                await page.wait_for_timeout(2000)
        except Exception:
            pass

        # Extract all lh3.googleusercontent.com photo URLs from page
        html = await page.content()
        # Pattern: lh3 URLs with size params
        photo_urls = re.findall(
            r'(https://lh[35]\.googleusercontent\.com/[a-zA-Z0-9_\-/=]+)',
            html
        )
        # Deduplicate and filter
        seen = set()
        unique_photos = []
        for url in photo_urls:
            # Normalize: remove size suffix for dedup
            base = re.sub(r'=[swh]\d+.*$', '', url)
            if base not in seen and len(url) > 80:
                seen.add(base)
                # Request full size
                full_url = re.sub(r'=[swh]\d+.*$', '', url) + "=s800"
                unique_photos.append(full_url)

        return unique_photos[:MAX_PHOTOS]

    except Exception as e:
        return []


async def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=0, help="Max businesses to scrape (0=all)")
    parser.add_argument("--delay", type=float, default=5, help="Avg delay between searches")
    parser.add_argument("--headless", action="store_true", default=True)
    parser.add_argument("--no-headless", dest="headless", action="store_false")
    args = parser.parse_args()

    global DELAY_MIN, DELAY_MAX
    DELAY_MIN = max(2, args.delay - 2)
    DELAY_MAX = args.delay + 2

    # Load businesses
    if not BUSINESSES_FILE.exists():
        print(f"ERROR: {BUSINESSES_FILE} not found!")
        print("Run prepare_scrape_input.py first on your Mac.")
        sys.exit(1)

    businesses = json.load(open(BUSINESSES_FILE, "r", encoding="utf-8"))
    total = len(businesses)
    if args.limit > 0:
        businesses = businesses[:args.limit]
    print(f"Loaded {len(businesses)} businesses to scrape (of {total} total)")

    # Create photos dir
    PHOTOS_DIR.mkdir(parents=True, exist_ok=True)

    # Load existing results
    results = {}
    if RESULTS_FILE.exists():
        results = json.load(open(RESULTS_FILE, "r", encoding="utf-8"))
    already_done = len(results)
    print(f"Already scraped: {already_done}")

    # Launch browser
    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=args.headless,
            args=["--disable-blink-features=AutomationControlled"]
        )
        context = await browser.new_context(
            locale="he-IL",
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 900}
        )
        page = await context.new_page()

        # Accept Google consent if it pops up
        try:
            await page.goto("https://www.google.com/maps", timeout=TIMEOUT)
            await page.wait_for_timeout(1500)
            consent = page.locator('button:has-text("Accept"), button:has-text("הסכמה"), button:has-text("קבל")')
            if await consent.count() > 0:
                await consent.first.click()
                await page.wait_for_timeout(1000)
        except Exception:
            pass

        found = 0
        skipped = 0
        failed = 0

        for i, biz in enumerate(businesses):
            slug = biz["slug"]
            name = biz["name"]
            city = biz.get("city", "")

            # Skip if already done
            if slug in results:
                skipped += 1
                continue

            # Scrape
            photos = await scrape_business_photos(page, name, city)

            if photos:
                # Download photos
                biz_dir = PHOTOS_DIR / slug
                biz_dir.mkdir(exist_ok=True)
                downloaded = 0
                photo_files = []
                for pi, url in enumerate(photos):
                    dest = biz_dir / f"photo_{pi+1}.jpg"
                    if download_photo(url, str(dest)):
                        downloaded += 1
                        photo_files.append(f"photo_{pi+1}.jpg")

                results[slug] = {
                    "name": name,
                    "photos": photo_files,
                    "urls": photos,
                    "downloaded": downloaded
                }
                found += 1
                status = f"OK {downloaded} photos"
            else:
                results[slug] = {"name": name, "photos": [], "urls": [], "downloaded": 0}
                failed += 1
                status = "no photos found"

            done = i + 1 - skipped + already_done
            print(f"  [{done}/{total}] {name} — {status}")

            # Save every 10
            if (i + 1) % 10 == 0:
                json.dump(results, open(RESULTS_FILE, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

            # Random delay
            delay = random.uniform(DELAY_MIN, DELAY_MAX)
            await asyncio.sleep(delay)

        await browser.close()

    # Final save
    json.dump(results, open(RESULTS_FILE, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

    print(f"\n{'='*50}")
    print(f"DONE!")
    print(f"  Found photos: {found}")
    print(f"  No photos:    {failed}")
    print(f"  Skipped:      {skipped}")
    print(f"  Results:      {RESULTS_FILE}")
    print(f"  Photos:       {PHOTOS_DIR}")


if __name__ == "__main__":
    asyncio.run(main())
