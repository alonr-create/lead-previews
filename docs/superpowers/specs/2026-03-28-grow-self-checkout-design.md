# Grow Self-Checkout — A/B/C Price Test

## Overview
Add Grow (Meshulam) payment to all 4,573 preview sites. Leads see their pre-built website, pay online, done. Zero sales calls needed.

## Product
One-time purchase: a ready-made landing page hosted on Vercel forever. No monthly fees, no renewal.

## Pricing — A/B/C Test

| Group | Strikethrough | Sale Price | Discount | Leads |
|-------|--------------|------------|----------|-------|
| A     | ~~1,490~~    | **149**    | 90%      | 400   |
| B     | ~~1,490~~    | **249**    | 83%      | 400   |
| C     | ~~1,490~~    | **349**    | 77%      | 400   |

Test pool: 1,200 leads from the 1,309 "personal photo" group in Monday.com.
Remaining 109 held as control/reserve.

## Messaging
Theme: solidarity discount during wartime.
Hebrew copy: "לרגל המצב, Alon.dev רוצה לעזור לעסקים קטנים — 90% הנחה על עמוד נחיתה מקצועי"

## Lead Flow

### Step 1 — Voice Agent Call
- Yael (Voice Agent) calls the lead
- Script: "היי [שם], כאן יעל מ-Alon.dev. בנינו עמוד נחיתה מקצועי לעסק שלך — עם התמונות האמיתיות מגוגל. אני שולחת לך עכשיו לינק בוואטסאפ, תסתכל ותגיד לי מה אתה חושב"
- Tool: `send_whatsapp` with site link + offer

### Step 2 — WhatsApp Follow-up (automatic)
Message template:
```
היי [שם]! הנה עמוד הנחיתה שבנינו לעסק שלך:
[link]

לרגל המצב — [discount]% הנחה!
במקום ₪1,490 → רק ₪[price]

👉 לרכישה: [checkout_link]
```

### Step 3 — Site Banner (sticky top)
Every preview site gets a sticky top banner:
- Hebrew, RTL
- Shows: strikethrough price, sale price, discount %, CTA button
- Button links to `/checkout.html` in same directory
- Banner color: warm gradient (gold/orange) to stand out

### Step 4 — Checkout Page
- `/checkout.html` in each site directory
- Grow iframe/redirect for payment
- Fields: name, phone, email, credit card (handled by Grow)
- Amount based on A/B/C group assignment
- Success redirect: thank you page

### Step 5 — Post-Payment
1. **WhatsApp confirmation** to customer: "תודה [שם]! האתר שלך פעיל"
2. **Telegram alert** to Alon with payment details
3. **Monday.com update**: status → "שילם", payment amount logged
4. **Banner change**: remove sale banner or replace with "האתר שלך פעיל"

## Technical Implementation

### Banner Injection
- Script that adds sticky banner HTML/CSS to all `index.html` files
- Banner reads price from a config (data attribute or JS variable)
- A/B/C group assignment stored in Monday.com or a JSON mapping file

### Checkout Page
- Static HTML with Grow payment form
- Each site's checkout.html has the correct amount baked in
- Grow webhook on payment success → triggers post-payment flow

### A/B/C Group Assignment
- 1,309 leads with personal photos, sorted randomly
- First 400 → Group A (₪149)
- Next 400 → Group B (₪249)
- Next 400 → Group C (₪349)
- Remaining 109 → reserve
- Assignment stored in Monday.com column or JSON file

### Grow Integration
- Payment page: iframe or redirect to Grow hosted page
- Webhook: Grow sends payment confirmation to our endpoint
- Endpoint: updates Monday.com + sends WA + Telegram alert

## Measurement (after 1 week)

| Metric | How |
|--------|-----|
| Conversion rate | Payments / leads contacted per group |
| Revenue per lead | Total revenue / leads contacted per group |
| Winner | Highest revenue per lead |
| Scale decision | Winner rate × remaining leads = projected revenue |

## Revenue Projections

### Test Phase (1,200 leads)
- Conservative (2%): ~₪6,000
- Average (3.5%): ~₪10,000
- Optimistic (5%): ~₪15,000

### Scale Phase (all 4,573 leads with winner price)
- Conservative (1.5%): ~₪17,000
- Average (3%): ~₪34,000
- Optimistic (5%): ~₪57,000

## Upsells (Phase 2 — not in this spec)
- Custom domain: ₪199/year
- Custom design: ₪499
- Google Business Profile setup: ₪299
- Monthly maintenance: ₪49/month

## Out of Scope
- Monthly subscriptions / renewals
- Automatic domain provisioning
- Custom design modifications pre-purchase
- Email outreach (WA + Voice Agent only for now)
