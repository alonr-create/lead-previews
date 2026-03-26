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
CSV_PATH = '/Users/oakhome/קלוד עבודות/leads_enriched_v2.csv'
CACHE_PATH = os.path.join(BASE_DIR, 'places_cache.json')

# Load .env from lead-outreach (for FB_PIXEL_ID, GA4_MEASUREMENT_ID)
_env_path = os.path.join(os.path.dirname(BASE_DIR), 'lead-outreach', '.env')
if os.path.exists(_env_path):
    with open(_env_path) as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith('#') and '=' in _line:
                _k, _v = _line.split('=', 1)
                os.environ.setdefault(_k.strip(), _v.strip())

GOOGLE_PLACES_API_KEY = os.environ.get('GOOGLE_PLACES_API_KEY', 'AIzaSyBHEODU6QPeJmKpy1oZg2vfjUXrvHXgWBQ')

CATEGORY_MAP = {
    # Hebrew categories — all use universal template for variable-driven content
    'מסעדה': 'restaurant', 'קונדיטוריה': 'restaurant', 'מאפייה': 'restaurant',
    'מכון יופי': 'universal', 'מספרה': 'universal', 'סטודיו': 'universal',
    'מוסך': 'universal', 'שיפוצים': 'universal', 'רופא שיניים': 'universal',
    'רואה חשבון': 'universal', 'עורך דין': 'universal', 'צלם': 'universal',
    'חנות חיות': 'universal', 'גן אירועים': 'universal', 'הובלות': 'universal',
    'מכבסות': 'universal', 'מכבסה': 'universal', 'חנות פרחים': 'universal',
    'בית דפוס': 'universal', 'צילום': 'universal', 'מכון כושר': 'universal',
    'וטרינר': 'universal', 'חנות בגדים': 'universal', 'אינסטלטור': 'universal',
    'רהיטים': 'universal', 'עיצוב גרפי': 'universal',
    'קוסמטיקאית': 'universal', 'בית קפה': 'restaurant', 'דיגיי': 'universal',
    'פילאטיס': 'universal', 'אולם אירועים': 'universal', 'סושי': 'restaurant',
    'הפקת אירועים': 'universal', 'חנות רהיטים': 'universal', 'סטודיו יוגה': 'universal',
    'שווארמה': 'restaurant', 'ספא': 'universal', 'חשמלאי': 'universal', 'פיצריה': 'restaurant',
    'יוגה': 'universal',
    # English categories (from mobile_leads.csv)
    'personal trainer': 'universal', 'barbershop': 'universal', 'air conditioning repair': 'universal',
    'laser hair removal': 'universal', 'photography studio': 'universal', 'motorcycle repair': 'universal',
    'reflexology': 'universal', 'carpentry': 'universal', 'beauty salon': 'universal',
    'catering': 'restaurant', 'moving company': 'universal', 'bridal salon': 'universal',
    'locksmith': 'universal', 'massage': 'universal', 'tire shop': 'universal',
    'nail bar': 'universal', 'auto parts': 'universal', 'cleaning service': 'universal',
    'tattoo parlor': 'universal', 'insurance agent': 'universal', 'architect': 'universal',
    'gardening': 'universal', 'dance studio': 'universal', 'hair salon': 'universal',
    'interior design': 'universal', 'glass repair': 'universal', 'accountant': 'universal',
    'upholstery': 'universal', 'ice cream shop': 'restaurant', 'gift shop': 'universal',
    'jewelry store': 'universal', 'bakery': 'restaurant', 'butcher shop': 'restaurant',
    'fish market': 'restaurant', 'physiotherapy': 'universal', 'spa': 'universal',
    'juice bar': 'restaurant', 'car appraiser': 'universal', 'mortgage advisor': 'universal',
    'dental lab': 'universal', 'toy store': 'universal', 'dietitian': 'universal',
    'blinds shutters': 'universal', 'traffic lawyer': 'universal', 'flooring tiles': 'universal',
    'welding': 'universal', 'graphic design': 'universal', 'landscaping': 'universal',
    'divorce lawyer': 'universal', 'glazier': 'universal', 'dermatology clinic': 'universal',
    'grocery store': 'universal', 'chiropractor': 'universal', 'pension advisor': 'universal',
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
    'קוסמטיקאית': {'badge': 'טיפוח ויופי', 'cta': 'קבעו תור', 'subtitle': 'יופי שמרגישים', 'about_title': 'הסיפור שלנו', 'about_desc': 'קוסמטיקאית מקצועית', 'services_label': 'הטיפולים שלנו'},
    'בית קפה': {'badge': 'קפה ואווירה', 'cta': 'בואו לבקר', 'subtitle': 'הפסקה שמגיעה לך', 'about_title': 'הסיפור שלנו', 'about_desc': 'בית קפה עם אופי', 'services_label': 'התפריט שלנו'},
    'דיגיי': {'badge': 'DJ ומוזיקה', 'cta': 'בקשו הצעת מחיר', 'subtitle': 'המוזיקה שתזכרו', 'about_title': 'מי אנחנו', 'about_desc': 'DJ מקצועי לכל אירוע', 'services_label': 'השירותים שלנו'},
    'פילאטיס': {'badge': 'פילאטיס', 'cta': 'הצטרפו עכשיו', 'subtitle': 'גוף חזק, נפש רגועה', 'about_title': 'הסטודיו שלנו', 'about_desc': 'סטודיו פילאטיס מקצועי', 'services_label': 'השיעורים שלנו'},
    'אולם אירועים': {'badge': 'אירועים ושמחות', 'cta': 'בקשו הצעת מחיר', 'subtitle': 'האירוע המושלם שלך', 'about_title': 'האולם שלנו', 'about_desc': 'אולם אירועים מפואר', 'services_label': 'סוגי אירועים'},
    'סושי': {'badge': 'סושי ומטבח יפני', 'cta': 'הזמינו עכשיו', 'subtitle': 'טעם של יפן', 'about_title': 'הסיפור שלנו', 'about_desc': 'סושי בר מקצועי', 'services_label': 'התפריט שלנו'},
    'הפקת אירועים': {'badge': 'הפקת אירועים', 'cta': 'בקשו הצעת מחיר', 'subtitle': 'הפקה שלמה מא עד ת', 'about_title': 'מי אנחנו', 'about_desc': 'חברת הפקת אירועים מקצועית', 'services_label': 'השירותים שלנו'},
    'חנות רהיטים': {'badge': 'ריהוט ועיצוב', 'cta': 'בואו לבקר', 'subtitle': 'הבית שלך, הסגנון שלך', 'about_title': 'החנות שלנו', 'about_desc': 'חנות רהיטים איכותיים', 'services_label': 'המוצרים שלנו'},
    'סטודיו יוגה': {'badge': 'יוגה ומדיטציה', 'cta': 'הצטרפו עכשיו', 'subtitle': 'שקט פנימי, כוח חיצוני', 'about_title': 'הסטודיו שלנו', 'about_desc': 'סטודיו יוגה עם מדריכים מוסמכים', 'services_label': 'השיעורים שלנו'},
    'שווארמה': {'badge': 'אוכל רחוב', 'cta': 'הזמינו עכשיו', 'subtitle': 'טעם שלא שוכחים', 'about_title': 'הסיפור שלנו', 'about_desc': 'שווארמה מקצועית', 'services_label': 'התפריט שלנו'},
    'ספא': {'badge': 'ספא ורוגע', 'cta': 'קבעו טיפול', 'subtitle': 'פינוק שמגיע לך', 'about_title': 'הספא שלנו', 'about_desc': 'ספא מפנק עם טיפולים מקצועיים', 'services_label': 'הטיפולים שלנו'},
}

