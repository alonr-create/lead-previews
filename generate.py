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
    # Food
    'מסעדה': 'restaurant', 'קונדיטוריה': 'restaurant', 'מאפייה': 'restaurant',
    # Beauty
    'מכון יופי': 'beauty', 'מספרה': 'beauty', 'סטודיו': 'beauty',
    # All others → universal
    'מוסך': 'universal', 'שיפוצים': 'universal', 'רופא שיניים': 'universal',
    'רואה חשבון': 'universal', 'עורך דין': 'universal', 'צלם': 'universal',
    'חנות חיות': 'universal', 'גן אירועים': 'universal', 'הובלות': 'universal',
    'מכבסות': 'universal', 'מכבסה': 'universal', 'חנות פרחים': 'universal',
    'בית דפוס': 'universal', 'צילום': 'universal', 'מכון כושר': 'universal',
    'וטרינר': 'universal', 'חנות בגדים': 'universal', 'אינסטלטור': 'universal',
    'רהיטים': 'universal', 'עיצוב גרפי': 'universal',
}

CATEGORY_CONFIG = {
    'מסעדה': {'badge': 'חוויה קולינרית', 'cta': 'הזמינו מקום', 'subtitle': 'טעמים שמספרים סיפור', 'about_title': 'הסיפור שלנו', 'about_desc': 'מקום שבו הטעם פוגש את הלב', 'services_label': 'התפריט שלנו'},
    'קונדיטוריה': {'badge': 'מאפים ועוגות', 'cta': 'הזמינו עכשיו', 'subtitle': 'מתוק בכל ביס', 'about_title': 'הסיפור שלנו', 'about_desc': 'מאפייה שמכינה באהבה', 'services_label': 'המוצרים שלנו'},
    'מאפייה': {'badge': 'מאפים טריים', 'cta': 'הזמינו עכשיו', 'subtitle': 'טריים מהתנור', 'about_title': 'הסיפור שלנו', 'about_desc': 'לחם ומאפים טריים כל יום', 'services_label': 'המוצרים שלנו'},
    'מכון יופי': {'badge': 'טיפוח ויופי', 'cta': 'קבעו תור', 'subtitle': 'יופי שמרגישים', 'about_title': 'הסיפור שלנו', 'about_desc': 'מכון יופי מקצועי', 'services_label': 'הטיפולים שלנו'},
    'מספרה': {'badge': 'עיצוב שיער', 'cta': 'קבעו תור', 'subtitle': 'סטייל שמדבר', 'about_title': 'הסיפור שלנו', 'about_desc': 'מספרה מקצועית עם ניסיון', 'services_label': 'השירותים שלנו'},
    'סטודיו': {'badge': 'סטודיו מקצועי', 'cta': 'צרו קשר', 'subtitle': 'מקצועיות ואיכות', 'about_title': 'מי אנחנו', 'about_desc': 'סטודיו מקצועי עם ניסיון', 'services_label': 'השירותים שלנו'},
    'שיפוצים': {'badge': 'שיפוצים ובנייה', 'cta': 'בקשו הצעת מחיר', 'subtitle': 'הבית שלך, החזון שלנו', 'about_title': 'מי אנחנו', 'about_desc': 'צוות שיפוצים מקצועי ואמין', 'services_label': 'השירותים שלנו'},
    'אינסטלטור': {'badge': 'אינסטלציה', 'cta': 'התקשרו עכשיו', 'subtitle': 'פתרון מהיר ומקצועי', 'about_title': 'מי אנחנו', 'about_desc': 'אינסטלטור מוסמך ומנוסה', 'services_label': 'השירותים שלנו'},
    'מוסך': {'badge': 'רכב ותחזוקה', 'cta': 'קבעו תור', 'subtitle': 'הרכב שלך בידיים טובות', 'about_title': 'מי אנחנו', 'about_desc': 'מוסך מורשה עם ציוד מתקדם', 'services_label': 'השירותים שלנו'},
    'רופא שיניים': {'badge': 'רפואת שיניים', 'cta': 'קבעו תור', 'subtitle': 'חיוך בריא ויפה', 'about_title': 'המרפאה שלנו', 'about_desc': 'מרפאת שיניים מתקדמת', 'services_label': 'הטיפולים שלנו'},
    'רואה חשבון': {'badge': 'ייעוץ פיננסי', 'cta': 'קבעו פגישה', 'subtitle': 'המספרים שלך בידיים טובות', 'about_title': 'המשרד שלנו', 'about_desc': 'משרד רואי חשבון מקצועי', 'services_label': 'השירותים שלנו'},
    'עורך דין': {'badge': 'ייעוץ משפטי', 'cta': 'קבעו פגישת ייעוץ', 'subtitle': 'ליווי משפטי מקצועי', 'about_title': 'המשרד שלנו', 'about_desc': 'משרד עורכי דין מנוסה', 'services_label': 'תחומי התמחות'},
    'צלם': {'badge': 'צילום מקצועי', 'cta': 'בקשו הצעת מחיר', 'subtitle': 'רגעים שנשארים לנצח', 'about_title': 'מי אנחנו', 'about_desc': 'צלם מקצועי', 'services_label': 'סוגי צילום'},
    'צילום': {'badge': 'צילום מקצועי', 'cta': 'בקשו הצעת מחיר', 'subtitle': 'רגעים שנשארים לנצח', 'about_title': 'מי אנחנו', 'about_desc': 'סטודיו צילום מקצועי', 'services_label': 'סוגי צילום'},
    'חנות חיות': {'badge': 'חיות מחמד', 'cta': 'בואו לבקר', 'subtitle': 'הכל לחיית המחמד שלך', 'about_title': 'החנות שלנו', 'about_desc': 'חנות חיות עם מגוון רחב', 'services_label': 'המוצרים שלנו'},
    'גן אירועים': {'badge': 'אירועים ושמחות', 'cta': 'בקשו הצעת מחיר', 'subtitle': 'האירוע המושלם שלך', 'about_title': 'המקום שלנו', 'about_desc': 'גן אירועים מרהיב', 'services_label': 'סוגי אירועים'},
    'הובלות': {'badge': 'הובלות ושינוע', 'cta': 'בקשו הצעת מחיר', 'subtitle': 'הובלה בטוחה ומקצועית', 'about_title': 'מי אנחנו', 'about_desc': 'חברת הובלות מקצועית', 'services_label': 'השירותים שלנו'},
    'מכבסות': {'badge': 'כביסה וניקוי', 'cta': 'צרו קשר', 'subtitle': 'נקי כמו חדש', 'about_title': 'מי אנחנו', 'about_desc': 'מכבסה מקצועית', 'services_label': 'השירותים שלנו'},
    'מכבסה': {'badge': 'כביסה וניקוי', 'cta': 'צרו קשר', 'subtitle': 'נקי כמו חדש', 'about_title': 'מי אנחנו', 'about_desc': 'מכבסה מקצועית', 'services_label': 'השירותים שלנו'},
    'חנות פרחים': {'badge': 'פרחים ועיצוב', 'cta': 'הזמינו עכשיו', 'subtitle': 'יופי שפורח', 'about_title': 'החנות שלנו', 'about_desc': 'חנות פרחים עם מגוון עשיר', 'services_label': 'המוצרים שלנו'},
    'בית דפוס': {'badge': 'דפוס והדפסה', 'cta': 'בקשו הצעת מחיר', 'subtitle': 'הדפסה באיכות גבוהה', 'about_title': 'מי אנחנו', 'about_desc': 'בית דפוס מקצועי', 'services_label': 'השירותים שלנו'},
    'מכון כושר': {'badge': 'כושר ובריאות', 'cta': 'הצטרפו עכשיו', 'subtitle': 'הגוף שלך, המטרה שלנו', 'about_title': 'מי אנחנו', 'about_desc': 'מכון כושר מודרני', 'services_label': 'השירותים שלנו'},
    'וטרינר': {'badge': 'רפואה וטרינרית', 'cta': 'קבעו תור', 'subtitle': 'בריאות חיית המחמד שלך', 'about_title': 'המרפאה שלנו', 'about_desc': 'מרפאה וטרינרית מקצועית', 'services_label': 'הטיפולים שלנו'},
    'חנות בגדים': {'badge': 'אופנה וסטייל', 'cta': 'בואו לבקר', 'subtitle': 'סטייל שמדבר', 'about_title': 'החנות שלנו', 'about_desc': 'חנות אופנה', 'services_label': 'הקולקציות שלנו'},
    'רהיטים': {'badge': 'ריהוט ועיצוב', 'cta': 'בואו לבקר', 'subtitle': 'הבית שלך, הסגנון שלך', 'about_title': 'החנות שלנו', 'about_desc': 'חנות רהיטים', 'services_label': 'המוצרים שלנו'},
    'עיצוב גרפי': {'badge': 'עיצוב גרפי', 'cta': 'צרו קשר', 'subtitle': 'עיצוב שמדבר', 'about_title': 'מי אנחנו', 'about_desc': 'סטודיו עיצוב גרפי', 'services_label': 'השירותים שלנו'},
}

