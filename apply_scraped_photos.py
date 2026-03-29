#!/usr/bin/env python3
"""
Apply scraped photos from Windows server back to the preview sites.
Copies photos and updates HTML to use local photo files instead of Unsplash.
"""
import json
import re
import shutil
from pathlib import Path

OUTPUT_DIR = Path(__file__).parent / "output"
PHOTOS_DIR = Path(__file__).parent / "scraped_photos"  # copied from Windows
RESULTS_FILE = Path(__file__).parent / "scrape_results.json"


def main():
    if not RESULTS_FILE.exists():
        print("ERROR: scrape_results.json not found!")
        print("Copy it from the Windows server first.")
        return

    results = json.load(open(RESULTS_FILE, "r", encoding="utf-8"))
    updated = 0
    skipped = 0

    for slug, data in results.items():
        if not data.get("photos"):
            skipped += 1
            continue

        site_dir = OUTPUT_DIR / slug
        if not site_dir.exists():
            skipped += 1
            continue

        # Copy photos
        src_dir = PHOTOS_DIR / slug
        photos_copied = 0
        for photo_name in data["photos"]:
            src = src_dir / photo_name
            dest = site_dir / photo_name
            if src.exists():
                shutil.copy2(str(src), str(dest))
                photos_copied += 1
            elif dest.exists() and dest.stat().st_size > 1000:
                photos_copied += 1  # already there

        if photos_copied == 0:
            skipped += 1
            continue

        # Update HTML — replace Unsplash URLs with local photos
        index = site_dir / "index.html"
        if not index.exists():
            continue

        html = index.read_text(encoding="utf-8", errors="ignore")
        new_html = html

        # Find all Unsplash URLs
        unsplash_urls = re.findall(r'https://images\.unsplash\.com/[^"\')\\s]+', html)
        unique_unsplash = list(dict.fromkeys(unsplash_urls))

        for i, old_url in enumerate(unique_unsplash[:photos_copied]):
            photo_name = f"photo_{i+1}.jpg"
            new_html = new_html.replace(old_url, photo_name)

        if new_html != html:
            index.write_text(new_html, encoding="utf-8")
            updated += 1
            print(f"  {slug} — {photos_copied} photos applied")
        else:
            skipped += 1

    print(f"\nDone!")
    print(f"  Updated: {updated} sites")
    print(f"  Skipped: {skipped} sites")


if __name__ == "__main__":
    main()