DEFAULT_CATEGORY_CONFIG = {'badge': 'שירותים מקצועיים', 'cta': 'צרו קשר', 'subtitle': 'מקצועיות ואיכות', 'about_title': 'מי אנחנו', 'about_desc': 'עסק מקצועי ואמין', 'services_label': 'השירותים שלנו'}

# English category configs — Hebrew UI text for English category names
CATEGORY_CONFIG.update({
    'personal trainer': {'badge': 'כושר ואימון אישי', 'cta': 'קבעו אימון ניסיון', 'subtitle': 'הגוף שלך, המטרה שלנו', 'about_title': 'מי אנחנו', 'about_desc': 'מאמן כושר אישי מוסמך ומנוסה', 'services_label': 'תוכניות אימון'},
    'barbershop': {'badge': 'מספרת גברים', 'cta': 'קבעו תור', 'subtitle': 'סטייל שמדבר', 'about_title': 'הסיפור שלנו', 'about_desc': 'ברבר מקצועי עם ניסיון', 'services_label': 'השירותים שלנו'},
    'air conditioning repair': {'badge': 'מיזוג אוויר', 'cta': 'התקשרו עכשיו', 'subtitle': 'פתרון מהיר ומקצועי', 'about_title': 'מי אנחנו', 'about_desc': 'טכנאי מיזוג מוסמך', 'services_label': 'השירותים שלנו'},
    'laser hair removal': {'badge': 'הסרת שיער בלייזר', 'cta': 'קבעו טיפול ניסיון', 'subtitle': 'עור חלק לתמיד', 'about_title': 'המכון שלנו', 'about_desc': 'מכון לייזר מתקדם עם טכנולוגיה חדישה', 'services_label': 'הטיפולים שלנו'},
    'photography studio': {'badge': 'צילום מקצועי', 'cta': 'בקשו הצעת מחיר', 'subtitle': 'רגעים שנשארים לנצח', 'about_title': 'הסטודיו שלנו', 'about_desc': 'סטודיו צילום מקצועי', 'services_label': 'סוגי צילום'},
    'motorcycle repair': {'badge': 'מוסך אופנועים', 'cta': 'קבעו תור', 'subtitle': 'האופנוע שלך בידיים טובות', 'about_title': 'המוסך שלנו', 'about_desc': 'מוסך אופנועים מורשה ומקצועי', 'services_label': 'השירותים שלנו'},
    'reflexology': {'badge': 'רפלקסולוגיה', 'cta': 'קבעו טיפול', 'subtitle': 'איזון גוף ונפש', 'about_title': 'המטפלת שלנו', 'about_desc': 'מטפלת רפלקסולוגיה מוסמכת', 'services_label': 'הטיפולים שלנו'},
    'carpentry': {'badge': 'נגרות ועץ', 'cta': 'בקשו הצעת מחיר', 'subtitle': 'עבודת עץ מקצועית', 'about_title': 'מי אנחנו', 'about_desc': 'נגר מקצועי עם ניסיון רב', 'services_label': 'השירותים שלנו'},
    'beauty salon': {'badge': 'יופי וטיפוח', 'cta': 'קבעו תור', 'subtitle': 'יופי שמרגישים', 'about_title': 'הסלון שלנו', 'about_desc': 'סלון יופי מקצועי עם טיפולים מתקדמים', 'services_label': 'הטיפולים שלנו'},
    'catering': {'badge': 'קייטרינג ואירועים', 'cta': 'בקשו תפריט', 'subtitle': 'טעמים שמספרים סיפור', 'about_title': 'הסיפור שלנו', 'about_desc': 'שירותי קייטרינג מקצועיים לכל אירוע', 'services_label': 'התפריט שלנו'},
    'moving company': {'badge': 'הובלות ושינוע', 'cta': 'בקשו הצעת מחיר', 'subtitle': 'הובלה בטוחה ומקצועית', 'about_title': 'מי אנחנו', 'about_desc': 'חברת הובלות מקצועית ואמינה', 'services_label': 'השירותים שלנו'},
    'bridal salon': {'badge': 'שמלות כלה', 'cta': 'קבעו מדידה', 'subtitle': 'השמלה המושלמת ליום המושלם', 'about_title': 'הסלון שלנו', 'about_desc': 'סלון שמלות כלה עם מגוון עשיר', 'services_label': 'הקולקציות שלנו'},
    'locksmith': {'badge': 'מנעולן', 'cta': 'התקשרו עכשיו', 'subtitle': 'פתרון מהיר 24/7', 'about_title': 'מי אנחנו', 'about_desc': 'מנעולן מוסמך עם שירות מהיר', 'services_label': 'השירותים שלנו'},
    'massage': {'badge': 'עיסוי מקצועי', 'cta': 'קבעו טיפול', 'subtitle': 'פינוק שמגיע לך', 'about_title': 'המטפל שלנו', 'about_desc': 'מעסה מוסמך עם ניסיון רב', 'services_label': 'סוגי עיסוי'},
    'tire shop': {'badge': 'צמיגים ופנצ\'ריות', 'cta': 'התקשרו עכשיו', 'subtitle': 'נסיעה בטוחה מתחילה בצמיגים', 'about_title': 'מי אנחנו', 'about_desc': 'חנות צמיגים מקצועית', 'services_label': 'השירותים שלנו'},
    'nail bar': {'badge': 'ציפורניים', 'cta': 'קבעו תור', 'subtitle': 'ציפורניים מושלמות', 'about_title': 'הסטודיו שלנו', 'about_desc': 'סטודיו ציפורניים מקצועי', 'services_label': 'הטיפולים שלנו'},
    'auto parts': {'badge': 'חלקי חילוף לרכב', 'cta': 'התקשרו לבדיקה', 'subtitle': 'החלפים שאתה צריך', 'about_title': 'החנות שלנו', 'about_desc': 'חנות חלפי חילוף מקצועית', 'services_label': 'המוצרים שלנו'},
    'cleaning service': {'badge': 'ניקיון מקצועי', 'cta': 'בקשו הצעת מחיר', 'subtitle': 'נקי כמו חדש', 'about_title': 'מי אנחנו', 'about_desc': 'שירותי ניקיון מקצועיים', 'services_label': 'השירותים שלנו'},
    'tattoo parlor': {'badge': 'קעקועים ופירסינג', 'cta': 'קבעו ייעוץ', 'subtitle': 'אמנות על הגוף', 'about_title': 'הסטודיו שלנו', 'about_desc': 'סטודיו קעקועים מקצועי', 'services_label': 'סוגי עבודות'},
    'insurance agent': {'badge': 'ביטוח', 'cta': 'קבעו פגישת ייעוץ', 'subtitle': 'הגנה שמותאמת לך', 'about_title': 'המשרד שלנו', 'about_desc': 'סוכן ביטוח עם ניסיון וליווי אישי', 'services_label': 'תחומי ביטוח'},
    'architect': {'badge': 'אדריכלות ועיצוב', 'cta': 'קבעו פגישה', 'subtitle': 'החזון שלך, התכנון שלנו', 'about_title': 'המשרד שלנו', 'about_desc': 'משרד אדריכלות מקצועי', 'services_label': 'תחומי התמחות'},
    'gardening': {'badge': 'גינון ונוף', 'cta': 'בקשו הצעת מחיר', 'subtitle': 'הגינה שחלמת עליה', 'about_title': 'מי אנחנו', 'about_desc': 'גנן מקצועי עם ניסיון רב', 'services_label': 'השירותים שלנו'},
    'dance studio': {'badge': 'סטודיו למחול', 'cta': 'הצטרפו לשיעור ניסיון', 'subtitle': 'ריקוד הוא חופש', 'about_title': 'הסטודיו שלנו', 'about_desc': 'סטודיו מחול מקצועי', 'services_label': 'סוגי ריקוד'},
    'hair salon': {'badge': 'עיצוב שיער', 'cta': 'קבעו תור', 'subtitle': 'סטייל שמדבר', 'about_title': 'הסלון שלנו', 'about_desc': 'מספרה מקצועית עם מעצבים מנוסים', 'services_label': 'השירותים שלנו'},
    'interior design': {'badge': 'עיצוב פנים', 'cta': 'קבעו פגישת ייעוץ', 'subtitle': 'הבית שלך, הסגנון שלך', 'about_title': 'הסטודיו שלנו', 'about_desc': 'סטודיו עיצוב פנים מקצועי', 'services_label': 'תחומי התמחות'},
    'glass repair': {'badge': 'זגגות', 'cta': 'בקשו הצעת מחיר', 'subtitle': 'פתרונות זכוכית מקצועיים', 'about_title': 'מי אנחנו', 'about_desc': 'זגג מקצועי עם ניסיון', 'services_label': 'השירותים שלנו'},
    'accountant': {'badge': 'ראיית חשבון', 'cta': 'קבעו פגישה', 'subtitle': 'המספרים שלך בידיים טובות', 'about_title': 'המשרד שלנו', 'about_desc': 'רואה חשבון מקצועי', 'services_label': 'השירותים שלנו'},
    'upholstery': {'badge': 'ריפוד', 'cta': 'בקשו הצעת מחיר', 'subtitle': 'ריפוד חדש, חיים חדשים', 'about_title': 'מי אנחנו', 'about_desc': 'מרפד מקצועי', 'services_label': 'השירותים שלנו'},
    'ice cream shop': {'badge': 'גלידה', 'cta': 'בואו לטעום', 'subtitle': 'טעמים שמשמחים', 'about_title': 'הסיפור שלנו', 'about_desc': 'גלידריה עם טעמים ייחודיים', 'services_label': 'הטעמים שלנו'},
    'gift shop': {'badge': 'מתנות', 'cta': 'בואו לבקר', 'subtitle': 'המתנה המושלמת', 'about_title': 'החנות שלנו', 'about_desc': 'חנות מתנות עם מגוון עשיר', 'services_label': 'המוצרים שלנו'},
    'jewelry store': {'badge': 'תכשיטים', 'cta': 'בואו לבקר', 'subtitle': 'יופי שנשאר', 'about_title': 'החנות שלנו', 'about_desc': 'חנות תכשיטים איכותית', 'services_label': 'הקולקציות שלנו'},
    'bakery': {'badge': 'מאפים טריים', 'cta': 'בואו לטעום', 'subtitle': 'טריים מהתנור', 'about_title': 'הסיפור שלנו', 'about_desc': 'מאפייה עם מאפים טריים כל יום', 'services_label': 'המוצרים שלנו'},
    'butcher shop': {'badge': 'קצבייה', 'cta': 'בואו לבקר', 'subtitle': 'בשר איכותי ומקצועי', 'about_title': 'החנות שלנו', 'about_desc': 'קצבייה מקצועית', 'services_label': 'המוצרים שלנו'},
    'fish market': {'badge': 'דגים טריים', 'cta': 'בואו לבקר', 'subtitle': 'טריות שמרגישים', 'about_title': 'החנות שלנו', 'about_desc': 'חנות דגים טריים ואיכותיים', 'services_label': 'המוצרים שלנו'},
    'physiotherapy': {'badge': 'פיזיותרפיה', 'cta': 'קבעו טיפול', 'subtitle': 'חזרה לתנועה חופשית', 'about_title': 'המרפאה שלנו', 'about_desc': 'מרפאת פיזיותרפיה מקצועית', 'services_label': 'הטיפולים שלנו'},
    'spa': {'badge': 'ספא ורוגע', 'cta': 'קבעו טיפול', 'subtitle': 'פינוק שמגיע לך', 'about_title': 'הספא שלנו', 'about_desc': 'ספא מפנק עם טיפולים מקצועיים', 'services_label': 'הטיפולים שלנו'},
    'juice bar': {'badge': 'מיצים טבעיים', 'cta': 'בואו לטעום', 'subtitle': 'טרי וטבעי', 'about_title': 'הסיפור שלנו', 'about_desc': 'בר מיצים טבעיים', 'services_label': 'התפריט שלנו'},
    'car appraiser': {'badge': 'שמאות רכב', 'cta': 'קבעו בדיקה', 'subtitle': 'הערכה מקצועית ואמינה', 'about_title': 'מי אנחנו', 'about_desc': 'שמאי רכב מוסמך', 'services_label': 'השירותים שלנו'},
    'mortgage advisor': {'badge': 'ייעוץ משכנתאות', 'cta': 'קבעו פגישת ייעוץ', 'subtitle': 'המשכנתא שמתאימה לך', 'about_title': 'מי אנחנו', 'about_desc': 'יועץ משכנתאות מקצועי', 'services_label': 'השירותים שלנו'},
    'dental lab': {'badge': 'מעבדת שיניים', 'cta': 'צרו קשר', 'subtitle': 'מקצועיות ודיוק', 'about_title': 'המעבדה שלנו', 'about_desc': 'מעבדת שיניים מתקדמת', 'services_label': 'השירותים שלנו'},
    'toy store': {'badge': 'צעצועים ומשחקים', 'cta': 'בואו לבקר', 'subtitle': 'עולם של כיף', 'about_title': 'החנות שלנו', 'about_desc': 'חנות צעצועים עם מגוון רחב', 'services_label': 'המוצרים שלנו'},
    'dietitian': {'badge': 'תזונה ודיאטה', 'cta': 'קבעו פגישה', 'subtitle': 'תזונה שמתאימה לך', 'about_title': 'מי אנחנו', 'about_desc': 'דיאטנית קלינית מוסמכת', 'services_label': 'השירותים שלנו'},
    'blinds shutters': {'badge': 'תריסים וסככות', 'cta': 'בקשו הצעת מחיר', 'subtitle': 'הגנה ועיצוב לבית', 'about_title': 'מי אנחנו', 'about_desc': 'מתקין תריסים מקצועי', 'services_label': 'השירותים שלנו'},
    'traffic lawyer': {'badge': 'עורך דין תעבורה', 'cta': 'קבעו ייעוץ', 'subtitle': 'ליווי משפטי מקצועי', 'about_title': 'המשרד שלנו', 'about_desc': 'עורך דין תעבורה מנוסה', 'services_label': 'תחומי התמחות'},
    'flooring tiles': {'badge': 'ריצוף ואריחים', 'cta': 'בקשו הצעת מחיר', 'subtitle': 'הרצפה המושלמת', 'about_title': 'מי אנחנו', 'about_desc': 'רצף מקצועי', 'services_label': 'השירותים שלנו'},
    'welding': {'badge': 'ריתוך ומסגרות', 'cta': 'בקשו הצעת מחיר', 'subtitle': 'ריתוך מקצועי', 'about_title': 'מי אנחנו', 'about_desc': 'רתך מוסמך ומנוסה', 'services_label': 'השירותים שלנו'},
    'graphic design': {'badge': 'עיצוב גרפי', 'cta': 'צרו קשר', 'subtitle': 'עיצוב שמדבר', 'about_title': 'הסטודיו שלנו', 'about_desc': 'סטודיו עיצוב גרפי מקצועי', 'services_label': 'השירותים שלנו'},
    'landscaping': {'badge': 'גינון ונוף', 'cta': 'בקשו הצעת מחיר', 'subtitle': 'עיצוב גינות מקצועי', 'about_title': 'מי אנחנו', 'about_desc': 'מעצב נוף מקצועי', 'services_label': 'השירותים שלנו'},
    'divorce lawyer': {'badge': 'עורך דין גירושין', 'cta': 'קבעו ייעוץ', 'subtitle': 'ליווי משפטי אישי', 'about_title': 'המשרד שלנו', 'about_desc': 'עורך דין דיני משפחה', 'services_label': 'תחומי התמחות'},
    'glazier': {'badge': 'זגגות', 'cta': 'בקשו הצעת מחיר', 'subtitle': 'עבודות זכוכית מקצועיות', 'about_title': 'מי אנחנו', 'about_desc': 'זגג מומחה', 'services_label': 'השירותים שלנו'},
    'dermatology clinic': {'badge': 'רפואת עור', 'cta': 'קבעו תור', 'subtitle': 'עור בריא ומטופח', 'about_title': 'המרפאה שלנו', 'about_desc': 'מרפאת עור מתקדמת', 'services_label': 'הטיפולים שלנו'},
    'grocery store': {'badge': 'מכולת', 'cta': 'בואו לבקר', 'subtitle': 'הכל תחת קורת גג אחת', 'about_title': 'החנות שלנו', 'about_desc': 'מכולת שכונתית עם מגוון עשיר', 'services_label': 'המוצרים שלנו'},
    'chiropractor': {'badge': 'כירופרקטיקה', 'cta': 'קבעו טיפול', 'subtitle': 'גב ישר, חיים טובים', 'about_title': 'המרפאה שלנו', 'about_desc': 'כירופרקט מוסמך', 'services_label': 'הטיפולים שלנו'},
    'pension advisor': {'badge': 'ייעוץ פנסיוני', 'cta': 'קבעו פגישת ייעוץ', 'subtitle': 'העתיד הפיננסי שלך', 'about_title': 'מי אנחנו', 'about_desc': 'יועץ פנסיוני מוסמך', 'services_label': 'השירותים שלנו'},
})

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

