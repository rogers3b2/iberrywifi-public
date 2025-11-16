#!/usr/bin/env python3
"""
Robust OpenAI generator for iberrywifi.
Features:
 - exponential backoff + jitter on 429/5xx
 - per-topic retry (so one failing topic won't stop others)
 - writes only successful outputs to generated/
 - writes sitemap.xml at the end (only includes files that were created)
"""
import os, sys, time, json, re, random
import requests
from datetime import datetime

OPENAI_KEY = os.environ.get("OPENAI_API_KEY")
SITE_BASE = os.environ.get("SITE_BASE_URL", "https://iberrywifi.com")
COMPANY = os.environ.get("COMPANY_NAME", "IberryWifi")

if not OPENAI_KEY:
    print("OPENAI_API_KEY missing in env", file=sys.stderr)
    sys.exit(1)

OPENAI_API = "https://api.openai.com/v1/chat/completions"
MODEL = "gpt-4o-mini"   # change if you prefer a different model

HEADERS = {
    "Authorization": f"Bearer {OPENAI_KEY}",
    "Content-Type": "application/json",
}

def call_openai_with_retries(system, user_prompt, max_tokens=800, temp=0.2, max_retries=5):
    attempt = 0
    while attempt < max_retries:
        try:
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
            r = requests.post(OPENAI_API, headers=HEADERS, json=payload, timeout=60)
            r.raise_for_status()
            data = r.json()
            return data["choices"][0]["message"]["content"].strip()
        except requests.exceptions.HTTPError as e:
            status = getattr(e.response, "status_code", None)
            msg = str(e)
            # Rate limit / server errors -> retry with backoff
            if status in (429, 500, 502, 503, 504):
                attempt += 1
                backoff = (2 ** attempt) + random.uniform(0, 1)
                print(f"OpenAI error (status {status}). Retry {attempt}/{max_retries} after {backoff:.1f}s. Error: {msg}")
                time.sleep(backoff)
                continue
            else:
                # non-retryable HTTP error
                raise
        except requests.exceptions.RequestException as e:
            # network-level issues - retry a few times
            attempt += 1
            backoff = (2 ** attempt) + random.uniform(0, 1)
            print(f"Network error when calling OpenAI. Retry {attempt}/{max_retries} after {backoff:.1f}s. Error: {e}")
            time.sleep(backoff)
            continue
    # if we get here, retries exhausted
    raise RuntimeError(f"OpenAI calls failed after {max_retries} attempts.")

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
Write a 700-900 word SEO blog in HTML about: {topic}.
Include:
- <title> (<=60 chars)
- <meta name=\"description\"> (<=155 chars)
- H1 and H2s
- Two short FAQs (schema-friendly)
- Suggested internal link targets (use example paths)
Output only an HTML snippet.
"""
    return call_openai_with_retries(system, prompt, max_tokens=1200, temp=0.2)

created_files = []
for t in topics:
    print("Generating:", t)
    try:
        html = generate_blog(t)
    except Exception as e:
        print("OpenAI error (final):", e)
        continue
    fname = re.sub(r'[^a-z0-9]+', '-', t.lower()).strip('-') + ".html"
    path = os.path.join(OUT_DIR, fname)
    with open(path, "w", encoding="utf-8") as f:
        f.write("<!-- Auto-generated blog -->\n")
        f.write(html)
    created_files.append(fname)
    print("Wrote:", path)
    # small polite delay to avoid bursting
    time.sleep(2)

# Generate sitemap.xml from the actual created files
urls = [f"{SITE_BASE}/"] + [f"{SITE_BASE}/{fn}" for fn in created_files]
sitemap = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
for u in urls:
    sitemap += f"  <url>\n    <loc>{u}</loc>\n    <lastmod>{datetime.utcnow().date().isoformat()}</lastmod>\n  </url>\n"
sitemap += "</urlset>"
with open("sitemap.xml", "w", encoding="utf-8") as f:
    f.write(sitemap)
print("Wrote sitemap.xml")
