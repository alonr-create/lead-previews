#!/usr/bin/env python3
"""
Add sales popup to all landing pages with A/B/C pricing.
- 3 groups of ~400 sites, each with different price
- Group A: 149₪, Group B: 249₪, Group C: 369₪
- All show ~~1,490₪~~ crossed out ("שאגת הארי" discount)
- Links directly to Grow payment page
"""
import re
import hashlib
import base64
from pathlib import Path

# Load lion image as base64 for inline embedding
_lion_path = Path(__file__).parent.parent / "Downloads" / "download.jpeg"
if not _lion_path.exists():
    _lion_path = Path.home() / "Downloads" / "download.jpeg"
LION_B64 = base64.b64encode(_lion_path.read_bytes()).decode() if _lion_path.exists() else ""

OUTPUT_DIR = Path(__file__).parent / "output"

GROW_LINKS = {
    'A': 'https://pay.grow.link/4b6de7b3263b90d9f092e025b4004e59-MzIzMzQ3Mw',
    'B': 'https://pay.grow.link/f7a9d917ba9636410be7d82bd2bacbd5-MzIzMzY2Ng',
    'C': 'https://pay.grow.link/a0fd8bc23807318c4f65535166f4209c-MzIzMzY2OQ',
}

PRICES = {
    'A': {'sale': '149', 'discount': '90%'},
    'B': {'sale': '249', 'discount': '83%'},
    'C': {'sale': '369', 'discount': '75%'},
}


def get_group(slug):
    """Deterministic A/B/C assignment based on slug hash."""
    h = int(hashlib.md5(slug.encode()).hexdigest(), 16)
    return ['A', 'B', 'C'][h % 3]


