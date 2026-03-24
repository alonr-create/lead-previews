#!/usr/bin/env python3
"""
Lead Preview Generator
Generates personalized website previews for business leads without websites.

Google Places API Setup:
  1. Go to https://console.cloud.google.com/
  2. Enable "Places API" (new) or "Places API" (legacy)
  3. Create an API key under Credentials
  4. Set env var: export GOOGLE_PLACES_API_KEY="your-key-here"
  The free tier allows ~$200/month credit which covers thousands of requests.
"""

import csv
import json
import os
import re
import time
import unicodedata
from urllib.parse import quote

try:
    import requests
except ImportError:
    import urllib.request
    import urllib.error
    requests = None  # fallback to urllib

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATES_DIR = os.path.join(BASE_DIR, 'templates')
OUTPUT_DIR = os.path.join(BASE_DIR, 'output')
CSV_PATH = '/Users/oakhome/קלוד עבודות/leads_alon_dev.csv'
CACHE_PATH = os.path.join(BASE_DIR, 'places_cache.json')

GOOGLE_PLACES_API_KEY = os.environ.get('GOOGLE_PLACES_API_KEY', 'AIzaSyBHEODU6QPeJmKpy1oZg2vfjUXrvHXgWBQ')

CATEGORY_MAP = {
    'מסעדה': 'restaurant',
    'מכון יופי': 'beauty',
}

# Rate limiting delay between API calls (seconds)
API_DELAY = 0.5


# ---------------------------------------------------------------------------
# HTTP helper (works with or without requests library)
# ---------------------------------------------------------------------------

def http_get_json(url, headers=None):
    """Fetch JSON from a URL. Works with requests lib or stdlib urllib."""
    if requests:
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        return resp.json()
    else:
        req = urllib.request.Request(url, headers=headers or {})
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode('utf-8'))


def http_post_json(url, body, headers=None):
    """POST JSON to a URL. Works with requests lib or stdlib urllib."""
    if requests:
        resp = requests.post(url, json=body, headers=headers, timeout=10)
        resp.raise_for_status()
        return resp.json()
    else:
        data = json.dumps(body).encode('utf-8')
        req = urllib.request.Request(url, data=data, headers=headers or {}, method='POST')
        req.add_header('Content-Type', 'application/json')
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode('utf-8'))


# ---------------------------------------------------------------------------
# Google Places API helpers
# ---------------------------------------------------------------------------

def load_places_cache():
    """Load cached Places API results from disk."""
    if os.path.exists(CACHE_PATH):
        with open(CACHE_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}


def save_places_cache(cache):
    """Save Places API results cache to disk."""
    with open(CACHE_PATH, 'w', encoding='utf-8') as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)


def places_text_search(name, city):
    """Search for a business using Google Places API (v1) Text Search.
    Returns the resource name (e.g. 'places/ChIJ...') or None."""
    url = "https://places.googleapis.com/v1/places:searchText"
    headers = {
        'X-Goog-Api-Key': GOOGLE_PLACES_API_KEY,
        'X-Goog-FieldMask': 'places.name',
    }
    body = {
        'textQuery': f"{name} {city} israel",
        'languageCode': 'he',
    }
    try:
        data = http_post_json(url, body, headers=headers)
        places = data.get('places', [])
        if places:
            return places[0]['name']  # e.g. "places/ChIJ..."
    except Exception:
        pass
    return None


def places_get_details(resource_name):
    """Fetch Place Details using Google Places API (v1).
    resource_name is e.g. 'places/ChIJ...'.
    Returns dict with photos, rating, userRatingCount, regularOpeningHours, formattedAddress."""
    url = f"https://places.googleapis.com/v1/{resource_name}?languageCode=he"
    headers = {
        'X-Goog-Api-Key': GOOGLE_PLACES_API_KEY,
        'X-Goog-FieldMask': 'photos,rating,userRatingCount,regularOpeningHours,formattedAddress,reviews,websiteUri',
    }
    try:
        data = http_get_json(url, headers=headers)
        if data:
            return data
    except Exception:
        pass
    return None


