#!/usr/bin/env python3
"""
Download Google Places photos locally and update HTML files.
Replaces API-dependent URLs with local photo files.
"""
import os
import re
import json
import time
import urllib.request
import ssl
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

OUTPUT_DIR = Path(__file__).parent / "output"
API_KEY = "AIzaSyBHEODU6QPeJmKpy1oZg2vfjUXrvHXgWBQ"
PHOTO_URL_PATTERN = re.compile(r'https://places\.googleapis\.com/v1/places/[^"\')\s]+')

# SSL context for downloads
ctx = ssl.create_default_context()

def find_sites_with_api_photos():
    """Find all sites that reference Google Places API photos."""
    sites = []
    for site_dir in sorted(OUTPUT_DIR.iterdir()):
        index = site_dir / "index.html"
        if not index.exists():
            continue
        html = index.read_text(encoding="utf-8", errors="ignore")
        urls = PHOTO_URL_PATTERN.findall(html)
        if urls:
            # Deduplicate URLs
            unique_urls = list(dict.fromkeys(urls))
            sites.append((site_dir, unique_urls))
    return sites


def download_photo(url, dest_path, retries=2):
    """Download a photo from Google Places API."""
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=15, context=ctx) as resp:
                data = resp.read()
                if len(data) < 1000:
                    # Too small, probably an error response
                    return False
                with open(dest_path, "wb") as f:
                    f.write(data)
                return True
        except Exception as e:
            if attempt < retries:
                time.sleep(1)
            else:
                print(f"  FAIL: {dest_path.name} - {e}")
                return False
    return False


def process_site(site_dir, urls):
    """Download photos for a single site and update its HTML."""
    index = site_dir / "index.html"
    html = index.read_text(encoding="utf-8", errors="ignore")

    replacements = {}
    downloaded = 0

    for i, url in enumerate(urls):
        photo_name = f"photo_{i+1}.jpg"
        photo_path = site_dir / photo_name

        if photo_path.exists() and photo_path.stat().st_size > 1000:
            # Already downloaded
            replacements[url] = photo_name
            downloaded += 1
            continue

        if download_photo(url, photo_path):
            replacements[url] = photo_name
            downloaded += 1
        else:
            # Use a stock fallback
            replacements[url] = "https://images.unsplash.com/photo-1497366216548-37526070297c?w=800&q=80"

    # Replace all URLs in HTML
    new_html = html
    for old_url, new_ref in replacements.items():
        new_html = new_html.replace(old_url, new_ref)

    if new_html != html:
        index.write_text(new_html, encoding="utf-8")

    return site_dir.name, downloaded, len(urls)


def main():
    print("Finding sites with Google Places API photos...")
    sites = find_sites_with_api_photos()
    print(f"Found {len(sites)} sites with API photo URLs")

    if not sites:
        print("Nothing to fix!")
        return

    # Collect all unique URLs first for progress tracking
    all_urls = set()
    for _, urls in sites:
        all_urls.update(urls)
    print(f"Total unique photo URLs: {len(all_urls)}")

    # Process sites
    total_downloaded = 0
    total_photos = 0
    failed_sites = []

    for i, (site_dir, urls) in enumerate(sites):
        name, downloaded, total = process_site(site_dir, urls)
        total_downloaded += downloaded
        total_photos += total

        if downloaded < total:
            failed_sites.append(name)

        if (i + 1) % 50 == 0 or i == len(sites) - 1:
            print(f"  Progress: {i+1}/{len(sites)} sites | {total_downloaded}/{total_photos} photos downloaded")

    print(f"\nDone! {total_downloaded}/{total_photos} photos downloaded across {len(sites)} sites")
    if failed_sites:
        print(f"Sites with failed downloads: {len(failed_sites)}")
        for s in failed_sites[:10]:
            print(f"  - {s}")


if __name__ == "__main__":
    main()
