# ScrapeKit

> A local-first, security-conscious web scraper. Accepts a public URL, validates it, checks `robots.txt`, fetches the page safely, extracts structured content, and exports JSON + Markdown.

---

## Features

- 🔒 **SSRF protection** — blocks requests to private/local/reserved IPs, validated at every redirect hop
- 🤖 **robots.txt compliance** — respects crawl policies before fetching any page
- 📄 **Structured extraction** — title, description, canonical URL, headings, links, visible text, stats
- 📦 **Clean output** — deterministic JSON and Markdown files saved to `outputs/`
- 🖥️ **Streamlit UI** — local browser interface with downloads
- 💻 **CLI** — `python main.py <url>`

---

## Architecture

```text
User URL
  ↓ URL Validation + Scheme Check
  ↓ Hostname/IP Validation (SSRF)
  ↓ robots.txt Fetch + Policy Check
  ↓ HTTP Page Fetch (redirect SSRF revalidation)
  ↓ HTML Parsing + Cleaning
  ↓ Structured Result (ScrapeResult)
  ↓ JSON + Markdown Export
```

### Module map

| Module | Responsibility |
|---|---|
| `app/security.py` | URL/scheme/hostname/IP/redirect validation |
| `app/validators.py` | IP classification helpers |
| `app/robots.py` | robots.txt fetch, parse, cache |
| `app/fetcher.py` | HTTP client wiring security + robots |
| `app/parser.py` | BeautifulSoup HTML extraction |
| `app/cleaner.py` | Noise removal, whitespace normalization |
| `app/models.py` | `ScrapeResult` typed dataclass |
| `app/exporter.py` | JSON + Markdown writers |
| `app/ui.py` | Streamlit interface |

---

## Installation

**Requirements**: Python 3.11+, Windows/macOS/Linux

```bash
git clone <repo>
cd scraper

python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

pip install -r requirements.txt
```

---

## Running Locally

### CLI

```bash
python main.py https://example.com
```

Example output:
```
Scrape completed

Title: Example Domain
Words: 32
Headings: 1
Links: 1
Robots: Allowed

JSON: outputs/example-com.json
Markdown: outputs/example-com.md
```

### Streamlit UI

```bash
streamlit run app/ui.py
```

Open `http://localhost:8501` in your browser.

---

## Example Output

### JSON (`outputs/example-com.json`)

```json
{
  "source": {
    "requested_url": "https://example.com",
    "final_url": "https://example.com",
    "status_code": 200,
    "content_type": "text/html",
    "robots_checked": true,
    "robots_allowed": true,
    "robots_url": "https://example.com/robots.txt"
  },
  "page": {
    "title": "Example Domain",
    "description": null,
    "canonical_url": null
  },
  "content": {
    "headings": [{"level": 1, "text": "Example Domain"}],
    "links": [{"href": "https://www.iana.org/domains/example", "text": "More information..."}],
    "text": "Example Domain\nThis domain is for use in illustrative examples..."
  },
  "stats": {
    "word_count": 32,
    "character_count": 198,
    "heading_count": 1,
    "link_count": 1
  },
  "scraped_at": "2026-09-28T14:30:00"
}
```

---

## Supported Pages

✅ Public HTTP/HTTPS HTML pages  
✅ Pages with redirects (revalidated at each hop)  
✅ Pages with relative links (resolved to absolute)  

❌ JavaScript-rendered pages (Playwright is a planned future enhancement)  
❌ Pages requiring authentication  
❌ Pages behind CAPTCHAs  
❌ Private/internal URLs  

---

## SSRF Protection

All URLs are validated **before** any network activity:

- Only `http://` and `https://` schemes are accepted
- The hostname is DNS-resolved and every returned IP is checked
- Blocked ranges include: loopback (`127.x`), private (`10.x`, `172.16–31.x`, `192.168.x`), link-local (`169.254.x`), IPv6 private (`::1`, `fc00::/7`, `fe80::/10`), and others
- Every redirect destination is **re-validated** before following
- Maximum of 5 redirects

> **Limitation**: DNS rebinding attacks cannot be fully prevented in a local single-process implementation. The design documents this honestly rather than overstating its protection.

---

## robots.txt Behavior

- `robots.txt` is fetched before every page scrape
- User-agent sent: `ScrapeKit/0.1 (+local-web-scraper)`
- `Disallow` rules for `ScrapeKit/0.1` or `*` are respected
- **robots.txt 404** → treated as "allow all" (standard semantics)
- **robots.txt timeout or network error** → scrape is **blocked** (conservative policy)
- Results are cached in memory for 300 seconds per origin

---

## Security Limitations

- This is a **local MVP** — not hardened for production API exposure without further review
- DNS rebinding is not fully mitigated (see SSRF section)
- No rate limiting is implemented
- No authentication bypass protection beyond SSRF checks

---

## Future Roadmap

*(Post-MVP — not yet implemented)*

1. Website change monitoring
2. AI summarization via local LLM
3. Scheduled scraping
4. Job / product data extraction
5. Playwright support for JS-rendered pages

---

## Development

```bash
# Run tests
pytest -v

# Run only offline tests
pytest -v -m "not live"

# Optional: live smoke test (requires internet)
pytest -v -m live
```

---

*ScrapeKit v0.1.0 — local-first, built incrementally.*