def build_photo_url(photo_name, max_width=800):
    """Build a Google Places (v1) photo URL from a photo resource name.
    photo_name is e.g. 'places/ChIJ.../photos/AelY...'."""
    return (
        f"https://places.googleapis.com/v1/{photo_name}/media"
        f"?maxWidthPx={max_width}&key={GOOGLE_PLACES_API_KEY}"
    )


def enrich_lead(lead, cache):
    """Enrich a single lead with Google Places data.
    Returns a dict of enrichment data (may be empty if API fails).
    Uses and updates the cache dict in-place."""
    name = lead['name']
    city = lead['city']
    cache_key = f"{name}|{city}"

    # Check cache first
    if cache_key in cache:
        return cache[cache_key]

    enrichment = {}

    if not GOOGLE_PLACES_API_KEY:
        return enrichment

    # Step 1: Text Search to find resource name (e.g. "places/ChIJ...")
    resource_name = places_text_search(name, city)
    time.sleep(API_DELAY)

    if not resource_name:
        cache[cache_key] = enrichment
        return enrichment

    # Step 2: Get details
    details = places_get_details(resource_name)
    time.sleep(API_DELAY)

    if not details:
        cache[cache_key] = enrichment
        return enrichment

    # Extract data (new API v1 uses camelCase fields)
    enrichment['place_id'] = resource_name
    enrichment['address'] = details.get('formattedAddress', '')
    enrichment['rating'] = details.get('rating', '')
    enrichment['reviews_count'] = details.get('userRatingCount', '')

    # Photos (up to 6) — new API uses "name" field per photo
    photos = details.get('photos', [])
    photo_names = [p['name'] for p in photos[:6]]
    enrichment['photo_refs'] = photo_names
    enrichment['photo_urls'] = [build_photo_url(pn) for pn in photo_names]

    # Opening hours (new API: regularOpeningHours)
    hours = details.get('regularOpeningHours', {})
    enrichment['hours_weekday_text'] = hours.get('weekdayDescriptions', [])
    enrichment['hours_periods'] = hours.get('periods', [])

    # Reviews (up to 3 best ones)
    reviews = details.get('reviews', [])
    enrichment['reviews'] = []
    for rev in reviews[:3]:
        enrichment['reviews'].append({
            'text': rev.get('text', {}).get('text', ''),
            'rating': rev.get('rating', 5),
            'author': rev.get('authorAttribution', {}).get('displayName', ''),
            'time': rev.get('relativePublishTimeDescription', ''),
        })

    # Save to cache
    cache[cache_key] = enrichment
    return enrichment


# ---------------------------------------------------------------------------
# Existing helpers
# ---------------------------------------------------------------------------

def slugify(text):
    """Create a URL-safe slug from Hebrew or English text."""
    text = text.strip()
    # Replace spaces and special chars with hyphens
    text = re.sub(r'[\s/\\:;,!?@#$%^&*()+=\[\]{}|<>\'\"]+', '-', text)
    # Remove leading/trailing hyphens
    text = text.strip('-')
    # Collapse multiple hyphens
    text = re.sub(r'-+', '-', text)
    # If empty after cleanup, use a fallback
    if not text:
        text = 'business'
    return text


def clean_phone(phone):
    """Remove dashes, spaces, parentheses from phone number."""
    cleaned = re.sub(r'[\s\-\(\)]+', '', phone)
    # Remove leading 0 for international format used in wa.me links
    if cleaned.startswith('0'):
        cleaned = cleaned[1:]
    return cleaned


def load_template(name):
    path = os.path.join(TEMPLATES_DIR, f'{name}.html')
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()


def load_banner():
    path = os.path.join(TEMPLATES_DIR, 'banner.html')
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()


