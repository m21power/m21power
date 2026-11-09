'''
RUN: python3 update_stats.py - TO UPDATE THE VALUES
'''
#!/usr/bin/env python3
"""Refresh live Google Play data: rewrites assets/stats.svg and the app cards in README.md."""
import json, os, re, urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
README = ROOT / "README.md"
STATS = ROOT / "assets" / "stats.svg"
CACHE = ROOT / "assets" / "app.json"

APPS = [
    {"id": "app.mesay.mezgebe_sibhat", "name": "Mezgebe Sibhat", "local": "መዝገበ ስብሐት",
     "desc": "Offline audio lessons for traditional Abinet education: Qidase, Wereb, Kidan and more. Download once, learn anywhere."},
    {"id": "app.mesay.mahiletzekidusyared", "name": "Mahlet Ze-Kidus Yared", "local": "ማሕሌት ዘቅዱስ ያሬድ",
     "desc": "The complete Mahlet and Wazema liturgy in Ge'ez: 100+ feast-day services, organized by Ethiopian month and feast."},
    {"id": "app.mesay.mezmuredawit", "name": "Mezmure Dawit", "local": "መዝሙረ ዳዊት ወ ግጻዌ",
     "desc": "The Psalms of David and Getsawe in one app, with a built-in audio player for reading and listening."},
]

MOCK = {
    "app.mesay.mezgebe_sibhat": {"installs": 10000, "score": 4.2, "reviews": 42, "icon": "https://play-lh.googleusercontent.com/fDBfdUcvXrg2yS2RYdonbagkEc1r6sNWQJ8irT2VoJqXbZS8F-KV_J97-YoE1N-4I_LCfiDulnEfJF-EOVjClg=w240-h480"},
    "app.mesay.mahiletzekidusyared": {"installs": 1000, "score": 4.9, "reviews": 53, "icon": "https://play-lh.googleusercontent.com/DnaJhVtNF4Nk68ItZ27JaxifRLnJU-P6HXZ7D6rh9Kdsbc2TzwfwcIqeb4y7uVihe9ZtK_8AmZ1g8xlCxk7kxA=w240-h480"},
    "app.mesay.mezmuredawit": {"installs": 1000, "score": 4.7, "reviews": 35, "icon": "https://play-lh.googleusercontent.com/nivETPt7CRUErLrAmAInrT7cd2jnPwpcEQgOuvP7k-mUrPnMDww0pIBr8Fc7S8smUSy2L2Ad6ee8AFDmp0kz=w240-h480"},
}


def parse_count(text):
    text = text.replace(",", "").strip()
    mult = {"K": 1_000, "M": 1_000_000, "B": 1_000_000_000}
    if text and text[-1].upper() in mult:
        return int(float(text[:-1]) * mult[text[-1].upper()])
    return int(float(text))


def parse_play_html(html):
    """Best-effort extraction of rating and review count from the raw Play page."""
    out = {}
    m = (re.search(r'"ratingValue"\s*:\s*"?([\d.]+)', html)
         or re.search(r'Rated ([\d.]+) stars', html)
         or re.search(r'>\s*([1-5](?:\.\d)?)\s*<[^>]*>\s*star', html))
    if m:
        out["score"] = float(m.group(1))
    m = (re.search(r'>\s*([\d.,]+[KMB]?)\s+reviews?\s*<', html)
         or re.search(r'([\d.,]+[KMB]?)\s+reviews', html)
         or re.search(r'"(?:ratingCount|reviewCount)"\s*:\s*"?(\d+)', html))
    if m:
        try:
            out["reviews"] = parse_count(m.group(1))
        except ValueError:
            pass
    return out


def scrape_html(app_id):
    import urllib.request
    url = f"https://play.google.com/store/apps/details?id={app_id}&hl=en_US&gl=US"
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9"})
    html = urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "ignore")
    return parse_play_html(html)


def fetch(app_id):
    if os.environ.get("MOCK"):
        return MOCK[app_id]
    from google_play_scraper import app
    r = app(app_id, lang="en", country="us")
    installs = r.get("minInstalls")
    if not installs and r.get("installs"):  # e.g. "10,000+"
        digits = re.sub(r"[^\d]", "", r["installs"])
        installs = int(digits) if digits else None
    result = {"installs": installs, "score": r.get("score"), "reviews": r.get("reviews") or r.get("ratings"),
              "icon": r.get("icon")}
    if not result["score"] or not result["reviews"]:  # library came back empty: read the page directly
        try:
            for k, v in scrape_html(app_id).items():
                if not result.get(k):
                    result[k] = v
        except Exception as e:
            print(f"warn: {app_id}: html fallback failed: {e}")
    return result


def fmt(n):
    if n >= 1_000_000:
        return f"{n / 1_000_000:g}M+"
    if n >= 1_000:
        return f"{n // 1_000}K+"
    return f"{n}+"


def circle(icon):
    base = re.sub(r"=[^/]*$", "", icon) + "=s256"
    quoted = urllib.parse.quote(base.replace("https://", ""), safe="")
    return f"https://images.weserv.nl/?url={quoted}&w=192&h=192&fit=cover&mask=circle"


def load_cache():
    try:
        return json.loads(CACHE.read_text())
    except Exception:
        return {}


