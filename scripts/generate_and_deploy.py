#!/usr/bin/env python3
import os, sys, time, json, re
import requests
from datetime import datetime

OPENAI_KEY = os.environ.get("OPENAI_API_KEY")
SITE_BASE = os.environ.get("SITE_BASE_URL", "https://iberrywifi.com")
COMPANY = os.environ.get("COMPANY_NAME", "IberryWifi")

if not OPENAI_KEY:
    print("OPENAI_API_KEY missing in env", file=sys.stderr)
    sys.exit(1)

OPENAI_API = "https://api.openai.com/v1/chat/completions"
MODEL = "gpt-4o-mini"

def call_openai(system, user_prompt, max_tokens=800, temp=0.2):
    headers = {
        "Authorization": f"Bearer {OPENAI_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user_prompt}
        ],
        "max_tokens": max_tokens,
        "temperature": temp,
        "n": 1
    }
    r = requests.post(OPENAI_API, headers=headers, json=payload, timeout=60)
    r.raise_for_status()
    data = r.json()
    return data["choices"][0]["message"]["content"].strip()

OUT_DIR = "generated"
os.makedirs(OUT_DIR, exist_ok=True)

topics = [
    "How to choose the best WiFi hotspot solution for hotels",
    "Firewall vs UTM: what small hotels need to know",
    "Top 5 tips to improve hotel WiFi speeds"
]

def generate_blog(topic):
    system = "You are an SEO copywriter for a WiFi / hospitality services company. Produce clean HTML output."
    prompt = f"""
Write a 700–900 word SEO blog in HTML about: {topic}.
Include:
- <title> (max 60 chars)
- <meta name="description"> (max 155 chars)
- H1 and H2s
- Two short FAQs
- Suggested internal link targets (use example URLs)
Output only valid HTML.
"""
    return call_openai(system, prompt, max_tokens=1200)


for t in topics:
    print("Generating:", t)
    try:
        html = generate_blog(t)
    except Exception as e:
        print("OpenAI error:", e)
        continue
    fname = re.sub(r'[^a-z0-9]+', '-', t.lower()).strip('-') + ".html"
    path = os.path.join(OUT_DIR, fname)
    with open(path, "w", encoding="utf-8") as f:
        f.write("<!-- Auto-generated blog -->\n")
        f.write(html)
    print("Wrote:", path)
    time.sleep(1)

# Generate simple sitemap
urls = [f"{SITE_BASE}/"] + [f"{SITE_BASE}/{fn}" for fn in os.listdir(OUT_DIR) if fn.endswith(".html")]
sitemap = '<?xml version="1.0" encoding="UTF-8"?>\\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\\n'
for u in urls:
    sitemap += f"  <url>\\n    <loc>{u}</loc>\\n    <lastmod>{datetime.utcnow().date().isoformat()}</lastmod>\\n  </url>\\n"
sitemap += "</urlset>"
with open("sitemap.xml", "w", encoding="utf-8") as f:
    f.write(sitemap)
print("Wrote sitemap.xml")