HEBREW_TRANSLIT = {
    'א': 'a', 'ב': 'b', 'ג': 'g', 'ד': 'd', 'ה': 'h', 'ו': 'v',
    'ז': 'z', 'ח': 'ch', 'ט': 't', 'י': 'y', 'כ': 'k', 'ך': 'k',
    'ל': 'l', 'מ': 'm', 'ם': 'm', 'נ': 'n', 'ן': 'n', 'ס': 's',
    'ע': 'a', 'פ': 'p', 'ף': 'f', 'צ': 'ts', 'ץ': 'ts', 'ק': 'k',
    'ר': 'r', 'ש': 'sh', 'ת': 't',
}

def slugify(text):
    """Create an ASCII-safe URL slug from Hebrew or English text.
    Uses only the short business name (before | or •), max 40 chars."""
    text = text.strip()
    # Take only the first part before | or • (the actual business name)
    text = re.split(r'[|•]', text)[0].strip()
    # Limit length to 40 chars (cut at word boundary)
    if len(text) > 40:
        text = text[:40].rsplit(' ', 1)[0]
    # Transliterate Hebrew characters to ASCII
    result = []
    for ch in text:
        if ch in HEBREW_TRANSLIT:
            result.append(HEBREW_TRANSLIT[ch])
        else:
            result.append(ch)
    text = ''.join(result)
    # Replace spaces and special chars with hyphens
    text = re.sub(r'[\s/\\:;,!?@#$%^&*()+=\[\]{}|<>\'\"•·]+', '-', text)
    # Remove any remaining non-ASCII, non-alphanumeric chars (except hyphens)
    text = re.sub(r'[^a-zA-Z0-9\-]', '', text)
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
    'קוסמטיקאית': [
        'https://images.unsplash.com/photo-1560066984-138dadb4c035?w=800',
        'https://images.unsplash.com/photo-1522337360788-8b13dee7a37e?w=800',
        'https://images.unsplash.com/photo-1487412912498-0447578fcca8?w=800',
        'https://images.unsplash.com/photo-1519494026892-80bbd2d6fd0d?w=800',
    ],
    'דיגיי': [
        'https://images.unsplash.com/photo-1571266028243-e4733b0f0bb0?w=800',
        'https://images.unsplash.com/photo-1493225457124-a3eb161ffa5f?w=800',
        'https://images.unsplash.com/photo-1470225620780-dba8ba36b745?w=800',
    ],
    'בית קפה': [
        'https://images.unsplash.com/photo-1501339847302-ac426a4a7cbb?w=800',
        'https://images.unsplash.com/photo-1559496417-e7f25cb247f3?w=800',
        'https://images.unsplash.com/photo-1554118811-1e0d58224f24?w=800',
    ],
    'סושי': [
        'https://images.unsplash.com/photo-1579871494447-9811cf80d66c?w=800',
        'https://images.unsplash.com/photo-1553621042-f6e147245754?w=800',
        'https://images.unsplash.com/photo-1617196034796-73dfa7b1fd56?w=800',
    ],
    'הפקת אירועים': [
        'https://images.unsplash.com/photo-1519167758481-83f550bb49b3?w=800',
        'https://images.unsplash.com/photo-1464366400600-7168b8af9bc3?w=800',
        'https://images.unsplash.com/photo-1478146059778-26028b07395a?w=800',
    ],
    'אולם אירועים': [
        'https://images.unsplash.com/photo-1519167758481-83f550bb49b3?w=800',
        'https://images.unsplash.com/photo-1464366400600-7168b8af9bc3?w=800',
        'https://images.unsplash.com/photo-1478146059778-26028b07395a?w=800',
    ],
    'פילאטיס': [
        'https://images.unsplash.com/photo-1518611012118-696072aa579a?w=800',
        'https://images.unsplash.com/photo-1571019613454-1cb2f99b2d8b?w=800',
        'https://images.unsplash.com/photo-1540497077202-7c8a3999166f?w=800',
    ],
    'ספא': [
        'https://images.unsplash.com/photo-1544161515-4ab6ce6db874?w=800',
        'https://images.unsplash.com/photo-1540555700478-4be289fbec6d?w=800',
        'https://images.unsplash.com/photo-1507652313519-d4e9174996dd?w=800',
    ],
    # English categories — category-specific Unsplash images
    'personal trainer': [
        'https://images.unsplash.com/photo-1534438327276-14e5300c3a48?w=800',
        'https://images.unsplash.com/photo-1571019613454-1cb2f99b2d8b?w=800',
        'https://images.unsplash.com/photo-1517836357463-d25dfeac3438?w=800',
        'https://images.unsplash.com/photo-1549060279-7e168fcee0c2?w=800',
    ],
    'barbershop': [
        'https://images.unsplash.com/photo-1503951914875-452162b0f3f1?w=800',
        'https://images.unsplash.com/photo-1599351431202-1e0f0137899a?w=800',
        'https://images.unsplash.com/photo-1621605815971-fbc98d665033?w=800',
        'https://images.unsplash.com/photo-1585747860715-2ba37e788b70?w=800',
    ],
    'air conditioning repair': [
        'https://images.unsplash.com/photo-1585338107529-13afc5f02586?w=800',
        'https://images.unsplash.com/photo-1504307651254-35680f356dfd?w=800',
        'https://images.unsplash.com/photo-1581578731548-c64695cc6952?w=800',
    ],
    'laser hair removal': [
        'https://images.unsplash.com/photo-1560066984-138dadb4c035?w=800',
        'https://images.unsplash.com/photo-1570172619644-dfd03ed5d881?w=800',
        'https://images.unsplash.com/photo-1522337360788-8b13dee7a37e?w=800',
        'https://images.unsplash.com/photo-1519494026892-80bbd2d6fd0d?w=800',
    ],
    'photography studio': [
        'https://images.unsplash.com/photo-1471341971476-ae15ff5dd4ea?w=800',
        'https://images.unsplash.com/photo-1542038784456-1ea8e935640e?w=800',
        'https://images.unsplash.com/photo-1452587925148-ce544e77e70d?w=800',
        'https://images.unsplash.com/photo-1554048612-b6a482bc67e5?w=800',
    ],
    'motorcycle repair': [
        'https://images.unsplash.com/photo-1558618666-fcd25c85f82e?w=800',
        'https://images.unsplash.com/photo-1558980394-4c7c9299fe96?w=800',
        'https://images.unsplash.com/photo-1449426468159-d96dbf08f19f?w=800',
    ],
    'reflexology': [
        'https://images.unsplash.com/photo-1544161515-4ab6ce6db874?w=800',
        'https://images.unsplash.com/photo-1519823551278-64ac92734fb1?w=800',
        'https://images.unsplash.com/photo-1600334089648-b0d9d3028eb2?w=800',
    ],
    'carpentry': [
        'https://images.unsplash.com/photo-1504148455328-c376907d081c?w=800',
        'https://images.unsplash.com/photo-1558618666-fcd25c85f82e?w=800',
        'https://images.unsplash.com/photo-1416339306562-f3d12fefd36f?w=800',
    ],
    'beauty salon': [
        'https://images.unsplash.com/photo-1560066984-138dadb4c035?w=800',
        'https://images.unsplash.com/photo-1522337360788-8b13dee7a37e?w=800',
        'https://images.unsplash.com/photo-1487412912498-0447578fcca8?w=800',
        'https://images.unsplash.com/photo-1519494026892-80bbd2d6fd0d?w=800',
    ],
    'catering': [
        'https://images.unsplash.com/photo-1555244162-803834f70033?w=800',
        'https://images.unsplash.com/photo-1414235077428-338989a2e8c0?w=800',
        'https://images.unsplash.com/photo-1517248135467-4c7edcad34c4?w=800',
        'https://images.unsplash.com/photo-1467003909585-2f8a72700288?w=800',
    ],
    'moving company': [
        'https://images.unsplash.com/photo-1600518464441-9154a4dea21b?w=800',
        'https://images.unsplash.com/photo-1558618666-fcd25c85f82e?w=800',
        'https://images.unsplash.com/photo-1504307651254-35680f356dfd?w=800',
    ],
    'bridal salon': [
        'https://images.unsplash.com/photo-1519741497674-611481863552?w=800',
        'https://images.unsplash.com/photo-1522413452208-996ff3f3e740?w=800',
        'https://images.unsplash.com/photo-1511285560929-80b456fea0bc?w=800',
        'https://images.unsplash.com/photo-1594552072238-b8a33785b261?w=800',
    ],
    'locksmith': [
        'https://images.unsplash.com/photo-1558618666-fcd25c85f82e?w=800',
        'https://images.unsplash.com/photo-1504307651254-35680f356dfd?w=800',
        'https://images.unsplash.com/photo-1581578731548-c64695cc6952?w=800',
    ],
    'massage': [
        'https://images.unsplash.com/photo-1544161515-4ab6ce6db874?w=800',
        'https://images.unsplash.com/photo-1519823551278-64ac92734fb1?w=800',
        'https://images.unsplash.com/photo-1600334089648-b0d9d3028eb2?w=800',
        'https://images.unsplash.com/photo-1515377905703-c4788e51af15?w=800',
    ],
    'tire shop': [
        'https://images.unsplash.com/photo-1487754180451-c456f719a1fc?w=800',
        'https://images.unsplash.com/photo-1625047509168-a7026f36de04?w=800',
        'https://images.unsplash.com/photo-1486262715619-67b85e0b08d3?w=800',
    ],
    'nail bar': [
        'https://images.unsplash.com/photo-1604654894610-df63bc536371?w=800',
        'https://images.unsplash.com/photo-1560066984-138dadb4c035?w=800',
        'https://images.unsplash.com/photo-1522337360788-8b13dee7a37e?w=800',
    ],
    'auto parts': [
        'https://images.unsplash.com/photo-1487754180451-c456f719a1fc?w=800',
        'https://images.unsplash.com/photo-1625047509168-a7026f36de04?w=800',
        'https://images.unsplash.com/photo-1486262715619-67b85e0b08d3?w=800',
    ],
    'cleaning service': [
        'https://images.unsplash.com/photo-1581578731548-c64695cc6952?w=800',
        'https://images.unsplash.com/photo-1558618666-fcd25c85f82e?w=800',
        'https://images.unsplash.com/photo-1504307651254-35680f356dfd?w=800',
    ],
    'tattoo parlor': [
        'https://images.unsplash.com/photo-1611501275019-9b5cda994e8d?w=800',
        'https://images.unsplash.com/photo-1590246814883-57c511c8c42c?w=800',
        'https://images.unsplash.com/photo-1598371839696-5c5bb1c12015?w=800',
    ],
    'insurance agent': [
        'https://images.unsplash.com/photo-1554224155-8d04cb21cd6c?w=800',
        'https://images.unsplash.com/photo-1460925895917-afdab827c52f?w=800',
        'https://images.unsplash.com/photo-1454165804606-c3d57bc86b40?w=800',
    ],
    'architect': [
        'https://images.unsplash.com/photo-1503387762-592deb58ef4e?w=800',
        'https://images.unsplash.com/photo-1488972685288-c3fd157d7c7a?w=800',
        'https://images.unsplash.com/photo-1487958449943-2429e8be8625?w=800',
    ],
    'gardening': [
        'https://images.unsplash.com/photo-1416879595882-3373a0480b5b?w=800',
        'https://images.unsplash.com/photo-1558904541-efa843a96f01?w=800',
        'https://images.unsplash.com/photo-1585320806297-9794b3e4eeae?w=800',
    ],
    'dance studio': [
        'https://images.unsplash.com/photo-1508700929628-666bc8bd84ea?w=800',
        'https://images.unsplash.com/photo-1547153760-18fc86324498?w=800',
        'https://images.unsplash.com/photo-1518834107812-67b0b7c58434?w=800',
    ],
    'hair salon': [
        'https://images.unsplash.com/photo-1521590832167-7bcbfaa6381f?w=800',
        'https://images.unsplash.com/photo-1560066984-138dadb4c035?w=800',
        'https://images.unsplash.com/photo-1622286342621-4bd786c2447c?w=800',
        'https://images.unsplash.com/photo-1559599101-f09722fb4948?w=800',
    ],
    'interior design': [
        'https://images.unsplash.com/photo-1618221195710-dd6b41faaea6?w=800',
        'https://images.unsplash.com/photo-1586023492125-27b2c045efd7?w=800',
        'https://images.unsplash.com/photo-1616486338812-3dadae4b4ace?w=800',
    ],
    'glass repair': [
        'https://images.unsplash.com/photo-1558618666-fcd25c85f82e?w=800',
        'https://images.unsplash.com/photo-1504307651254-35680f356dfd?w=800',
        'https://images.unsplash.com/photo-1581578731548-c64695cc6952?w=800',
    ],
    'accountant': [
        'https://images.unsplash.com/photo-1554224155-8d04cb21cd6c?w=800',
        'https://images.unsplash.com/photo-1460925895917-afdab827c52f?w=800',
        'https://images.unsplash.com/photo-1454165804606-c3d57bc86b40?w=800',
    ],
    'physiotherapy': [
        'https://images.unsplash.com/photo-1576091160399-112ba8d25d1d?w=800',
        'https://images.unsplash.com/photo-1519823551278-64ac92734fb1?w=800',
        'https://images.unsplash.com/photo-1544161515-4ab6ce6db874?w=800',
    ],
    'spa': [
        'https://images.unsplash.com/photo-1540555700478-4be289fbec6d?w=800',
        'https://images.unsplash.com/photo-1544161515-4ab6ce6db874?w=800',
        'https://images.unsplash.com/photo-1507652313519-d4e9174996dd?w=800',
    ],
    'ice cream shop': [
        'https://images.unsplash.com/photo-1497034825429-c343d7c6a68f?w=800',
        'https://images.unsplash.com/photo-1501443762994-82bd5dace89a?w=800',
        'https://images.unsplash.com/photo-1517093728432-a0440f8d45af?w=800',
    ],
    'bakery': [
        'https://images.unsplash.com/photo-1509440159596-0249088772ff?w=800',
        'https://images.unsplash.com/photo-1517433367423-f7e136d2c4e0?w=800',
        'https://images.unsplash.com/photo-1555507036-ab1f4038024a?w=800',
    ],
    'juice bar': [
        'https://images.unsplash.com/photo-1622597467836-f3285f2131b8?w=800',
        'https://images.unsplash.com/photo-1589733955941-5eeaf752f6dd?w=800',
        'https://images.unsplash.com/photo-1600271886742-f049cd451bba?w=800',
    ],
    'jewelry store': [
        'https://images.unsplash.com/photo-1515562141207-7a88fb7ce338?w=800',
        'https://images.unsplash.com/photo-1573408301185-9146fe634ad0?w=800',
        'https://images.unsplash.com/photo-1602751584552-8ba73aad10e1?w=800',
    ],
    'dermatology clinic': [
        'https://images.unsplash.com/photo-1576091160399-112ba8d25d1d?w=800',
        'https://images.unsplash.com/photo-1579684385127-1ef15d508118?w=800',
        'https://images.unsplash.com/photo-1519494026892-80bbd2d6fd0d?w=800',
    ],
    'chiropractor': [
        'https://images.unsplash.com/photo-1576091160399-112ba8d25d1d?w=800',
        'https://images.unsplash.com/photo-1519823551278-64ac92734fb1?w=800',
        'https://images.unsplash.com/photo-1544161515-4ab6ce6db874?w=800',
    ],
    'DEFAULT': [
        'https://images.unsplash.com/photo-1497366216548-37526070297c?w=800',
        'https://images.unsplash.com/photo-1497366811353-6870744d04b2?w=800',
        'https://images.unsplash.com/photo-1497215728101-856f4ea42174?w=800',
    ],
}


