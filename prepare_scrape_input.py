#!/usr/bin/env python3
"""
Prepare input for the free Google Maps photo scraper.
Reads generic sites (no local photos) and extracts business name + city.
Output: businesses_to_scrape.json — copy this to the Windows server.
"""
import json
import re
from pathlib import Path

OUTPUT_DIR = Path(__file__).parent / "output"
RESULT_FILE = Path(__file__).parent / "businesses_to_scrape.json"


def extract_info(index_html):
    """Extract business name and city from HTML."""
    html = index_html.read_text(encoding="utf-8", errors="ignore")

    # Business name from <title>
    m = re.search(r"<title>([^<]+)</title>", html)
    if not m:
        return None, None
    title = m.group(1).strip()
    for sep in [" | ", " — ", " - "]:
        if sep in title:
            title = title.split(sep)[0].strip()

    # City from first Hebrew "ב..." pattern in the visible text area
    # Look for city in meta description or first 2000 chars
    city = ""
    # Try structured data first (common in generated sites)
    city_match = re.search(r'"addressLocality"\s*:\s*"([^"]+)"', html)
    if city_match:
        city = city_match.group(1).strip()
    else:
        # Fallback: Hebrew "ב+city" pattern
        city_match = re.search(r'ב(תל אביב|ירושלים|חיפה|באר שבע|נתניה|ראשון לציון|פתח תקווה|אשדוד|הרצליה|רמת גן|חולון|בני ברק|רעננה|כפר סבא|מודיעין|אשקלון|נהריה|עכו|קריית שמונה|עפולה|טבריה|קריית ביאליק|קריית מוצקין|קריית אתא|קריית ים|גבעתיים|רמת השרון|הוד השרון|יבנה|לוד|רמלה|אילת|דימונה|ערד|מגדל העמק|נצרת|כרמיאל|צפת|עקרון|נס ציונה|רחובות|פרדס חנה)', html[:3000])
        if city_match:
            city = city_match.group(1).strip()

    return title, city


def main():
    businesses = []
    generic_slugs = json.load(open(Path(__file__).parent / "generic_slugs.json", "r", encoding="utf-8"))

    for slug in generic_slugs:
        index = OUTPUT_DIR / slug / "index.html"
        if not index.exists():
            continue
        name, city = extract_info(index)
        if not name:
            continue
        businesses.append({"slug": slug, "name": name, "city": city or ""})

    json.dump(businesses, open(RESULT_FILE, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"Prepared {len(businesses)} businesses for scraping")
    print(f"Output: {RESULT_FILE}")
    print(f"\nNext steps:")
    print(f"  1. Copy {RESULT_FILE} to Windows server: C:\\scrape_photos\\")
    print(f"  2. Copy scrape_photos_free.py to Windows server: C:\\scrape_photos\\")
    print(f"  3. On Windows: python scrape_photos_free.py --limit 50  (test first)")
    print(f"  4. When done: copy C:\\scrape_photos\\photos\\ back to Mac")
    print(f"  5. Run apply_scraped_photos.py to update the sites")


if __name__ == "__main__":
    main()
