# ScrapeKit — Iterative Build Plan

## Goal

Build **ScrapeKit**: a small, polished, local-first Python web scraper that validates, fetches, parses, and exports structured data from public HTML pages — with security-first architecture (SSRF protection, robots.txt compliance) and a Streamlit UI.

The build follows the 12-phase sequence defined in [`master_prompt.md`](file:///c:/Users/gadit/OneDrive/Desktop/projects/scraper/master_prompt.md), proceeding **one phase at a time**, never leaving the repo in a broken state.

---

## User Review Required

> [!IMPORTANT]
> Each phase is implemented, verified, and logged **before** moving to the next. You approve each phase result before I continue.

> [!WARNING]
> No cloud dependencies, no Docker, no databases are introduced. If you later need them, we discuss it explicitly first.

> [!CAUTION]
> SSRF protections will **not** be weakened to make a specific test URL work. robots.txt will **not** be bypassed. These are hard constraints.

---

## Open Questions

> [!IMPORTANT]
> **Q1 — Virtual environment**: Should I create a `.venv` inside the repo root (`scraper/.venv`), or do you already have one you prefer to use?
> Default plan: create `.venv` in repo root.

> [!IMPORTANT]
> **Q2 — Git**: Is Git initialized on this repo? Should I suggest commit commands after each phase, or just keep a changelog?
> Default plan: maintain `CHANGELOG.md` and suggest git commands, but not run them automatically.

> [!IMPORTANT]
> **Q3 — Existing files**: The repo currently contains only `master_prompt.md`. I will treat this as a **fresh start** and will not delete it. Confirm this is correct.

---

## Documentation Strategy

Two living documents will be created and maintained alongside the code:

| File | Purpose |
|---|---|
| [`README.md`](file:///c:/Users/gadit/OneDrive/Desktop/projects/scraper/README.md) | Developer and user guide — updated after each phase adds user-visible capability |
| [`CHANGELOG.md`](file:///c:/Users/gadit/OneDrive/Desktop/projects/scraper/CHANGELOG.md) | Unreleased running log — one entry per phase with date, files changed, and what was done |

### CHANGELOG format (Keep a Changelog convention)

```markdown
## [Unreleased]

### Phase 2 — 2026-09-28
#### Added
- `app/security.py`: URL/scheme/hostname/SSRF validation
- `app/validators.py`: public IP helpers
- `tests/test_security.py`: 20+ deterministic SSRF tests
#### Changed
- n/a
```

### README sections maintained per phase

| Phase | README section added/updated |
|---|---|
| 1 | Installation, project structure |
| 2 | SSRF protection description |
| 3 | robots.txt behavior |
| 4 | HTTP fetcher, timeouts |
| 5–6 | Extraction and cleaning |
| 7–8 | Data model, output files |
| 9 | CLI usage + example output |
| 10 | Streamlit usage |
| 11 | Security limitations, roadmap |

---

## Target Repository Structure

```text
scraper/
│
├── app/
│   ├── __init__.py
│   ├── security.py        # SSRF + URL validation (Phase 2)
│   ├── validators.py      # IP/hostname helpers (Phase 2)
│   ├── robots.py          # robots.txt fetch + parse + cache (Phase 3)
│   ├── fetcher.py         # HTTP client wiring security+robots (Phase 4)
│   ├── parser.py          # BeautifulSoup HTML extraction (Phase 5)
│   ├── cleaner.py         # text noise removal + normalization (Phase 6)
│   ├── models.py          # ScrapeResult dataclass (Phase 7)
│   ├── exporter.py        # JSON + Markdown writers (Phase 8)
│   └── ui.py              # Streamlit interface (Phase 10)
│
├── tests/
│   ├── test_security.py   # Phase 2
│   ├── test_robots.py     # Phase 3
│   ├── test_fetcher.py    # Phase 4
│   ├── test_parser.py     # Phase 5
│   ├── test_cleaner.py    # Phase 6
│   ├── test_exporter.py   # Phase 8
│   └── fixtures/          # local HTML files for parser/cleaner tests
│
├── outputs/               # generated .json and .md scrape results
├── main.py                # CLI entry point (Phase 9)
├── requirements.txt       # pinned deps (Phase 1)
├── pyproject.toml         # project metadata + tool config (Phase 1)
├── .gitignore             # Phase 1
├── README.md              # created Phase 1, updated each phase
├── CHANGELOG.md           # created Phase 1, updated each phase
└── master_prompt.md       # preserved as-is
```

---

## Phases

### Phase 0 — Repository Inspection ✅ (done during planning)

**Goal**: Understand what already exists and what environment we're working in.

**Findings**:
- Python 3.11.2 ✅
- pip 26.0.1 ✅
- Repo contains only `master_prompt.md` — fresh start
- No venv, no existing code, no Git state checked yet
- Windows 11 / PowerShell environment

**Output**: This plan. No code changes.

---

### Phase 1 — Project Skeleton

**Goal**: Create the minimal working project scaffold.

#### [NEW] `.gitignore`
Standard Python gitignore — excludes `.venv/`, `__pycache__/`, `outputs/`, `.pytest_cache/`, `*.pyc`.

#### [NEW] `requirements.txt`
```text
httpx>=0.27
beautifulsoup4>=4.12
lxml>=5.2
pydantic>=2.7
streamlit>=1.35
pytest>=8.2
pytest-httpx>=0.30
```

#### [NEW] `pyproject.toml`
```toml
[project]
name = "scrapekit"
version = "0.1.0"
requires-python = ">=3.11"

[tool.pytest.ini_options]
testpaths = ["tests"]
```

#### [NEW] `app/__init__.py` — empty package marker

#### [NEW] `README.md` — skeleton with sections (filled progressively)

#### [NEW] `CHANGELOG.md` — initialized with `[Unreleased]` block

**Verification**:
```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python -c "import httpx, bs4, pydantic, streamlit; print('OK')"
```

**Git suggestion**: `feat: initial project skeleton`

---

### Phase 2 — URL Validation + Security Layer

**Goal**: Implement a security boundary that all URLs must pass before any network activity.

#### [NEW] `app/security.py`

Key functions:
```python
def validate_url(url: str) -> str:
    """Validate scheme, parse URL, normalize. Raises SecurityError."""

def validate_hostname(hostname: str) -> list[str]:
    """Resolve hostname to IPs. Raises SecurityError if any IP is private/reserved."""

def is_safe_ip(ip: str) -> bool:
    """Return True if the IP is a publicly routable address."""

def validate_redirect_target(url: str) -> str:
    """Re-run full validation on a redirect destination."""
```

Private/reserved ranges blocked:
- `127.0.0.0/8`, `10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`
- `169.254.0.0/16`, `100.64.0.0/10`, `0.0.0.0/8`
- `224.0.0.0/4`, `240.0.0.0/4`
- `::1/128`, `fc00::/7`, `fe80::/10`

#### [NEW] `app/validators.py`
IP classification helpers using `ipaddress` stdlib — no regex.

#### [NEW] `tests/test_security.py`
Deterministic tests (no real network): mock `socket.getaddrinfo`.

Test cases:
- `localhost` → blocked
- `127.0.0.1` → blocked
- `192.168.1.1` → blocked
- `169.254.0.1` → blocked
- `::1` → blocked
- `fd00::1` → blocked
- `::ffff:127.0.0.1` (IPv4-mapped) → blocked
- `0x7f000001` (hex IP) → blocked
- `file://` → blocked
- `javascript://` → blocked
- `ftp://` → blocked
- malformed URL → blocked
- valid public URL → passes

**Verification**:
```powershell
pytest tests/test_security.py -v
```
All tests must pass before Phase 3 begins.

**Git suggestion**: `feat: add URL validation and SSRF protection`

---

### Phase 3 — robots.txt Layer

**Goal**: Fetch and parse `robots.txt` for a target domain and enforce crawl policy.

#### [NEW] `app/robots.py`

Key design:
```python
USER_AGENT = "ScrapeKit/0.1 (+local-web-scraper)"
ROBOTS_CACHE_TTL = 300  # seconds

class RobotsChecker:
    def is_allowed(self, url: str) -> bool: ...
    def _fetch_robots(self, origin: str) -> str: ...  # uses security layer
    def _get_cached(self, origin: str) -> str | None: ...
```

Policy:
- robots.txt fetch fails (timeout/network) → **block** scrape, log reason
- robots.txt 404 → treat as "allow all" (standard semantics), document this
- `Disallow` for `ScrapeKit/0.1` or `*` → block
- `Allow` overrides Disallow (standard)
- Uses `urllib.robotparser.RobotFileParser` internally

#### [NEW] `tests/test_robots.py`
Mocked HTTP responses (using `pytest-httpx` or `responses`).

Test cases:
- allowed URL
- disallowed URL
- explicit user-agent group
- wildcard group
- Allow overrides Disallow
- empty Disallow (allow all)
- missing robots.txt (404) → allowed
- robots timeout → blocked
- malformed robots content → conservative block
- robots redirect to safe target
- robots redirect to unsafe target → blocked
- cache hit (no second fetch)
- cache TTL expiry

**Verification**:
```powershell
pytest tests/test_robots.py -v
```

**Git suggestion**: `feat: add robots.txt policy enforcement`

---

### Phase 4 — HTTP Fetcher

**Goal**: Wire security + robots into a safe HTTP fetch pipeline.

#### [NEW] `app/fetcher.py`

Pipeline:
```text
validate_url()
  → validate_hostname()       [SSRF check]
  → RobotsChecker.is_allowed()
  → httpx.Client.get()        [with redirect interception]
    → each redirect: validate_redirect_target()
  → check Content-Type (must be text/html)
  → check response size (cap at ~5 MB)
  → return raw HTML + metadata
```

Constants:
```python
CONNECT_TIMEOUT = 10.0   # seconds
READ_TIMEOUT = 20.0      # seconds
MAX_REDIRECTS = 5
MAX_RESPONSE_BYTES = 5 * 1024 * 1024  # 5 MB
```

#### [NEW] `tests/test_fetcher.py`
Uses mocked httpx transport — no real network.

**Verification**:
```powershell
# mocked tests
pytest tests/test_fetcher.py -v

# optional live smoke test
python -c "from app.fetcher import fetch; r = fetch('https://example.com'); print(r.status_code)"
```

**Git suggestion**: `feat: add HTTP fetcher with redirect SSRF validation`

---

### Phase 5 — HTML Parser

**Goal**: Extract structured content from validated HTML.

#### [NEW] `app/parser.py`

Extracts:
- `title` — `<title>` tag
- `description` — `<meta name="description">`
- `canonical` — `<link rel="canonical">`
- `headings` — list of `{level: int, text: str}`
- `links` — list of `{href: str, text: str}` (absolute URLs)
- `text` — visible page text (noise removed by cleaner)
- `meta_tags` — key/value dict of all meta tags

#### [NEW] `tests/test_parser.py`
Uses local HTML fixtures in `tests/fixtures/`.

Fixtures:
- `basic.html` — minimal page with title, meta, h1, links
- `relative_links.html` — relative hrefs to be absolutized
- `no_meta.html` — missing description/canonical
- `duplicate_links.html` — deduplication test

**Verification**:
```powershell
pytest tests/test_parser.py -v
```

**Git suggestion**: `feat: add structured HTML parser`

---

### Phase 6 — Cleaner

**Goal**: Improve text quality by removing noise and normalizing whitespace.

#### [NEW] `app/cleaner.py`

Removes: `<script>`, `<style>`, `<noscript>`, `<svg>`, HTML comments
Normalizes: collapse multiple whitespace/newlines into single spaces/newlines
Deduplicates: links (by `href`)
Preserves: useful paragraph breaks

#### Modified `app/parser.py`
Cleaner is called inside parser — not mixed into fetcher/security.

**Verification**:
```powershell
pytest tests/test_parser.py tests/test_cleaner.py -v
```

**Git suggestion**: `feat: add HTML cleaner`

---

### Phase 7 — Data Model

**Goal**: Replace loose dicts with a typed `ScrapeResult` model.

#### [NEW] `app/models.py`
```python
from dataclasses import dataclass, field
from datetime import datetime

@dataclass
class SourceInfo:
    requested_url: str
    final_url: str
    status_code: int
    content_type: str
    robots_checked: bool
    robots_allowed: bool
    robots_url: str

@dataclass
class PageInfo:
    title: str
    description: str
    canonical_url: str | None

@dataclass
class ContentInfo:
    headings: list[dict]
    links: list[dict]
    text: str

@dataclass
class StatsInfo:
    word_count: int
    character_count: int
    heading_count: int
    link_count: int

@dataclass
class ScrapeResult:
    source: SourceInfo
    page: PageInfo
    content: ContentInfo
    stats: StatsInfo
    scraped_at: datetime = field(default_factory=datetime.utcnow)
```

**Verification**:
```powershell
python -c "from app.models import ScrapeResult; print('model OK')"
```

**Git suggestion**: `feat: add typed ScrapeResult data model`

---

### Phase 8 — Exporters

**Goal**: Write scrape results to `outputs/` as JSON and Markdown files.

#### [NEW] `app/exporter.py`

```python
def export_json(result: ScrapeResult, output_dir: Path) -> Path: ...
def export_markdown(result: ScrapeResult, output_dir: Path) -> Path: ...
def make_safe_filename(url: str) -> str: ...
```

Filename strategy: slugify the hostname + path, max 80 chars, e.g. `example-com.json`.

Markdown output structure:
```markdown
# Example Domain

**URL**: https://example.com
**Scraped**: 2026-09-28T14:30:00Z
**Words**: 32 | **Links**: 1 | **Headings**: 1

## Headings
- H1: Example Domain

## Links
- [More information...](https://www.iana.org/domains/example)

## Content
Example Domain. This domain is for use in illustrative examples...
```

#### [NEW] `tests/test_exporter.py`
- Correct JSON structure and keys
- Safe filenames for edge-case URLs
- Markdown contains expected sections
- Files written to temp dir

**Verification**:
```powershell
pytest tests/test_exporter.py -v
```

**Git suggestion**: `feat: add JSON and Markdown exporters`

---

### Phase 9 — CLI

**Goal**: Wire the full pipeline into `main.py`.

#### [NEW] `main.py`

```python
# python main.py https://example.com
```

Output format:
```text
Scrape completed

Title: Example Domain
Words: 32
Headings: 1
Links: 1
Robots: Allowed

JSON: outputs/example-com.json
Markdown: outputs/example-com.md
```

Error output:
```text
Scrape blocked

Reason: Target resolves to a private network address.
```

Uses `sys.exit(1)` on failure, `sys.exit(0)` on success.

**Verification**:
```powershell
python main.py https://example.com
python main.py https://127.0.0.1       # must block
python main.py file:///etc/passwd       # must block
```

**Git suggestion**: `feat: add CLI entry point`

---

### Phase 10 — Streamlit UI

**Goal**: Build a clean local browser interface.

#### [NEW] `app/ui.py`

UI elements:
- URL text input
- "Scrape" button
- Spinner / loading state
- Success view:
  - page title, source URL, final URL, robots status badge
  - stat cards (words, headings, links, characters)
  - expandable: headings list, links table, text preview
  - Download JSON button, Download Markdown button
- Blocked/error view:
  - clear reason message (no stack traces exposed)

**Verification**:
```powershell
streamlit run app/ui.py
# Manually test: https://example.com (success), https://192.168.1.1 (blocked)
```

**Git suggestion**: `feat: add Streamlit local UI`

---

### Phase 11 — Polish

**Goal**: Production-ready MVP.

Additions:
- Edge-case tests (empty body, binary response, very long pages)
- Cleaner error messages throughout
- Security limitations section in README
- Explicit documentation of DNS rebinding limitation
- `pyproject.toml` lint config (optional: ruff)
- Final README pass covering all 13 sections from master_prompt

**Git suggestion**: `docs: finalize README and security documentation`

---

### Phase 12 — Product Extension Recommendations (post-MVP only)

After Phase 11 is complete and verified, recommend the top 3 next product directions from:
1. Website change monitoring
2. Job listing extraction
3. AI summarization (local LLM via Ollama)
4. Scheduled scraping
5. Semantic search / RAG

**No implementation until explicitly requested.**

---

## Verification Plan

### Automated Tests (per phase)
Each phase runs its own test file before proceeding:
```powershell
pytest tests/test_security.py -v    # Phase 2
pytest tests/test_robots.py -v      # Phase 3
pytest tests/test_fetcher.py -v     # Phase 4
pytest tests/test_parser.py -v      # Phase 5
pytest tests/test_cleaner.py -v     # Phase 6
pytest tests/test_exporter.py -v    # Phase 8
pytest -v                           # Full suite, Phase 11
```

### Full suite gate
No phase is considered complete until `pytest -v` exits 0.

### Manual Verification (Phase 9 + 10)
```powershell
# CLI
python main.py https://example.com
python main.py https://127.0.0.1

# UI
streamlit run app/ui.py
```

### Live smoke test (optional, internet required)
```powershell
pytest tests/smoke_test.py -v -m live
```

---

## Git Commit Convention

```
feat: add URL validation and SSRF protection        ← Phase 2
feat: add robots.txt policy enforcement             ← Phase 3
feat: add HTTP fetcher with redirect validation     ← Phase 4
feat: add structured HTML parser                    ← Phase 5
feat: add HTML cleaner                              ← Phase 6
feat: add typed ScrapeResult data model             ← Phase 7
feat: add JSON and Markdown exporters               ← Phase 8
feat: add CLI entry point                           ← Phase 9
feat: add Streamlit local UI                        ← Phase 10
docs: finalize README and security documentation    ← Phase 11
```

Commits are **suggested** after each phase — not run automatically unless you ask.