DEFAULT_CATEGORY_CONFIG = {'badge': 'שירותים מקצועיים', 'cta': 'צרו קשר', 'subtitle': 'מקצועיות ואיכות', 'about_title': 'מי אנחנו', 'about_desc': 'עסק מקצועי ואמין', 'services_label': 'השירותים שלנו'}

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
        'X-Goog-FieldMask': 'photos,rating,userRatingCount,regularOpeningHours,formattedAddress,reviews,websiteUri,iconMaskBaseUri,iconBackgroundColor,googleMapsUri',
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

    # Icon / logo
    icon_uri = details.get('iconMaskBaseUri', '')
    if icon_uri:
        enrichment['icon_url'] = icon_uri + '.png'
    enrichment['icon_bg_color'] = details.get('iconBackgroundColor', '')

    # Website URI (for favicon extraction)
    website_uri = details.get('websiteUri', '')
    if website_uri:
        enrichment['website_uri'] = website_uri

    # Save to cache
    cache[cache_key] = enrichment
    return enrichment


# ---------------------------------------------------------------------------
# Existing helpers
# ---------------------------------------------------------------------------

def slugify(text):
    """Create a URL-safe slug from Hebrew or English text.
    Uses only the short business name (before | or •), max 40 chars."""
    text = text.strip()
    # Take only the first part before | or • (the actual business name)
    text = re.split(r'[|•]', text)[0].strip()
    # Limit length to 40 chars (cut at word boundary)
    if len(text) > 40:
        text = text[:40].rsplit(' ', 1)[0]
    # Replace spaces and special chars with hyphens
    text = re.sub(r'[\s/\\:;,!?@#$%^&*()+=\[\]{}|<>\'\"•·]+', '-', text)
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