# Category-specific Hebrew testimonials — 3 per category group
TESTIMONIALS_BY_GROUP = {
    'beauty': [
        ('דנה ל.', 'ד', '"הגעתי בפעם הראשונה ומיד הרגשתי בבית. מקצועיות ברמה אחרת, תוצאות מדהימות. ממליצה בחום!"'),
        ('שירה כ.', 'ש', '"כבר שנה שאני מטופלת כאן ולא מוכנה להחליף. יחס אישי, ניקיון ותוצאות שמדברות בעד עצמן."'),
        ('מיכל א.', 'מ', '"השירות הכי טוב שקיבלתי. מקשיבים, מבינים בדיוק מה צריך, ותמיד יוצאת מרוצה. תודה!"'),
    ],
    'food': [
        ('אלון מ.', 'א', '"אוכל מעולה, מנות טריות ושירות חם. אחד המקומות האהובים עלינו באזור!"'),
        ('רוני ש.', 'ר', '"הזמנו קייטרינג לאירוע משפחתי — כולם שאלו מאיפה האוכל. פשוט מושלם."'),
        ('יעל ד.', 'י', '"ביקרנו כבר כמה פעמים וכל פעם מחדש מופתעים מהאיכות. מקום שחייבים לנסות."'),
    ],
    'health': [
        ('דוד כ.', 'ד', '"אחרי טיפול אחד כבר הרגשתי שיפור משמעותי. ידיים מקצועיות ויחס אישי."'),
        ('נעמי ר.', 'נ', '"המטפל מקצועי ברמה גבוהה מאוד. מקשיב, מסביר, ובאמת עוזר. ממליצה!"'),
        ('אורי ת.', 'א', '"כבר חצי שנה שאני מטופל ורואה תוצאות מדהימות. שינה לי את החיים."'),
    ],
    'home': [
        ('משה ב.', 'מ', '"עבודה מקצועית, מדויקת ובזמן. הגיע, העריך, ביצע — הכל כמו שהובטח."'),
        ('רחל ס.', 'ר', '"שירות אמין ומהיר. הגיע תוך שעה ופתר את הבעיה. מומלץ בחום!"'),
        ('יוסי ל.', 'י', '"עבודה נקייה ומקצועית. מחיר הוגן ותוצאה מצוינת. נשתמש שוב בוודאות."'),
    ],
    'professional': [
        ('שרון מ.', 'ש', '"ליווי מקצועי מהרגע הראשון. מסביר בסבלנות, זמין תמיד, ותוצאות מעולות."'),
        ('גיל ע.', 'ג', '"משרד מקצועי ואמין. טיפלו בעניין שלי ביעילות ובמסירות. ממליץ!"'),
        ('תמר ח.', 'ת', '"שירות ברמה גבוהה, יחס אישי ותוצאות. בדיוק מה שחיפשנו."'),
    ],
    'fitness': [
        ('עמית ר.', 'ע', '"מאמן מעולה! מתאים את התוכנית בדיוק בשבילי. רואה תוצאות כבר אחרי חודש."'),
        ('ליאת כ.', 'ל', '"אווירה נהדרת, מקצועיות ויחס אישי. המקום האהוב עליי לאימון."'),
        ('נדב ש.', 'נ', '"הגעתי אחרי פציעה וחזרתי לכושר מלא. מקצוען אמיתי. תודה!"'),
    ],
    'creative': [
        ('יונתן ב.', 'י', '"עבודה מרשימה ויצירתית. הבינו בדיוק מה רציתי והתוצאה עלתה על הציפיות."'),
        ('מיה ד.', 'מ', '"מקצועיות, יצירתיות ותשומת לב לכל פרט. פשוט אומנות."'),
        ('אופיר א.', 'א', '"עבודה ברמה גבוהה מאוד. שירות אישי ותוצאות שמדברות בעד עצמן."'),
    ],
    'default': [
        ('אבי כ.', 'א', '"שירות מעולה ומקצועי. ממליץ בחום לכל מי שמחפש איכות ואמינות."'),
        ('מיכל ש.', 'מ', '"תשומת לב לפרטים, מקצועיות ברמה גבוהה ויחס אישי. הכי טוב שיש באזור."'),
        ('רונית ד.', 'ר', '"כבר שנים שאנחנו לקוחות קבועים ולא מוכנים להחליף. מקום אמין ומומלץ."'),
    ],
}