def make_popup(group):
    price = PRICES[group]
    link = GROW_LINKS[group]
    lion_img = f'data:image/jpeg;base64,{LION_B64}' if LION_B64 else ''
    return f'''
<!-- Sales Popup -->
<style>
.sale-overlay{{position:fixed;inset:0;background:rgba(0,0,0,0.6);z-index:100000;display:none;align-items:center;justify-content:center;padding:16px;backdrop-filter:blur(4px);-webkit-backdrop-filter:blur(4px)}}
.sale-overlay.show{{display:flex}}
.sale-box{{background:#fff;border-radius:20px;max-width:420px;width:100%;padding:0;overflow:hidden;position:relative;direction:rtl;font-family:'Heebo',sans-serif;animation:popIn 0.4s cubic-bezier(0.34,1.56,0.64,1);box-shadow:0 20px 60px rgba(0,0,0,0.3)}}
@keyframes popIn{{0%{{transform:scale(0.8);opacity:0}}100%{{transform:scale(1);opacity:1}}}}
.sale-top{{background:linear-gradient(135deg,#1a365d,#0f172a);padding:20px 24px;text-align:center;position:relative;display:flex;flex-direction:column;align-items:center}}
.sale-top::after{{content:'';position:absolute;bottom:-12px;left:50%;transform:translateX(-50%);width:0;height:0;border-left:14px solid transparent;border-right:14px solid transparent;border-top:14px solid #0f172a}}
.sale-lion{{width:auto;height:70px;border-radius:12px;object-fit:contain;margin-bottom:10px}}
.sale-badge{{display:inline-block;background:rgba(59,130,246,0.3);color:#fff;font-size:13px;font-weight:700;padding:5px 18px;border-radius:100px;letter-spacing:1px;margin-bottom:8px}}
.sale-headline{{color:#1e293b;font-size:20px;font-weight:800;line-height:1.4;margin:0 0 12px}}
.sale-body{{padding:28px 24px 24px;text-align:center}}
.sale-reason{{font-size:15px;color:#64748b;line-height:1.7;margin-bottom:16px}}
.sale-reason strong{{color:#1e293b}}
.sale-prices{{display:flex;justify-content:center;gap:20px;margin-bottom:16px;align-items:center}}
.sale-price-item{{text-align:center}}
.sale-price-old{{font-size:18px;color:#94a3b8;text-decoration:line-through}}
.sale-price-new{{font-size:36px;font-weight:800;color:#dc2626;line-height:1}}
.sale-price-per{{font-size:12px;color:#94a3b8;margin-top:2px}}
.sale-discount{{background:#fef2f2;color:#dc2626;font-weight:800;font-size:14px;padding:4px 12px;border-radius:8px}}
.sale-timer{{display:flex;align-items:center;justify-content:center;gap:8px;margin-bottom:20px;font-size:14px;color:#64748b}}
.sale-timer-val{{background:#eff6ff;color:#1d4ed8;font-weight:800;font-size:18px;padding:4px 10px;border-radius:8px;font-variant-numeric:tabular-nums;direction:ltr}}
.sale-cta{{display:block;width:100%;padding:16px;background:linear-gradient(135deg,#2563eb,#1d4ed8);color:#fff;border:none;border-radius:14px;font-size:18px;font-weight:700;font-family:'Heebo',sans-serif;cursor:pointer;text-decoration:none;text-align:center;transition:all 0.3s;box-shadow:0 4px 16px rgba(37,99,235,0.3)}}
.sale-cta:hover{{transform:translateY(-2px);box-shadow:0 8px 24px rgba(37,99,235,0.4)}}
.sale-sub{{font-size:12px;color:#94a3b8;margin-top:12px;display:flex;justify-content:center;gap:16px}}
.sale-close{{position:absolute;top:12px;left:12px;background:rgba(255,255,255,0.2);border:none;color:#fff;width:30px;height:30px;border-radius:50%;font-size:18px;cursor:pointer;display:flex;align-items:center;justify-content:center;transition:background 0.2s;z-index:1}}
.sale-close:hover{{background:rgba(255,255,255,0.4)}}
@media(max-width:480px){{.sale-headline{{font-size:16px}}.sale-price-new{{font-size:28px}}.sale-box{{margin:0 8px}}.sale-lion{{height:50px}}}}
</style>
<div class="sale-overlay" id="salePopup">
<div class="sale-box">
<div class="sale-top">
<button class="sale-close" onclick="document.getElementById('salePopup').classList.remove('show')">&times;</button>
<img class="sale-lion" src="{lion_img}" alt="">
<div class="sale-badge">מבצע שאגת הארי</div>
</div>
<div class="sale-body">
<div class="sale-headline">העסק שלך חייב נוכחות דיגיטלית.<br>במיוחד עכשיו.</div>
<div class="sale-reason">
בזמן שהמדינה נלחמת — <strong>העסק שלך צריך להמשיך לרוץ.</strong><br>
האתר הזה כבר מוכן בשבילך. רק צריך להפעיל אותו.
</div>
<div class="sale-prices">
<div class="sale-price-item">
<div class="sale-price-old">1,490 &#8362;</div>
<div class="sale-price-new">{price['sale']} &#8362;</div>
<div class="sale-price-per">חד-פעמי</div>
</div>
<div class="sale-discount">{price['discount']} הנחה</div>
</div>
<div class="sale-timer">
<span>המבצע נגמר בעוד</span>
<span class="sale-timer-val" id="popupTimer">23:59:59</span>
</div>
<a class="sale-cta" id="popupCta" href="{link}">
אני רוצה את האתר הזה &larr;
</a>
<div class="sale-sub">
<span>&#128274; תשלום מאובטח</span>
<span>&#9889; האתר שלך תוך 24 שעות</span>
</div>
</div>
</div>
</div>
<script>
(function(){{
var pp=document.getElementById('salePopup');
var shown=sessionStorage.getItem('popup_shown');
if(!shown){{
setTimeout(function(){{pp.classList.add('show');sessionStorage.setItem('popup_shown','1')}},8000);
}}
pp.addEventListener('click',function(e){{if(e.target===pp)pp.classList.remove('show')}});
var key='popup_timer';var stored=localStorage.getItem(key);var deadline;
if(stored&&parseInt(stored)>Date.now()){{deadline=parseInt(stored)}}
else{{deadline=Date.now()+86400000;localStorage.setItem(key,deadline.toString())}}
setInterval(function(){{
var diff=Math.max(0,deadline-Date.now());
var h=Math.floor(diff/3600000),m=Math.floor((diff%3600000)/60000),s=Math.floor((diff%60000)/1000);
var el=document.getElementById('popupTimer');
if(el)el.textContent=(h<10?'0':'')+h+':'+(m<10?'0':'')+m+':'+(s<10?'0':'')+s;
}},1000);
var bannerCta=document.querySelector('.lp-banner-cta');
if(bannerCta){{
bannerCta.href='{link}';
bannerCta.textContent='לקבלת האתר \\u2190';
}}
}})();
</script>
<!-- End Sales Popup -->
'''


def add_popup(html_path, group):
    html = html_path.read_text(encoding='utf-8', errors='ignore')

    # Remove old popup if exists
    if 'salePopup' in html:
        html = re.sub(r'<!-- Sales Popup -->.*?<!-- End Sales Popup -->', '', html, flags=re.DOTALL)

    popup = make_popup(group)

    if '</body>' in html:
        html = html.replace('</body>', popup + '\n</body>')
    else:
        html += popup

    html_path.write_text(html, encoding='utf-8')
    return True


def main():
    groups = {'A': 0, 'B': 0, 'C': 0}
    skipped = 0

    for d in sorted(OUTPUT_DIR.iterdir()):
        if not d.is_dir() or d.name.startswith('.'):
            continue
        index = d / 'index.html'
        if not index.exists():
            continue
        photo1 = d / 'photo_1.jpg'
        if not photo1.exists() or photo1.stat().st_size < 1000:
            skipped += 1
            continue

        group = get_group(d.name)
        add_popup(index, group)
        groups[group] += 1

    total = sum(groups.values())
    print(f"Updated: {total} sites")
    print(f"  Group A (149₪): {groups['A']} sites")
    print(f"  Group B (249₪): {groups['B']} sites")
    print(f"  Group C (369₪): {groups['C']} sites")
    print(f"Skipped: {skipped} sites (no photos)")


if __name__ == "__main__":
    main()