def get_short_name(name):
    """Extract the short business name (before | or •)."""
    return re.split(r'[|•]', name)[0].strip()


def build_logo_html(name, theme='beauty', enrichment=None):
    """Build a logo element for the business.
    Priority: 1) favicon from website, 2) Google icon, 3) CSS initials fallback."""
    if enrichment is None:
        enrichment = {}
    short = get_short_name(name)

    # Theme colors
    colors = {
        'beauty': {'bg': 'linear-gradient(135deg,#C4727E,#B8924A)', 'border': 'rgba(196,114,126,0.15)'},
        'restaurant': {'bg': 'linear-gradient(135deg,#B85C38,#C4964A)', 'border': 'rgba(184,92,56,0.15)'},
        'universal': {'bg': 'linear-gradient(135deg,#2563EB,#D97706)', 'border': 'rgba(37,99,235,0.15)'},
    }
    c = colors.get(theme, colors['beauty'])

    # Try to get a real logo
    logo_img = ''
    website = enrichment.get('website_uri', '')
    icon_url = enrichment.get('icon_url', '')

    if website:
        # Extract domain for favicon via Google's favicon service
        import re as _re
        domain_match = _re.search(r'https?://(?:www\.)?([^/]+)', website)
        if domain_match:
            domain = domain_match.group(1)
            favicon_url = f'https://www.google.com/s2/favicons?domain={domain}&sz=64'
            logo_img = (
                f'<img src="{favicon_url}" alt="" '
                f'style="width:36px;height:36px;border-radius:50%;object-fit:contain;flex-shrink:0" '
                f'onerror="this.style.display=\'none\';this.nextElementSibling.style.display=\'flex\'">'
            )
    elif icon_url:
        bg_color = enrichment.get('icon_bg_color', '#888')
        logo_img = (
            f'<img src="{icon_url}" alt="" '
            f'style="width:36px;height:36px;border-radius:50%;object-fit:contain;flex-shrink:0;'
            f'background:{bg_color};padding:6px" '
            f'onerror="this.style.display=\'none\';this.nextElementSibling.style.display=\'flex\'">'
        )

    # CSS initials fallback (always rendered, hidden if img loads)
    words = short.split()
    initials = ''.join(w[0] for w in words[:2]) if words else '?'
    fallback_style = 'display:none' if logo_img else 'display:flex'
    initials_div = (
        f'<div style="width:36px;height:36px;border-radius:50%;background:{c["bg"]};'
        f'{fallback_style};align-items:center;justify-content:center;color:#fff;font-weight:800;'
        f'font-size:14px;font-family:\'Heebo\',sans-serif;letter-spacing:-0.5px;flex-shrink:0">{initials}</div>'
    )

    return f'''
<!-- Business Logo -->
<div class="biz-logo" style="position:fixed;top:70px;right:20px;z-index:98;display:flex;align-items:center;gap:10px;background:rgba(255,255,255,0.92);backdrop-filter:blur(16px);-webkit-backdrop-filter:blur(16px);padding:8px 16px 8px 8px;border-radius:100px;box-shadow:0 2px 16px rgba(0,0,0,0.06);border:1px solid {c['border']}">
  {logo_img}{initials_div}
  <span style="font-size:14px;font-weight:700;color:#1a1a1a;font-family:\'Heebo\',sans-serif;white-space:nowrap;max-width:160px;overflow:hidden;text-overflow:ellipsis">{short}</span>
</div>'''


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
    'קונדיטוריה': [
        'https://images.unsplash.com/photo-1517248135467-4c7edcad34c4?w=800',
        'https://images.unsplash.com/photo-1555396273-367ea4eb4db5?w=800',
        'https://images.unsplash.com/photo-1414235077428-338989a2e8c0?w=800',
    ],
    'מאפייה': [
        'https://images.unsplash.com/photo-1517248135467-4c7edcad34c4?w=800',
        'https://images.unsplash.com/photo-1555396273-367ea4eb4db5?w=800',
        'https://images.unsplash.com/photo-1414235077428-338989a2e8c0?w=800',
    ],
    'מכון יופי': [
        'https://images.unsplash.com/photo-1560066984-138dadb4c035?w=800',
        'https://images.unsplash.com/photo-1522337360788-8b13dee7a37e?w=800',
        'https://images.unsplash.com/photo-1487412912498-0447578fcca8?w=800',
        'https://images.unsplash.com/photo-1519494026892-80bbd2d6fd0d?w=800',
    ],
    'מספרה': [
        'https://images.unsplash.com/photo-1521590832167-7bcbfaa6381f?w=800',
        'https://images.unsplash.com/photo-1560066984-138dadb4c035?w=800',
        'https://images.unsplash.com/photo-1622286342621-4bd786c2447c?w=800',
    ],
    'סטודיו': [
        'https://images.unsplash.com/photo-1560066984-138dadb4c035?w=800',
        'https://images.unsplash.com/photo-1522337360788-8b13dee7a37e?w=800',
        'https://images.unsplash.com/photo-1487412912498-0447578fcca8?w=800',
    ],
    'שיפוצים': [
        'https://images.unsplash.com/photo-1504307651254-35680f356dfd?w=800',
        'https://images.unsplash.com/photo-1581578731548-c64695cc6952?w=800',
        'https://images.unsplash.com/photo-1503387762-592deb58ef4e?w=800',
    ],
    'אינסטלטור': [
        'https://images.unsplash.com/photo-1585704032915-c3400ca199e7?w=800',
        'https://images.unsplash.com/photo-1558618666-fcd25c85f82e?w=800',
        'https://images.unsplash.com/photo-1504307651254-35680f356dfd?w=800',
    ],
    'מוסך': [
        'https://images.unsplash.com/photo-1487754180451-c456f719a1fc?w=800',
        'https://images.unsplash.com/photo-1625047509168-a7026f36de04?w=800',
        'https://images.unsplash.com/photo-1486262715619-67b85e0b08d3?w=800',
    ],
    'רופא שיניים': [
        'https://images.unsplash.com/photo-1629909613654-28e377c37b09?w=800',
        'https://images.unsplash.com/photo-1606811841689-23dfddce3e95?w=800',
        'https://images.unsplash.com/photo-1588776814546-1ffcf47267a5?w=800',
    ],
    'רואה חשבון': [
        'https://images.unsplash.com/photo-1554224155-8d04cb21cd6c?w=800',
        'https://images.unsplash.com/photo-1460925895917-afdab827c52f?w=800',
        'https://images.unsplash.com/photo-1454165804606-c3d57bc86b40?w=800',
    ],
    'עורך דין': [
        'https://images.unsplash.com/photo-1589829545856-d10d557cf95f?w=800',
        'https://images.unsplash.com/photo-1505664194779-8beaceb93744?w=800',
        'https://images.unsplash.com/photo-1450101499163-c8848c66ca85?w=800',
    ],
    'צלם': [
        'https://images.unsplash.com/photo-1471341971476-ae15ff5dd4ea?w=800',
        'https://images.unsplash.com/photo-1542038784456-1ea8e935640e?w=800',
        'https://images.unsplash.com/photo-1452587925148-ce544e77e70d?w=800',
    ],
    'צילום': [
        'https://images.unsplash.com/photo-1471341971476-ae15ff5dd4ea?w=800',
        'https://images.unsplash.com/photo-1542038784456-1ea8e935640e?w=800',
        'https://images.unsplash.com/photo-1452587925148-ce544e77e70d?w=800',
    ],
    'חנות חיות': [
        'https://images.unsplash.com/photo-1548199973-03cce0bbc87b?w=800',
        'https://images.unsplash.com/photo-1450778869180-41d0601e046e?w=800',
        'https://images.unsplash.com/photo-1587300003388-59208cc962cb?w=800',
    ],
    'גן אירועים': [
        'https://images.unsplash.com/photo-1519167758481-83f550bb49b3?w=800',
        'https://images.unsplash.com/photo-1464366400600-7168b8af9bc3?w=800',
        'https://images.unsplash.com/photo-1478146059778-26028b07395a?w=800',
    ],
    'הובלות': [
        'https://images.unsplash.com/photo-1600518464441-9154a4dea21b?w=800',
        'https://images.unsplash.com/photo-1586864387967-d02ef85d93e8?w=800',
        'https://images.unsplash.com/photo-1558618666-fcd25c85f82e?w=800',
    ],
    'מכבסות': [
        'https://images.unsplash.com/photo-1545173168-9f1947eebb7f?w=800',
        'https://images.unsplash.com/photo-1517677208171-0bc6725a3e60?w=800',
        'https://images.unsplash.com/photo-1582735689369-4fe89db7114c?w=800',
    ],
    'מכבסה': [
        'https://images.unsplash.com/photo-1545173168-9f1947eebb7f?w=800',
        'https://images.unsplash.com/photo-1517677208171-0bc6725a3e60?w=800',
        'https://images.unsplash.com/photo-1582735689369-4fe89db7114c?w=800',
    ],
    'חנות פרחים': [
        'https://images.unsplash.com/photo-1487530811176-3780de880c2d?w=800',
        'https://images.unsplash.com/photo-1490750967868-88aa4f44baee?w=800',
        'https://images.unsplash.com/photo-1455659817273-f96807779a8a?w=800',
    ],
    'בית דפוס': [
        'https://images.unsplash.com/photo-1504711434969-e33886168d5c?w=800',
        'https://images.unsplash.com/photo-1497366216548-37526070297c?w=800',
        'https://images.unsplash.com/photo-1497215728101-856f4ea42174?w=800',
    ],
    'מכון כושר': [
        'https://images.unsplash.com/photo-1534438327276-14e5300c3a48?w=800',
        'https://images.unsplash.com/photo-1571019613454-1cb2f99b2d8b?w=800',
        'https://images.unsplash.com/photo-1540497077202-7c8a3999166f?w=800',
    ],
    'וטרינר': [
        'https://images.unsplash.com/photo-1548199973-03cce0bbc87b?w=800',
        'https://images.unsplash.com/photo-1587300003388-59208cc962cb?w=800',
        'https://images.unsplash.com/photo-1450778869180-41d0601e046e?w=800',
    ],
    'חנות בגדים': [
        'https://images.unsplash.com/photo-1441986300917-64674bd600d8?w=800',
        'https://images.unsplash.com/photo-1558171813-4c088753af8f?w=800',
        'https://images.unsplash.com/photo-1567401893414-76b7b1e5a7a5?w=800',
    ],
    'רהיטים': [
        'https://images.unsplash.com/photo-1555041469-a586c61ea9bc?w=800',
        'https://images.unsplash.com/photo-1524758631624-e2822e304c36?w=800',
        'https://images.unsplash.com/photo-1506439773649-6e0eb8cfb237?w=800',
    ],
    'עיצוב גרפי': [
        'https://images.unsplash.com/photo-1558655146-d09347e92766?w=800',
        'https://images.unsplash.com/photo-1561070791-2526d30994b5?w=800',
        'https://images.unsplash.com/photo-1497215728101-856f4ea42174?w=800',
    ],
    'DEFAULT': [
        'https://images.unsplash.com/photo-1497366216548-37526070297c?w=800',
        'https://images.unsplash.com/photo-1497366811353-6870744d04b2?w=800',
        'https://images.unsplash.com/photo-1497215728101-856f4ea42174?w=800',
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
    short_name = get_short_name(lead['name'])

    # Build map section
    map_html = build_map_section(short_name, lead['city'], address)

    # Build logo (with real favicon if available)
    theme = CATEGORY_MAP.get(category, 'beauty')
    logo_html = build_logo_html(lead['name'], theme, enrichment)

    html = template_html.replace('{{BUSINESS_NAME}}', short_name)
    html = html.replace('{{CITY}}', lead['city'])
    html = html.replace('{{PHONE}}', lead['phone'])
    html = html.replace('{{PHONE_CLEAN}}', phone_clean)
    html = html.replace('{{BANNER}}', banner_html + logo_html)

    # New enrichment variables
    html = html.replace('{{ADDRESS}}', address)

    rating = enrichment.get('rating', '')
    html = html.replace('{{RATING}}', str(rating) if rating else '')

    reviews_count = enrichment.get('reviews_count', '')
    html = html.replace('{{REVIEWS_COUNT}}', str(reviews_count) if reviews_count else '')

    # Category-specific text placeholders (for universal template)
    config = CATEGORY_CONFIG.get(category, DEFAULT_CATEGORY_CONFIG)
    html = html.replace('{{BADGE_TEXT}}', config['badge'])
    html = html.replace('{{CTA_TEXT}}', config['cta'])
    html = html.replace('{{HERO_SUBTITLE}}', config['subtitle'])
    html = html.replace('{{ABOUT_TITLE}}', config['about_title'])
    html = html.replace('{{ABOUT_DESC}}', config['about_desc'])
    html = html.replace('{{SERVICES_LABEL}}', config['services_label'])

    # Photos: use Google Places if available, otherwise Unsplash fallbacks
    photo_urls = enrichment.get('photo_urls', [])
    fallbacks = UNSPLASH_FALLBACKS.get(category, UNSPLASH_FALLBACKS.get('DEFAULT', []))
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

    # Legal disclaimer — protection against impersonation claims
    disclaimer_html = (
        '<div style="background:#f5f5f5;border-top:1px solid #ddd;padding:16px 20px;'
        'text-align:center;font-family:Heebo,Arial,sans-serif;direction:rtl;'
        'font-size:12px;color:#999;line-height:1.6;">'
        'אתר לדוגמא בלבד — נבנה על ידי '
        '<a href="https://alon-dev.vercel.app" style="color:#0f3460;">alon dev</a>'
        ' כהצעה עסקית. אינו מייצג את העסק באופן רשמי. '
        'המידע נאסף ממקורות ציבוריים (Google Maps). '
        '<a href="https://output-seven-black.vercel.app/terms/" style="color:#0f3460;">תנאי שימוש</a>'
        '<br>לבקשת הסרה מיידית: '
        '<a href="https://wa.me/972559173249?text=בקשת%20הסרה%20-%20' + short_name.replace(' ', '%20') + '" style="color:#25D366;">'
        '055-917-3249</a>'
        '</div>'
    )

    # Inject map before footer
    html = html.replace('<!-- Footer -->', f'{map_html}\n\n{disclaimer_html}\n\n<!-- Footer -->')

    # Tracking pixel — fires when someone opens the page
    tracking_pixel = (
        f'<script>'
        f'(function(){{'
        f'var p="{phone_clean}",n=encodeURIComponent("{short_name}");'
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
            f"fbq('track','ViewContent',{{content_name:'{short_name}',content_category:'{lead.get('category','')}'}});"
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
            short = get_short_name(lead['name'])
            total += 1
            rows += f'''
        <tr>
          <td>{total}</td>
          <td><a href="{slug}/index.html" target="_blank">{short}</a></td>
          <td>{lead['city']}</td>
          <td>{cat_heb}</td>
          <td>{lead['phone']}</td>
          <td><a href="{slug}/index.html" target="_blank">צפה</a></td>
        </tr>'''

    # Build dynamic stats for all categories
    stats_html = f'''
    <div class="stat">
      <div class="stat-num">{total}</div>
      <div class="stat-label">סה"כ</div>
    </div>'''
    for cat_name, cat_leads in sorted(leads_by_category.items(), key=lambda x: -len(x[1])):
        stats_html += f'''
    <div class="stat">
      <div class="stat-num">{len(cat_leads)}</div>
      <div class="stat-label">{cat_name}</div>
    </div>'''

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
      gap: 16px;
      justify-content: center;
      flex-wrap: wrap;
    }}
    .stat {{
      background: #1a1a2e;
      padding: 12px 20px;
      border-radius: 12px;
      border: 1px solid #222;
    }}
    .stat-num {{
      font-size: 1.4rem;
      font-weight: 700;
      color: #fff;
    }}
    .stat-label {{
      font-size: 0.8rem;
      color: #888;
    }}
  </style>
</head>
<body>
  <h1>Lead Previews</h1>
  <p class="subtitle">תצוגות מקדימות לעסקים ללא אתר</p>
  <div class="stats">{stats_html}
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
        if not cat:
            skipped.append((lead['name'], cat))
            continue
        if cat not in CATEGORY_MAP:
            # Default unknown categories to universal template
            CATEGORY_MAP[cat] = 'universal'
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