# Map categories to testimonial groups
CATEGORY_TESTIMONIAL_GROUP = {
    'beauty salon': 'beauty', 'hair salon': 'beauty', 'barbershop': 'beauty',
    'nail bar': 'beauty', 'laser hair removal': 'beauty', 'bridal salon': 'beauty',
    'מכון יופי': 'beauty', 'מספרה': 'beauty', 'קוסמטיקאית': 'beauty', 'ספא': 'beauty', 'spa': 'beauty',
    'tattoo parlor': 'beauty',
    'מסעדה': 'food', 'קונדיטוריה': 'food', 'מאפייה': 'food', 'בית קפה': 'food',
    'שווארמה': 'food', 'סושי': 'food', 'פיצריה': 'food',
    'catering': 'food', 'bakery': 'food', 'butcher shop': 'food', 'fish market': 'food',
    'ice cream shop': 'food', 'juice bar': 'food', 'grocery store': 'food',
    'massage': 'health', 'reflexology': 'health', 'physiotherapy': 'health',
    'chiropractor': 'health', 'dermatology clinic': 'health', 'dietitian': 'health',
    'רופא שיניים': 'health', 'dental lab': 'health',
    'חשמלאי': 'home', 'אינסטלטור': 'home', 'שיפוצים': 'home',
    'air conditioning repair': 'home', 'locksmith': 'home', 'cleaning service': 'home',
    'carpentry': 'home', 'gardening': 'home', 'landscaping': 'home',
    'glass repair': 'home', 'glazier': 'home', 'blinds shutters': 'home',
    'flooring tiles': 'home', 'welding': 'home', 'upholstery': 'home',
    'moving company': 'home', 'הובלות': 'home',
    'רואה חשבון': 'professional', 'עורך דין': 'professional',
    'accountant': 'professional', 'insurance agent': 'professional',
    'mortgage advisor': 'professional', 'pension advisor': 'professional',
    'traffic lawyer': 'professional', 'divorce lawyer': 'professional',
    'architect': 'professional', 'interior design': 'professional',
    'personal trainer': 'fitness', 'מכון כושר': 'fitness',
    'פילאטיס': 'fitness', 'יוגה': 'fitness', 'dance studio': 'fitness',
    'צלם': 'creative', 'צילום': 'creative', 'photography studio': 'creative',
    'graphic design': 'creative', 'עיצוב גרפי': 'creative',
    'מוסך': 'home', 'motorcycle repair': 'home', 'tire shop': 'home',
    'auto parts': 'home', 'car appraiser': 'home',
}