def build_map_embed(name, city):
    """Build Google Maps embed URL (free, no API key needed)."""
    query = quote(f"{name} {city} ישראל")
    return f'https://www.google.com/maps/embed/v1/place?key=AIzaSyBFw0Qbyq9zTFTd-tUY6dZWTgaQzuU17R8&q={query}&language=he'


def build_map_section(name, city, address):
    """Build a real Google Maps section for the business."""
    query = quote(f"{name} {city}")
    maps_link = f"https://www.google.com/maps/search/?api=1&query={query}"
    return f'''
<!-- Map -->
<section style="padding:0">
  <div style="max-width:1100px;margin:0 auto;padding:0 24px 60px">
    <div style="border-radius:20px;overflow:hidden;box-shadow:0 8px 30px rgba(0,0,0,0.08);border:1px solid rgba(0,0,0,0.06)">
      <iframe
        width="100%"
        height="350"
        style="border:0;display:block"
        loading="lazy"
        referrerpolicy="no-referrer-when-downgrade"
        src="https://maps.google.com/maps?q={query}+ישראל&output=embed&hl=he&z=16">
      </iframe>
      <div style="padding:20px;background:#fff;text-align:center">
        <p style="color:#3D3D3D;font-size:1rem;margin-bottom:12px">{address if address else f'{name}, {city}'}</p>
        <a href="{maps_link}" target="_blank" style="color:#4285f4;text-decoration:none;font-weight:600;font-size:14px">פתח בגוגל מפות</a>
      </div>
    </div>
  </div>
</section>'''


# ---------------------------------------------------------------------------
# Unsplash fallback photos by category
# ---------------------------------------------------------------------------

UNSPLASH_FALLBACKS = {
    'מסעדה': [
        'https://images.unsplash.com/photo-1517248135467-4c7edcad34c4?w=800',
        'https://images.unsplash.com/photo-1555396273-367ea4eb4db5?w=800',
        'https://images.unsplash.com/photo-1414235077428-338989a2e8c0?w=800',
        'https://images.unsplash.com/photo-1552566626-52f8b828add9?w=800',
    ],
    'מכון יופי': [
        'https://images.unsplash.com/photo-1560066984-138dadb4c035?w=800',
        'https://images.unsplash.com/photo-1522337360788-8b13dee7a37e?w=800',
        'https://images.unsplash.com/photo-1487412912498-0447578fcca8?w=800',
        'https://images.unsplash.com/photo-1519494026892-80bbd2d6fd0d?w=800',
    ],
}


def build_reviews_section(reviews):
    """Build an HTML section with real Google reviews."""
    cards = ''
    for rev in reviews:
        stars = ''.join(['<span style="color:#F5A623">&#9733;</span>' for _ in range(rev.get('rating', 5))])
        stars += ''.join(['<span style="color:#ddd">&#9733;</span>' for _ in range(5 - rev.get('rating', 5))])
        text = rev.get('text', '')[:200]
        if len(rev.get('text', '')) > 200:
            text += '...'
        author = rev.get('author', 'לקוח')
        initials = author[0] if author else '?'
        time_ago = rev.get('time', '')
        cards += f'''
      <div style="background:#fff;border-radius:16px;padding:24px;box-shadow:0 4px 20px rgba(0,0,0,0.06);border:1px solid rgba(0,0,0,0.04);flex:1;min-width:280px">
        <div style="display:flex;align-items:center;gap:12px;margin-bottom:12px">
          <div style="width:44px;height:44px;border-radius:50%;background:linear-gradient(135deg,#667eea,#764ba2);color:#fff;display:flex;align-items:center;justify-content:center;font-weight:700;font-size:18px">{initials}</div>
          <div>
            <div style="font-weight:600;font-size:15px;color:#1a1a1a">{author}</div>
            <div style="font-size:12px;color:#999">{time_ago}</div>
          </div>
        </div>
        <div style="margin-bottom:8px;font-size:16px">{stars}</div>
        <p style="color:#555;font-size:14px;line-height:1.7;margin:0">"{text}"</p>
      </div>'''

    return f'''
<!-- Real Google Reviews -->
<section style="padding:60px 24px;background:#FAFAF8">
  <div style="max-width:1100px;margin:0 auto">
    <h2 style="text-align:center;font-size:1.8rem;font-weight:700;color:#1a1a1a;margin-bottom:8px">מה הלקוחות אומרים</h2>
    <p style="text-align:center;color:#888;margin-bottom:40px;font-size:15px">ביקורות אמיתיות מגוגל</p>
    <div style="display:flex;gap:20px;flex-wrap:wrap;justify-content:center">{cards}
    </div>
  </div>
</section>'''


