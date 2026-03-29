#!/usr/bin/env python3
"""Search Google Places for 100 sites that currently have generic photos."""
import json
import os
import re
import ssl
import time
import urllib.request
from pathlib import Path

API_KEY = "AIzaSyBHEODU6QPeJmKpy1oZg2vfjUXrvHXgWBQ"
OUTPUT_DIR = Path(__file__).parent / "output"
CACHE_PATH = Path(__file__).parent / "places_cache.json"
ctx = ssl.create_default_context()


def http_post_json(url, body, headers):
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=15, context=ctx) as resp:
        return json.loads(resp.read().decode("utf-8"))


def http_get_json(url, headers):
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=15, context=ctx) as resp:
        return json.loads(resp.read().decode("utf-8"))


def download_photo(url, dest):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15, context=ctx) as resp:
            data = resp.read()
            if len(data) < 1000:
                return False
            with open(dest, "wb") as f:
                f.write(data)
            return True
    except Exception:
        return False


def extract_business_name(index_html):
    """Extract business name from HTML title or h1."""
    html = index_html.read_text(encoding="utf-8", errors="ignore")
    # Try <title>
    m = re.search(r"<title>([^<]+)</title>", html)
    if m:
        title = m.group(1).strip()
        # Remove common suffixes
        for sep in [" | ", " — ", " - "]:
            if sep in title:
                title = title.split(sep)[0].strip()
        return title, html
    return None, html


def find_generic_sites():
    """Find sites with only Unsplash/stock photos (no local photos)."""
    sites = []
    for site_dir in sorted(OUTPUT_DIR.iterdir()):
        if not site_dir.is_dir():
            continue
        index = site_dir / "index.html"
        if not index.exists():
            continue
        # Skip if already has local photos
        if list(site_dir.glob("photo_*.jpg")):
            continue
        sites.append(site_dir)
    return sites


def main():
    print("Finding generic sites...")
    generic_sites = find_generic_sites()
    print(f"Found {len(generic_sites)} generic sites")

    cache = json.load(open(CACHE_PATH, "r", encoding="utf-8")) if CACHE_PATH.exists() else {}

    results = {"found_photos": [], "no_photos": [], "not_found": []}
    processed = 0

    for site_dir in generic_sites[:100]:
        index = site_dir / "index.html"
        biz_name, html = extract_business_name(index)
        if not biz_name:
            continue

        # Extract city from HTML
        city_match = re.search(r'ב([א-ת\s]{2,20})', html[:3000])
        city = city_match.group(1).strip() if city_match else ""

        cache_key = f"{biz_name}|{city}"
        slug = site_dir.name

        # Check if already in cache with photos
        if cache_key in cache and cache[cache_key].get("photo_urls"):
            photo_urls = cache[cache_key]["photo_urls"]
            # Download photos
            downloaded = 0
            for i, url in enumerate(photo_urls[:4]):
                dest = site_dir / f"photo_{i+1}.jpg"
                if download_photo(url, dest):
                    downloaded += 1
            if downloaded > 0:
                # Update HTML
                new_html = html
                unsplash_urls = re.findall(r'https://images\.unsplash\.com/[^"\')\s]+', html)
                unique_unsplash = list(dict.fromkeys(unsplash_urls))
                for i, old_url in enumerate(unique_unsplash[:downloaded]):
                    new_html = new_html.replace(old_url, f"photo_{i+1}.jpg")
                if new_html != html:
                    index.write_text(new_html, encoding="utf-8")
                results["found_photos"].append({"slug": slug, "name": biz_name, "photos": downloaded})
                processed += 1
                print(f"  [{processed}/100] {biz_name} — {downloaded} photos (from cache)")
                continue

        # Search Google Places
        try:
            search_url = "https://places.googleapis.com/v1/places:searchText"
            headers = {
                "X-Goog-Api-Key": API_KEY,
                "X-Goog-FieldMask": "places.name,places.photos",
            }
            body = {"textQuery": f"{biz_name} {city} israel", "languageCode": "he"}
            data = http_post_json(search_url, body, headers)
            places = data.get("places", [])
            time.sleep(0.3)
        except Exception as e:
            results["not_found"].append({"slug": slug, "name": biz_name, "error": str(e)})
            processed += 1
            print(f"  [{processed}/100] {biz_name} — ERROR: {e}")
            continue

        if not places:
            results["not_found"].append({"slug": slug, "name": biz_name})
            processed += 1
            print(f"  [{processed}/100] {biz_name} — not found on Google")
            continue

        place = places[0]
        photos = place.get("photos", [])

        if not photos:
            results["no_photos"].append({"slug": slug, "name": biz_name})
            processed += 1
            print(f"  [{processed}/100] {biz_name} — found but no photos")
            continue

        # Download photos
        photo_urls = []
        downloaded = 0
        for i, p in enumerate(photos[:4]):
            pname = p["name"]
            url = f"https://places.googleapis.com/v1/{pname}/media?maxWidthPx=800&key={API_KEY}"
            photo_urls.append(url)
            dest = site_dir / f"photo_{i+1}.jpg"
            if download_photo(url, dest):
                downloaded += 1
            time.sleep(0.1)

        if downloaded > 0:
            # Update HTML — replace unsplash URLs with local photos
            new_html = html
            unsplash_urls = re.findall(r'https://images\.unsplash\.com/[^"\')\s]+', html)
            unique_unsplash = list(dict.fromkeys(unsplash_urls))
            for i, old_url in enumerate(unique_unsplash[:downloaded]):
                new_html = new_html.replace(old_url, f"photo_{i+1}.jpg")
            if new_html != html:
                index.write_text(new_html, encoding="utf-8")
            results["found_photos"].append({"slug": slug, "name": biz_name, "photos": downloaded})
        else:
            results["no_photos"].append({"slug": slug, "name": biz_name})

        # Update cache
        cache[cache_key] = cache.get(cache_key, {})
        cache[cache_key]["photo_urls"] = photo_urls
        cache[cache_key]["place_id"] = place["name"]

        processed += 1
        print(f"  [{processed}/100] {biz_name} — {downloaded} photos downloaded")

        if processed >= 100:
            break

    # Save cache
    json.dump(cache, open(CACHE_PATH, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

    # Report
    print(f"\n{'='*50}")
    print(f"RESULTS:")
    print(f"  Found + downloaded photos: {len(results['found_photos'])}")
    print(f"  Found but no photos:       {len(results['no_photos'])}")
    print(f"  Not found on Google:       {len(results['not_found'])}")

    # Save results for comparison page
    json.dump(results, open(Path(__file__).parent / "search_100_results.json", "w", encoding="utf-8"), ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