def build_testimonials_html(category):
    """Generate 3 category-specific testimonial cards."""
    group = CATEGORY_TESTIMONIAL_GROUP.get(category, 'default')
    testimonials = TESTIMONIALS_BY_GROUP.get(group, TESTIMONIALS_BY_GROUP['default'])
    cards = ''
    for i, (name, initial, text) in enumerate(testimonials):
        delay = i + 1
        cards += f'''      <div class="testimonial-card reveal reveal-delay-{delay}">
        <div class="testimonial-stars">
          <div class="star"></div><div class="star"></div><div class="star"></div><div class="star"></div><div class="star"></div>
        </div>
        <p class="testimonial-text">{text}</p>
        <div class="testimonial-author">
          <div class="testimonial-avatar">{initial}</div>
          <div class="testimonial-name">{name}</div>
        </div>
      </div>
'''
    return cards


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

    # Rating: prefer enrichment, fallback to CSV
    rating = enrichment.get('rating', '') or lead.get('rating', '')
    html = html.replace('{{RATING}}', str(rating) if rating else '')

    # Reviews count: prefer enrichment, fallback to CSV
    reviews_count = enrichment.get('reviews_count', '') or lead.get('reviews', '')
    html = html.replace('{{REVIEWS_COUNT}}', str(reviews_count) if reviews_count else '')

    # Category-specific text placeholders (for universal template)
    config = CATEGORY_CONFIG.get(category, DEFAULT_CATEGORY_CONFIG)
    html = html.replace('{{BADGE_TEXT}}', config['badge'])
    html = html.replace('{{CTA_TEXT}}', config['cta'])
    html = html.replace('{{HERO_SUBTITLE}}', config['subtitle'])
    html = html.replace('{{ABOUT_TITLE}}', config['about_title'])
    html = html.replace('{{ABOUT_DESC}}', config['about_desc'])
    html = html.replace('{{SERVICES_LABEL}}', config['services_label'])

    # OG meta tags for WhatsApp link previews
    og_desc = f"{config['badge']} — {short_name} ב{lead['city']}. {config['subtitle']}"
    html = html.replace('{{OG_DESCRIPTION}}', og_desc)
    # Use first photo as OG image (Google Places or fallback)
    photo_urls_for_og = enrichment.get('photo_urls', [])
    og_fallbacks = UNSPLASH_FALLBACKS.get(category, UNSPLASH_FALLBACKS.get('DEFAULT', []))
    og_image = photo_urls_for_og[0] if photo_urls_for_og else (og_fallbacks[0] if og_fallbacks else '')
    html = html.replace('{{OG_IMAGE}}', og_image)

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

    # Opening hours card
    weekday_text = enrichment.get('hours_weekday_text', [])
    if weekday_text:
        day_names_he = {'Sunday': 'ראשון', 'Monday': 'שני', 'Tuesday': 'שלישי',
                        'Wednesday': 'רביעי', 'Thursday': 'חמישי', 'Friday': 'שישי', 'Saturday': 'שבת'}
        import datetime as _dt
        today_idx = _dt.datetime.now().weekday()  # 0=Mon
        # Google returns Sun-first (0=Sun), Python weekday 0=Mon
        today_google = (today_idx + 1) % 7  # convert to Sun=0
        hours_rows = []
        for i, line in enumerate(weekday_text):
            cls = ' today' if i == today_google else ''
            parts = line.split(': ', 1)
            day = day_names_he.get(parts[0], parts[0]) if len(parts) > 1 else parts[0]
            time_str = parts[1] if len(parts) > 1 else ''
            hours_rows.append(f'<div class="hours-row{cls}"><span>{day}</span><span>{time_str}</span></div>')
        hours_html = (
            '<div class="hours-card">'
            '<div class="hours-title">🕐 שעות פתיחה</div>'
            + '\n'.join(hours_rows) +
            '</div>'
        )
    else:
        hours_html = ''
    html = html.replace('{{HOURS_SECTION}}', hours_html)

    # Reviews — build real reviews HTML section
    reviews = enrichment.get('reviews', [])
    if reviews:
        reviews_html = build_reviews_section(reviews)
    else:
        reviews_html = ''
    html = html.replace('{{REVIEWS_SECTION}}', reviews_html)

    # Category-specific testimonials
    testimonials_html = build_testimonials_html(category)
    html = html.replace('{{TESTIMONIALS_HTML}}', testimonials_html)

    # Legal disclaimer — protection against impersonation claims
    disclaimer_html = (
        '<div style="background:#f5f5f5;border-top:1px solid #ddd;padding:16px 20px;'
        'text-align:center;font-family:Heebo,Arial,sans-serif;direction:rtl;'
        'font-size:12px;color:#999;line-height:1.6;">'
        'אתר לדוגמא בלבד — נבנה על ידי '
        '<a href="https://alondev.site" style="color:#0f3460;">alon dev</a>'
        ' כהצעה עסקית. אינו מייצג את העסק באופן רשמי. '
        'המידע נאסף ממקורות ציבוריים (Google Maps). '
        '<a href="https://output-seven-black.vercel.app/terms/" style="color:#0f3460;">תנאי שימוש</a>'
        '<br>לבקשת הסרה מיידית: '
        '<a href="https://wa.me/972559566148?text=בקשת%20הסרה%20-%20' + short_name.replace(' ', '%20') + '" style="color:#25D366;">'
        '055-956-6148</a>'
        '</div>'
    )

    # Inject map before footer
    html = html.replace('<!-- Footer -->', f'{map_html}\n\n{disclaimer_html}\n\n<!-- Footer -->')

    # Tracking pixel — fires when someone opens the page + time on site
    tracking_pixel = (
        f'<script>'
        f'(function(){{'
        f'var p="{phone_clean}",n=encodeURIComponent("{short_name}"),base="https://output-seven-black.vercel.app/api/track";'
        f'var img=new Image();'
        f'img.src=base+"?phone="+p+"&name="+n+"&t="+Date.now();'
        f'var start=Date.now();'
        f'setInterval(function(){{'
        f'var s=Math.round((Date.now()-start)/1000);'
        f'var ping=new Image();'
        f'ping.src=base+"?phone="+p+"&name="+n+"&event=time_on_site&seconds="+s+"&t="+Date.now();'
        f'}},10000);'
        f'}})()'
        f'</script>'
    )

    # Google Analytics 4 (GA4)
    ga4_id = os.environ.get('GA4_MEASUREMENT_ID', '')
    ga4_code = ''
    if ga4_id:
        ga4_code = (
            f'<!-- Google Analytics 4 -->'
            f'<script async src="https://www.googletagmanager.com/gtag/js?id={ga4_id}"></script>'
            f'<script>'
            f'window.dataLayer=window.dataLayer||[];'
            f'function gtag(){{dataLayer.push(arguments)}}'
            f"gtag('js',new Date());"
            f"gtag('config','{ga4_id}',{{"
            f"page_title:'{short_name}',"
            f"custom_map:{{'dimension1':'business_phone','dimension2':'business_category'}},"
            f"business_phone:'{phone_clean}',"
            f"business_category:'{lead.get('category', '')}'"
            f"}});"
            f'</script>'
            f'<!-- End GA4 -->'
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

    html = html.replace('</head>', f'{ga4_code}\n</head>')
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

    # Filter: no website only (leads_final.csv already pre-filtered — all are no-website)
    has_website_col = any(r.get('has_website', '') for r in leads)
    if has_website_col:
        no_website = [r for r in leads if r.get('has_website', '').strip().lower() == 'no']
    else:
        no_website = leads  # Already filtered by enrichment pipeline

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
        cat_en = CATEGORY_MAP.get(cat_heb, 'universal')
        template_html = templates.get(cat_heb) or load_template(cat_en)
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