def card(a, d):
    link = f"https://play.google.com/store/apps/details?id={a['id']}"
    rating = ""
    if d.get("score"):
        rating = f'\n      <img src="https://img.shields.io/badge/Rating-{d["score"]:.1f}%E2%98%85-F59E0B?style=flat-square"/>'
    return f"""    <td width="33%" align="center" valign="top">
      <a href="{link}"><img src="{circle(d['icon'])}" width="96" height="96" alt="{a['name']}"/></a>
      <h3>{a['name']}</h3>
      <p><sub>{a['local']}</sub></p>
      <p>{a['desc']}</p>
      <img src="https://img.shields.io/badge/Downloads-{fmt(d['installs']).replace('+', '%2B')}-34A853?style=flat-square"/>{rating}
      <br/><br/>
      <a href="{link}"><img src="https://img.shields.io/badge/Get%20it%20on-Google%20Play-0F172A?style=for-the-badge&logo=googleplay&logoColor=34A853"/></a>
    </td>"""


STATS_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="150" viewBox="0 0 1200 150">
  <defs>
    <linearGradient id="n" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#7DD3FC"/><stop offset="1" stop-color="#A78BFA"/></linearGradient>
    <linearGradient id="card" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#111B2E"/><stop offset="1" stop-color="#0B1220"/></linearGradient>
  </defs>
  <style>
    .t{font-family:'Segoe UI','Inter','Helvetica Neue',Arial,sans-serif}
    @keyframes up{from{opacity:0;transform:translateY(16px)}to{opacity:1;transform:translateY(0)}}
    .c1{animation:up .8s .1s both}.c2{animation:up .8s .25s both}.c3{animation:up .8s .4s both}.c4{animation:up .8s .55s both}
    .num{font-size:44px;font-weight:800;fill:url(#n)}
    .lab{font-size:14px;fill:#94A3B8;letter-spacing:2px;font-weight:600}
  </style>
  <g class="t">
    <g class="c1"><rect x="10" y="10" width="280" height="130" rx="18" fill="url(#card)" stroke="#ffffff" stroke-opacity="0.09"/>
      <text class="num" x="150" y="76" text-anchor="middle">__APPS__</text><text class="lab" x="150" y="108" text-anchor="middle">APPS ON GOOGLE PLAY</text></g>
    <g class="c2"><rect x="316" y="10" width="280" height="130" rx="18" fill="url(#card)" stroke="#ffffff" stroke-opacity="0.09"/>
      <text class="num" x="456" y="76" text-anchor="middle">__DOWNLOADS__</text><text class="lab" x="456" y="108" text-anchor="middle">TOTAL DOWNLOADS</text></g>
    <g class="c3"><rect x="622" y="10" width="280" height="130" rx="18" fill="url(#card)" stroke="#ffffff" stroke-opacity="0.09"/>
      <text class="num" x="762" y="76" text-anchor="middle">__TOP__</text><text class="lab" x="762" y="108" text-anchor="middle">TOP-RATED APP</text></g>
    <g class="c4"><rect x="928" y="10" width="262" height="130" rx="18" fill="url(#card)" stroke="#ffffff" stroke-opacity="0.09"/>
      <text class="num" x="1059" y="76" text-anchor="middle">__REVIEWS__</text><text class="lab" x="1059" y="108" text-anchor="middle">USER REVIEWS</text></g>
  </g>
</svg>
"""


def main():
    cache, data = load_cache(), {}
    for a in APPS:
        try:
            fresh = fetch(a["id"])
        except Exception as e:
            print(f"warn: {a['id']}: fetch failed: {e}")
            fresh = {}
        old, seed = cache.get(a["id"], {}), MOCK.get(a["id"], {})
        merged = {}
        for field in ("installs", "icon", "score", "reviews"):
            value = fresh.get(field)
            if value in (None, "", 0):
                value = old.get(field)
                if value in (None, "", 0):
                    value = seed.get(field)
                if value is not None:
                    print(f"warn: {a['id']}: '{field}' not available live, using saved value")
            merged[field] = value
        for field in ("installs", "icon"):
            if not merged[field]:
                raise SystemExit(f"No value for '{field}' of {a['id']}; aborting.")
        data[a["id"]] = merged
    CACHE.write_text(json.dumps(data, indent=2))

    total = sum(d["installs"] for d in data.values())
    scores = [d["score"] for d in data.values() if d.get("score")]
    reviews = sum(d["reviews"] for d in data.values() if d.get("reviews"))
    top_txt = f"{max(scores):.1f}★" if scores else "—"
    rev_txt = (f"{reviews // 25 * 25}+" if reviews >= 100 else str(reviews)) if reviews else "—"

    STATS.write_text(STATS_SVG.replace("__APPS__", str(len(APPS))).replace("__DOWNLOADS__", fmt(total))
                     .replace("__TOP__", top_txt).replace("__REVIEWS__", rev_txt))

    block = "<table>\n  <tr>\n" + "\n".join(card(a, data[a["id"]]) for a in APPS) + "\n  </tr>\n</table>"
    text = README.read_text()
    new = re.sub(r"(<!-- APPS:START -->).*?(<!-- APPS:END -->)",
                 lambda m: f"{m.group(1)}\n{block}\n{m.group(2)}", text, flags=re.S)
    README.write_text(new)
    print(f"ok: {len(APPS)} apps, {fmt(total)} downloads, top {top_txt}, {rev_txt} reviews")


if __name__ == "__main__":
    main()