def generate_page(template_html, banner_html, lead, enrichment=None):
    """Replace template variables with lead data and inject banner + map."""
    if enrichment is None:
        enrichment = {}

    phone_clean = clean_phone(lead['phone'])
    # Prefer Google address over CSV address
    address = enrichment.get('address') or lead.get('address', '')
    category = lead.get('category', '')

    # Build map section
    map_html = build_map_section(lead['name'], lead['city'], address)

    html = template_html.replace('{{BUSINESS_NAME}}', lead['name'])
    html = html.replace('{{CITY}}', lead['city'])
    html = html.replace('{{PHONE}}', lead['phone'])
    html = html.replace('{{PHONE_CLEAN}}', phone_clean)
    html = html.replace('{{BANNER}}', banner_html)

    # New enrichment variables
    html = html.replace('{{ADDRESS}}', address)

    rating = enrichment.get('rating', '')
    html = html.replace('{{RATING}}', str(rating) if rating else '')

    reviews_count = enrichment.get('reviews_count', '')
    html = html.replace('{{REVIEWS_COUNT}}', str(reviews_count) if reviews_count else '')

    # Photos: use Google Places if available, otherwise Unsplash fallbacks
    photo_urls = enrichment.get('photo_urls', [])
    fallbacks = UNSPLASH_FALLBACKS.get(category, UNSPLASH_FALLBACKS.get('מסעדה', []))
    for i in range(1, 7):
        placeholder = f'{{{{PHOTO_{i}}}}}'
        if i <= len(photo_urls):
            html = html.replace(placeholder, photo_urls[i - 1])
        elif i <= len(fallbacks):
            html = html.replace(placeholder, fallbacks[i - 1])
        else:
            html = html.replace(placeholder, '')

    # Opening hours as JSON for JS parsing
    hours_data = {
        'weekday_text': enrichment.get('hours_weekday_text', []),
        'periods': enrichment.get('hours_periods', []),
    }
    html = html.replace('{{HOURS_JSON}}', json.dumps(hours_data, ensure_ascii=False))

    # Reviews — build real reviews HTML section
    reviews = enrichment.get('reviews', [])
    if reviews:
        reviews_html = build_reviews_section(reviews)
    else:
        reviews_html = ''
    html = html.replace('{{REVIEWS_SECTION}}', reviews_html)

    # Inject map before footer
    html = html.replace('<!-- Footer -->', f'{map_html}\n\n<!-- Footer -->')

    # Tracking pixel — fires when someone opens the page
    tracking_pixel = (
        f'<script>'
        f'(function(){{'
        f'var p="{phone_clean}",n=encodeURIComponent("{lead["name"]}");'
        f'var img=new Image();'
        f'img.src="https://output-seven-black.vercel.app/api/track?phone="+p+"&name="+n+"&t="+Date.now();'
        f'}})()'
        f'</script>'
    )

    # Facebook Pixel for retargeting
    fb_pixel_id = os.environ.get('FB_PIXEL_ID', '')
    fb_pixel = ''
    if fb_pixel_id:
        fb_pixel = (
            f"<!-- Facebook Pixel -->"
            f"<script>"
            f"!function(f,b,e,v,n,t,s){{if(f.fbq)return;n=f.fbq=function(){{n.callMethod?"
            f"n.callMethod.apply(n,arguments):n.queue.push(arguments)}};if(!f._fbq)f._fbq=n;"
            f"n.push=n;n.loaded=!0;n.version='2.0';n.queue=[];t=b.createElement(e);t.async=!0;"
            f"t.src=v;s=b.getElementsByTagName(e)[0];s.parentNode.insertBefore(t,s)}}"
            f"(window,document,'script','https://connect.facebook.net/en_US/fbevents.js');"
            f"fbq('init','{fb_pixel_id}');"
            f"fbq('track','PageView');"
            f"fbq('track','ViewContent',{{content_name:'{lead['name']}',content_category:'{lead.get('category','')}'}});"
            f"</script>"
            f"<noscript><img height='1' width='1' style='display:none' "
            f"src='https://www.facebook.com/tr?id={fb_pixel_id}&ev=PageView&noscript=1'/></noscript>"
            f"<!-- End Facebook Pixel -->"
        )

    html = html.replace('</body>', f'{tracking_pixel}\n{fb_pixel}\n</body>')

    return html


