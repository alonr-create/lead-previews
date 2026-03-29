#!/usr/bin/env python3
"""
Move Monday.com items with personal photos to a specific group.
Reads personal_slugs.json, finds matching items on the board, moves them.
"""

import json
import os
import re
import sys
import requests
import time

# Force unbuffered output
sys.stdout.reconfigure(line_buffering=True) if hasattr(sys.stdout, 'reconfigure') else None

# Config
BOARD_ID = 5092777389
TARGET_GROUP = "group_mm1wy57m"
LINK_COLUMN = "link_mm1s9wtb"
API_URL = "https://api.monday.com/v2"

# Get API token
API_TOKEN = os.environ.get("MONDAY_API_TOKEN") or os.environ.get("MONDAY_API_KEY")
if not API_TOKEN:
    # Read from .env file
    env_path = "/Users/oakhome/קלוד עבודות/alonbot/.env"
    with open(env_path) as f:
        for line in f:
            if line.startswith("MONDAY_API_KEY="):
                API_TOKEN = line.strip().split("=", 1)[1]
                break
            elif line.startswith("MONDAY_API_TOKEN="):
                API_TOKEN = line.strip().split("=", 1)[1]
                break

if not API_TOKEN:
    print("ERROR: No Monday.com API token found")
    exit(1)

print(f"API token loaded ({len(API_TOKEN)} chars)")

headers = {
    "Authorization": API_TOKEN,
    "Content-Type": "application/json",
    "API-Version": "2024-10"
}

# Load personal slugs
script_dir = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(script_dir, "personal_slugs.json")) as f:
    personal_slugs = set(s.lower() for s in json.load(f))

print(f"Loaded {len(personal_slugs)} personal slugs")

def extract_slug(url):
    """Extract slug from preview URL."""
    if not url:
        return None
    # Match lead-previews.vercel.app/SLUG/ or preview.alondev.site/SLUG/
    m = re.search(r'(?:lead-previews\.vercel\.app|preview\.alondev\.site)/([^/]+)', url)
    if m:
        return m.group(1).lower()
    return None

def monday_request(query, variables=None):
    """Make a Monday.com API request with retry."""
    payload = {"query": query}
    if variables:
        payload["variables"] = variables

    for attempt in range(3):
        resp = requests.post(API_URL, json=payload, headers=headers, timeout=30)
        data = resp.json()

        if "errors" in data:
            error_msg = str(data["errors"])
            if "complexity" in error_msg.lower() or "rate" in error_msg.lower():
                wait = 5 * (attempt + 1)
                print(f"  Rate limited, waiting {wait}s...")
                time.sleep(wait)
                continue
            print(f"  API Error: {error_msg}")
            return None

        return data

    print("  Failed after 3 retries")
    return None

# Step 1: Fetch all items with non-empty link column
print("\nFetching items from board...")

# First page
query_first = """
query {
  boards(ids: [%d]) {
    items_page(limit: 500, query_params: {rules: [{column_id: "%s", compare_value: [], operator: is_not_empty}]}) {
      cursor
      items {
        id
        name
        column_values(ids: ["%s"]) {
          text
        }
      }
    }
  }
}
""" % (BOARD_ID, LINK_COLUMN, LINK_COLUMN)

all_items = []
data = monday_request(query_first)
if not data or "data" not in data:
    print(f"ERROR: Failed to fetch first page: {data}")
    exit(1)

page_data = data["data"]["boards"][0]["items_page"]
items = page_data["items"]
cursor = page_data["cursor"]
all_items.extend(items)
print(f"  Page 1: {len(items)} items (cursor: {'yes' if cursor else 'no'})")

# Subsequent pages
page = 2
while cursor:
    query_next = """
    query {
      next_items_page(limit: 500, cursor: "%s") {
        cursor
        items {
          id
          name
          column_values(ids: ["%s"]) {
            text
          }
        }
      }
    }
    """ % (cursor, LINK_COLUMN)

    data = monday_request(query_next)
    if not data or "data" not in data:
        print(f"  ERROR on page {page}, stopping pagination")
        break

    page_data = data["data"]["next_items_page"]
    items = page_data["items"]
    cursor = page_data["cursor"]
    all_items.extend(items)
    print(f"  Page {page}: {len(items)} items (cursor: {'yes' if cursor else 'no'})")
    page += 1
    time.sleep(0.5)  # Be gentle with API

print(f"\nTotal items with links: {len(all_items)}")

# Step 2: Match slugs
matching_ids = []
for item in all_items:
    link_text = item["column_values"][0]["text"] if item["column_values"] else None
    slug = extract_slug(link_text)
    if slug and slug in personal_slugs:
        matching_ids.append(item["id"])
        # Print first few for verification
        if len(matching_ids) <= 5:
            print(f"  Match: {item['name']} -> slug={slug} (id={item['id']})")

print(f"\nMatching items to move: {len(matching_ids)}")

if not matching_ids:
    print("No items to move. Done.")
    exit(0)

# Step 3: Move items in batches of 10
print(f"\nMoving {len(matching_ids)} items to group {TARGET_GROUP}...")
moved = 0
failed = 0

for i in range(0, len(matching_ids), 10):
    batch = matching_ids[i:i+10]

    # Build batch mutation with aliases
    mutations = []
    for j, item_id in enumerate(batch):
        mutations.append(f'm{j}: move_item_to_group(item_id: {item_id}, group_id: "{TARGET_GROUP}") {{ id }}')

    mutation = "mutation {\n  " + "\n  ".join(mutations) + "\n}"

    data = monday_request(mutation)
    if data and "data" in data:
        batch_moved = sum(1 for k in data["data"] if data["data"][k] is not None)
        moved += batch_moved
        if batch_moved < len(batch):
            failed += len(batch) - batch_moved
        print(f"  Batch {i//10 + 1}: moved {batch_moved}/{len(batch)} items (total: {moved})")
    else:
        failed += len(batch)
        print(f"  Batch {i//10 + 1}: FAILED")

    time.sleep(1)  # Rate limit protection

print(f"\nDone! Moved: {moved}, Failed: {failed}, Total matched: {len(matching_ids)}")
