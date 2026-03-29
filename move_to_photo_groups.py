#!/usr/bin/env python3
"""
Move leads to Monday.com groups based on photo count.
Groups: 4+ photos, 3, 2, 1 photo.
"""
import json
import re
import time
import urllib.request
from pathlib import Path

API_KEY = "eyJhbGciOiJIUzI1NiJ9.eyJ0aWQiOjYzMDU1OTI2MywiYWFpIjoxMSwidWlkIjozNjk2NjE5OSwiaWFkIjoiMjAyNi0wMy0wOVQxMjozOToyMy4wMDBaIiwicGVyIjoibWU6d3JpdGUiLCJhY3RpZCI6MTQzMTIzOTMsInJnbiI6ImV1YzEifQ.AjRtzOrFukZ_uS_jxn6e4Gd2NS-m-7evgkZAni4AtCc"
BOARD_ID = 5092777389
API_URL = "https://api.monday.com/v2"

GROUPS = {
    4: "group_mm1xbpey",   # 4 תמונות מגוגל (also 5, 6)
    3: "group_mm1xe4hz",   # 3 תמונות מגוגל
    2: "group_mm1x9es4",   # 2 תמונות מגוגל
    1: "group_mm1xzkyr",   # תמונה אחת מגוגל
}

# Groups we should move items FROM (don't move items already in sales pipeline groups)
SKIP_GROUPS = {
    "group_mm1s9vs5",   # נוצר קשר
    "group_mm1sbstm",   # מעוניינים
    "group_mm1te35h",   # נקבעה פגישה
    "group_mm1v1peh",   # ניסיון קביעה מחדש
    "group_mm1vthnb",   # עבר פגישה
    "group_mm1smn4q",   # סגירות
    "group_mm1s4xpc",   # לא רלוונטי
}


def monday_api(query, variables=None):
    data = json.dumps({"query": query, "variables": variables or {}}).encode()
    req = urllib.request.Request(API_URL, data=data, headers={
        "Authorization": API_KEY,
        "Content-Type": "application/json",
        "API-Version": "2025-04",
    })
    with urllib.request.urlopen(req) as resp:
        result = json.loads(resp.read())
    if "errors" in result:
        print(f"API Error: {result['errors']}")
    return result.get("data", {})


def extract_slug(link_value):
    if not link_value:
        return None
    try:
        obj = json.loads(link_value)
        url = obj.get("url", "")
    except (json.JSONDecodeError, TypeError):
        url = str(link_value)
    # Extract slug from URL like https://preview.alondev.site/SLUG/ or .../lead-previews.vercel.app/SLUG/
    m = re.search(r'(?:preview\.alondev\.site|lead-previews\.vercel\.app|output-[^/]+\.vercel\.app)/([^/?]+)', url)
    if m:
        return m.group(1)
    return None


def fetch_all_items():
    """Fetch all items with their group and preview link."""
    items = []
    cursor = None
    page = 0
    while True:
        page += 1
        if cursor:
            query = f'''query {{ next_items_page(limit: 500, cursor: "{cursor}") {{ cursor items {{ id name group {{ id }} column_values(ids: ["link_mm1s9wtb"]) {{ value }} }} }} }}'''
        else:
            query = f'''query {{ boards(ids: {BOARD_ID}) {{ items_page(limit: 500) {{ cursor items {{ id name group {{ id }} column_values(ids: ["link_mm1s9wtb"]) {{ value }} }} }} }} }}'''

        data = monday_api(query)

        if cursor:
            page_data = data.get("next_items_page", {})
        else:
            boards = data.get("boards", [])
            page_data = boards[0].get("items_page", {}) if boards else {}

        page_items = page_data.get("items", [])
        items.extend(page_items)
        cursor = page_data.get("cursor")
        print(f"  Page {page}: {len(page_items)} items (total: {len(items)})")

        if not cursor or not page_items:
            break
        time.sleep(0.3)

    return items


def move_items_batch(item_ids, group_id):
    """Move items to group in batches of 50."""
    for i in range(0, len(item_ids), 50):
        batch = item_ids[i:i+50]
        mutations = []
        for j, item_id in enumerate(batch):
            mutations.append(f'm{j}: move_item_to_group(item_id: {item_id}, group_id: "{group_id}") {{ id }}')
        query = "mutation { " + " ".join(mutations) + " }"
        monday_api(query)
        if i + 50 < len(item_ids):
            time.sleep(0.5)


def main():
    # Load photo count mapping
    print("Loading photo count data...")
    results_file = Path(__file__).parent / "scrape_results.json"
    results = json.load(open(results_file, encoding="utf-8"))
    slug_photos = {}
    for slug, data in results.items():
        slug_photos[slug] = len(data.get("photos", []))

    # Also check output dirs
    output_dir = Path(__file__).parent / "output"
    for d in output_dir.iterdir():
        if not d.is_dir() or d.name.startswith('.'):
            continue
        if d.name not in slug_photos or slug_photos[d.name] == 0:
            count = len([f for f in d.iterdir() if f.name.startswith('photo_') and f.name.endswith('.jpg') and f.stat().st_size > 1000])
            if count > 0:
                slug_photos[d.name] = count

    print(f"Slug → photo mappings: {len(slug_photos)}")

    # Fetch all Monday.com items
    print("\nFetching all items from Monday.com...")
    items = fetch_all_items()
    print(f"Total items fetched: {len(items)}")

    # Match and categorize
    to_move = {4: [], 3: [], 2: [], 1: []}
    matched = 0
    skipped_pipeline = 0
    no_link = 0
    no_match = 0
    already_in_group = 0

    target_group_ids = set(GROUPS.values())

    for item in items:
        group_id = item["group"]["id"]

        # Skip items already in photo groups
        if group_id in target_group_ids:
            already_in_group += 1
            continue

        # Skip items in sales pipeline
        if group_id in SKIP_GROUPS:
            skipped_pipeline += 1
            continue

        link_val = item["column_values"][0]["value"] if item["column_values"] else None
        slug = extract_slug(link_val)

        if not slug:
            no_link += 1
            continue

        photo_count = slug_photos.get(slug, 0)
        if photo_count == 0:
            no_match += 1
            continue

        # Map to group (4+ → group 4)
        group_key = min(photo_count, 4)
        to_move[group_key].append(int(item["id"]))
        matched += 1

    print(f"\n--- Results ---")
    print(f"Matched: {matched}")
    print(f"Skipped (sales pipeline): {skipped_pipeline}")
    print(f"Already in photo groups: {already_in_group}")
    print(f"No preview link: {no_link}")
    print(f"No photo match: {no_match}")
    for k in [4, 3, 2, 1]:
        print(f"  → {k} photos: {len(to_move[k])} items")

    # Move items
    for photo_count in [4, 3, 2, 1]:
        ids = to_move[photo_count]
        if not ids:
            continue
        group_id = GROUPS[photo_count]
        print(f"\nMoving {len(ids)} items to '{photo_count} תמונות' group...")
        move_items_batch(ids, group_id)
        print(f"  Done!")

    print("\nAll done!")


if __name__ == "__main__":
    main()