def generate_index(leads_by_category):
    """Generate the internal directory page."""
    rows = ''
    total = 0
    for cat_heb, leads in sorted(leads_by_category.items()):
        for lead in leads:
            slug = slugify(lead['name'])
            total += 1
            rows += f'''
        <tr>
          <td>{total}</td>
          <td><a href="{slug}/index.html" target="_blank">{lead['name']}</a></td>
          <td>{lead['city']}</td>
          <td>{cat_heb}</td>
          <td>{lead['phone']}</td>
          <td><a href="{slug}/index.html" target="_blank">צפה</a></td>
        </tr>'''

    return f'''<!DOCTYPE html>
<html lang="he" dir="rtl">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Lead Previews Directory</title>
  <link href="https://fonts.googleapis.com/css2?family=Heebo:wght@400;500;700&display=swap" rel="stylesheet">
  <style>
    * {{ margin: 0; padding: 0; box-sizing: border-box; }}
    body {{
      font-family: 'Heebo', sans-serif;
      background: #0f0f1a;
      color: #e0e0e0;
      padding: 40px 20px;
    }}
    h1 {{
      text-align: center;
      font-size: 2rem;
      margin-bottom: 8px;
      color: #fff;
    }}
    .subtitle {{
      text-align: center;
      color: #888;
      margin-bottom: 32px;
      font-size: 1.05rem;
    }}
    table {{
      width: 100%;
      max-width: 1000px;
      margin: 0 auto;
      border-collapse: collapse;
    }}
    th, td {{
      padding: 12px 16px;
      text-align: right;
      border-bottom: 1px solid #222;
    }}
    th {{
      background: #1a1a2e;
      color: #aaa;
      font-weight: 500;
      font-size: 0.9rem;
    }}
    tr:hover {{ background: rgba(255,255,255,0.03); }}
    a {{
      color: #6c9bff;
      text-decoration: none;
    }}
    a:hover {{ text-decoration: underline; }}
    .stats {{
      text-align: center;
      margin-bottom: 24px;
      display: flex;
      gap: 24px;
      justify-content: center;
      flex-wrap: wrap;
    }}
    .stat {{
      background: #1a1a2e;
      padding: 16px 28px;
      border-radius: 12px;
      border: 1px solid #222;
    }}
    .stat-num {{
      font-size: 1.6rem;
      font-weight: 700;
      color: #fff;
    }}
    .stat-label {{
      font-size: 0.85rem;
      color: #888;
    }}
  </style>
</head>
<body>
  <h1>Lead Previews</h1>
  <p class="subtitle">תצוגות מקדימות לעסקים ללא אתר</p>
  <div class="stats">
    <div class="stat">
      <div class="stat-num">{total}</div>
      <div class="stat-label">סה"כ</div>
    </div>
    <div class="stat">
      <div class="stat-num">{len(leads_by_category.get('מסעדה', []))}</div>
      <div class="stat-label">מסעדות</div>
    </div>
    <div class="stat">
      <div class="stat-num">{len(leads_by_category.get('מכון יופי', []))}</div>
      <div class="stat-label">מכוני יופי</div>
    </div>
  </div>
  <table>
    <thead>
      <tr>
        <th>#</th>
        <th>שם העסק</th>
        <th>עיר</th>
        <th>קטגוריה</th>
        <th>טלפון</th>
        <th>תצוגה</th>
      </tr>
    </thead>
    <tbody>{rows}
    </tbody>
  </table>
</body>
</html>'''


def main():
    # Load templates
    banner_html = load_banner()
    templates = {}
    for cat_heb, cat_en in CATEGORY_MAP.items():
        templates[cat_heb] = load_template(cat_en)

    # Read CSV
    with open(CSV_PATH, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        leads = list(reader)

    # Filter: no website only
    no_website = [r for r in leads if r.get('has_website', '').strip().lower() == 'no']

    # Group by category
    leads_by_category = {}
    skipped = []

    for lead in no_website:
        cat = lead.get('category', '').strip()
        if cat not in CATEGORY_MAP:
            skipped.append((lead['name'], cat))
            continue
        leads_by_category.setdefault(cat, []).append(lead)

    # Create output dir
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Load Google Places cache
    cache = load_places_cache()

    # Enrich leads with Google Places data
    enriched_count = 0
    total_leads = sum(len(v) for v in leads_by_category.values())

    if GOOGLE_PLACES_API_KEY:
        print(f'\n--- Google Places Enrichment ---')
        print(f'API key: ...{GOOGLE_PLACES_API_KEY[-8:]}')
    else:
        print(f'\n--- Google Places Enrichment ---')
        print(f'No GOOGLE_PLACES_API_KEY set. Skipping enrichment (using fallbacks).')

    enrichments = {}
    for cat_heb, cat_leads in leads_by_category.items():
        for lead in cat_leads:
            lead_key = f"{lead['name']}|{lead['city']}"
            data = enrich_lead(lead, cache)
            enrichments[lead_key] = data
            if data.get('place_id'):
                enriched_count += 1
                print(f"  Enriching: {lead['name']}... OK")
            else:
                print(f"  Enriching: {lead['name']}... SKIP")

    # Save cache after enrichment
    save_places_cache(cache)

    # Generate pages
    total = 0
    for cat_heb, cat_leads in leads_by_category.items():
        template_html = templates[cat_heb]
        for lead in cat_leads:
            slug = slugify(lead['name'])
            page_dir = os.path.join(OUTPUT_DIR, slug)
            os.makedirs(page_dir, exist_ok=True)

            lead_key = f"{lead['name']}|{lead['city']}"
            enrichment = enrichments.get(lead_key, {})
            html = generate_page(template_html, banner_html, lead, enrichment)
            page_path = os.path.join(page_dir, 'index.html')
            with open(page_path, 'w', encoding='utf-8') as f:
                f.write(html)
            total += 1

    # Generate index
    index_html = generate_index(leads_by_category)
    with open(os.path.join(OUTPUT_DIR, 'index.html'), 'w', encoding='utf-8') as f:
        f.write(index_html)

    # Summary
    print(f'\n=== Lead Preview Generator ===')
    print(f'Total generated: {total}')
    for cat_heb, cat_leads in leads_by_category.items():
        print(f'  {cat_heb}: {len(cat_leads)}')
    if skipped:
        print(f'Skipped (unknown category): {len(skipped)}')
        for name, cat in skipped:
            print(f'  - {name} ({cat})')
    print(f'\nEnriched {enriched_count}/{total_leads} with Google data')
    print(f'Cache: {CACHE_PATH}')
    print(f'Output: {OUTPUT_DIR}/')
    print(f'Index:  {OUTPUT_DIR}/index.html')


if __name__ == '__main__':
    main()
