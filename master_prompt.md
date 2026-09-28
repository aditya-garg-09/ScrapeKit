You are my senior software engineer and implementation partner. We are going to build a polished local-first web scraping product from scratch inside this repository.

## Product

Working name: `ScrapeKit`

Core idea:

> User enters a public website URL → scraper validates access → checks robots.txt → fetches the page safely → extracts useful structured information → cleans/normalizes it → saves downloadable JSON + Markdown output.

The goal is NOT to build a giant scraping framework.

The goal is to build a small, polished, technically sound product that works reliably for normal public HTML pages and has a clean architecture that can later evolve into a real SaaS/backend product.

---

# Development philosophy

Build this incrementally.

Do NOT dump the entire application at once.

Work like a senior engineer pairing with me:

1. Inspect the existing repository first.
2. Explain briefly what you found.
3. Propose the smallest next implementation step.
4. Implement it.
5. Run/verify it.
6. Show me exactly what changed.
7. Then move to the next step.

Keep each step functional.

Never leave the repository in a broken state between steps.

Do not over-engineer early.

Prefer simple, understandable code over abstractions that are not yet justified.

---

# Runtime

Everything must run locally on my machine.

Target environment:

* Windows 11
* VS Code
* Python 3.11+
* Virtual environment
* Local filesystem
* No cloud dependency
* No paid APIs
* No external database initially

Do not introduce AWS, Docker, Kubernetes, Redis, PostgreSQL, queues, or microservices unless there is a concrete reason later.

---

# Initial tech stack

Use:

* Python
* `httpx` or `requests` for HTTP
* `BeautifulSoup4` + `lxml` for HTML parsing
* `urllib.robotparser` or an appropriately maintained robots.txt implementation for robots handling
* `ipaddress` / DNS resolution utilities for SSRF validation
* `dataclasses` or Pydantic for structured models
* Streamlit for the local UI
* pytest for tests
* standard Python logging
* pathlib for filesystem operations

Keep dependencies minimal.

Prefer the Python standard library when it provides a sufficient solution.

---

# Desired architecture

Eventually aim for something roughly like:

```text
scrape-kit/
│
├── app/
│   ├── __init__.py
│   ├── fetcher.py
│   ├── parser.py
│   ├── cleaner.py
│   ├── robots.py
│   ├── security.py
│   ├── models.py
│   ├── exporter.py
│   ├── validators.py
│   └── ui.py
│
├── tests/
│   ├── test_fetcher.py
│   ├── test_parser.py
│   ├── test_cleaner.py
│   ├── test_robots.py
│   ├── test_security.py
│   ├── test_exporter.py
│   └── fixtures/
│
├── outputs/
├── main.py
├── requirements.txt
├── README.md
├── .gitignore
└── pyproject.toml
```

You may adjust this structure when there is a good engineering reason.

Do not create files just for the sake of having files.

---

# MVP behavior

The product should accept a single URL.

Example:

```text
https://example.com
```

Before fetching the actual page, the application must:

1. Validate the URL.
2. Validate the hostname.
3. Perform SSRF safety checks.
4. Determine whether the target is eligible for scraping.
5. Fetch and evaluate `robots.txt`.
6. Respect the site's robots policy for the requested URL.
7. Only then fetch the page.

The scraper should attempt to extract:

* URL
* final URL after redirects
* page title
* meta description
* canonical URL if available
* headings (H1/H2/H3)
* links
* link text
* visible page text
* basic metadata
* scrape timestamp
* HTTP status
* content type
* basic statistics such as:

  * character count
  * word count
  * heading count
  * link count

Output should be structured and deterministic.

Example conceptual JSON:

```json
{
  "source": {
    "requested_url": "...",
    "final_url": "...",
    "status_code": 200,
    "content_type": "text/html",
    "robots_allowed": true
  },
  "page": {
    "title": "...",
    "description": "...",
    "canonical_url": "..."
  },
  "content": {
    "headings": [],
    "links": [],
    "text": "..."
  },
  "stats": {
    "word_count": 1234,
    "character_count": 5678,
    "heading_count": 8,
    "link_count": 42
  },
  "scraped_at": "..."
}
```

Generate:

```text
outputs/
    <safe-name>.json
    <safe-name>.md
```

---

# SSRF protection — mandatory

Treat the scraper as an SSRF-sensitive application.

Even though the first version is local, the architecture must be safe enough that exposing the scraping logic behind an API later does not immediately create an unrestricted server-side request primitive.

Implement a dedicated security/validation layer.

## URL requirements

Only support:

```text
http://
https://
```

Reject:

```text
file://
ftp://
gopher://
data://
javascript://
```

and any unsupported or ambiguous URL scheme.

Reject malformed URLs.

Normalize the URL before processing.

---

# SSRF protections

The application must prevent requests to private, local, link-local, loopback, multicast, reserved, and otherwise non-public network destinations.

At minimum, explicitly consider:

```text
127.0.0.0/8
10.0.0.0/8
172.16.0.0/12
192.168.0.0/16
169.254.0.0/16
100.64.0.0/10
0.0.0.0/8
224.0.0.0/4
240.0.0.0/4
::1/128
fc00::/7
fe80::/10
```

Do not rely only on string matching.

Resolve the hostname and inspect the resulting IP addresses using proper IP parsing.

Reject a hostname when any resolved destination is non-public or otherwise unsafe.

Be careful with:

* `localhost`
* local hostnames
* decimal IP representations
* hexadecimal IP representations
* IPv4-mapped IPv6 addresses
* unusual IPv6 forms
* trailing dots
* mixed-case hostnames
* DNS rebinding scenarios

Use canonical parsing and validation rather than ad-hoc regexes.

---

# Redirect SSRF protection

SSRF validation must happen not only for the initial URL but also after redirects.

Example:

```text
https://public.example
        ↓ redirect
http://127.0.0.1:8080
```

This must be blocked.

Therefore:

* inspect each redirect destination
* revalidate scheme
* re-resolve hostname
* re-check IP safety
* reject unsafe redirects
* impose a redirect limit

Do not blindly trust the initial hostname.

Use a small bounded redirect limit such as 5 unless there is a strong reason to choose another value.

---

# DNS rebinding considerations

Do not assume that checking a hostname once is sufficient.

Structure the fetch/security layer so that the resolved destination is validated before connection where practical.

Document any limitations of the local implementation honestly.

Do not claim the implementation provides perfect protection against every possible DNS race unless it actually does.

---

# SSRF tests

Create deterministic tests for:

* localhost
* `127.0.0.1`
* private IPv4 addresses
* link-local IPv4
* loopback IPv6
* private IPv6
* IPv4-mapped IPv6
* malformed URLs
* unsupported schemes
* unsafe redirect targets
* safe public URLs

Tests should not make real requests to internal services.

Mock DNS resolution and HTTP behavior where appropriate.

---

# robots.txt handling — mandatory

The scraper must respect `robots.txt` for the target domain.

Before fetching the target page:

1. Determine the origin.
2. Construct the robots URL:
   `https://example.com/robots.txt`
3. Fetch robots.txt using the same security controls as every other request.
4. Parse the rules for the scraper's user agent.
5. Determine whether the requested URL is allowed.
6. Refuse the scrape when the page is disallowed.

Use a clearly identifiable user agent, for example:

```text
ScrapeKit/0.1
```

Prefer:

```text
ScrapeKit/0.1 (+local-web-scraper)
```

when appropriate.

Do not impersonate a browser merely to circumvent crawler policies.

---

# robots.txt semantics

Handle at minimum:

* `User-agent`
* `Disallow`
* `Allow`
* wildcard user agents
* multiple matching groups
* path matching
* empty `Disallow`
* robots.txt retrieval failures

Follow standard robots.txt semantics rather than implementing a custom interpretation.

Do not treat robots.txt as an access-control mechanism.

It is a crawling policy signal.

Do not use robots.txt to justify bypassing authentication or other access controls.

---

# robots.txt failure policy

Define and document what happens when robots.txt cannot be retrieved.

Use a conservative policy.

The initial product should default to:

```text
robots.txt unavailable due to timeout/network error
→ do not scrape
```

For a valid HTTP response such as 404 where no robots.txt exists, handle according to standard robots semantics and document the decision.

Do not silently ignore robots failures.

The UI and CLI should communicate the reason clearly.

Example:

```text
Scrape blocked:
robots.txt could not be retrieved safely.
```

or:

```text
Scrape blocked:
robots.txt disallows ScrapeKit/0.1 from accessing this path.
```

---

# robots.txt caching

Avoid downloading robots.txt unnecessarily for every operation.

Implement a simple local in-memory cache initially.

Cache based on origin/host.

Keep the TTL bounded and configurable.

Do not build a distributed cache.

---

# robots.txt tests

Create deterministic local/mocked tests covering:

* allowed URL
* disallowed URL
* explicit user-agent group
* wildcard group
* Allow vs Disallow
* empty Disallow
* missing robots.txt
* robots timeout
* malformed robots content
* robots redirect
* unsafe robots redirect
* cache behavior

Do not depend entirely on live websites for these tests.

---

# HTTP safety

Implement:

* connection/read timeouts
* reasonable response size limits
* redirect handling
* content-type checking
* HTTP error handling
* useful error messages
* safe redirect validation
* robots.txt checking before page retrieval

Never allow the scraper to hang indefinitely.

---

# Response size limits

Apply bounded response sizes to both:

1. target HTML
2. robots.txt

Do not allow a malicious or unexpectedly large server response to consume arbitrary memory.

Use streaming or bounded reads where appropriate.

---

# HTML parser

After a request is approved by the security and robots layers, extract:

* title
* description
* canonical
* headings
* links
* text
* metadata

Use:

```text
HTTP Fetch
   ↓
Security validation
   ↓
robots validation
   ↓
HTML parsing
```

Do not mix SSRF logic into BeautifulSoup parsing code.

---

# Cleaning

The parser should remove obvious non-content elements such as:

* script
* style
* noscript
* svg

Normalize excessive whitespace.

Avoid returning giant amounts of useless markup.

Preserve useful textual structure.

---

# Relative links

Convert relative links into absolute URLs.

Example:

```text
/about
```

becomes:

```text
https://example.com/about
```

Do not automatically follow those links in the initial MVP.

The initial product is a single-page scraper.

---

# Duplicate handling

Deduplicate links where appropriate.

Preserve useful ordering.

Do not deduplicate page text so aggressively that legitimate repeated content disappears.

---

# Logging

Use Python's logging system.

Have useful logs such as:

```text
Starting scrape
Validating URL
Resolving destination
SSRF validation passed
Fetching robots.txt
robots.txt allows target
Fetching page
Response received
Parsing HTML
Extracting content
Writing output
Scrape completed
```

For blocked requests, log the reason clearly.

Do not log sensitive information unnecessarily.

Do not spam the console.

---

# Errors

Handle common cases cleanly:

* invalid URL
* unsupported scheme
* private IP
* localhost
* unsafe redirect
* DNS resolution failure
* timeout
* connection failure
* robots.txt unavailable
* robots.txt disallow
* 404
* 403
* 500
* non-HTML content
* empty response
* malformed HTML

The application should not crash with a giant traceback during normal user errors.

---

# Data model

Represent scraping results using a clean structured model.

Include security/robots information such as:

```text
requested_url
final_url
robots_checked
robots_allowed
robots_url
status_code
content_type
```

Keep security diagnostics useful without leaking implementation details unnecessarily.

---

# UI

After the core scraper works, build a clean local Streamlit interface.

The UI should contain:

* URL input
* Scrape button
* loading state
* success/error state
* page title
* source URL
* final URL
* robots status
* basic extraction statistics
* preview of extracted text
* preview of headings
* preview of links
* Download JSON button
* Download Markdown button

For blocked requests, show a clear explanation:

```text
Scrape blocked

Reason:
robots.txt disallows ScrapeKit/0.1 from accessing this URL.
```

or:

```text
Scrape blocked

Reason:
The target resolves to a private or local network address.
```

Do not expose unnecessary low-level stack traces to the end user.

---

# CLI

Maintain a simple CLI too.

Example:

```bash
python main.py https://example.com
```

The CLI should produce a useful summary such as:

```text
Scrape completed

Title: Example Domain
Words: 32
Headings: 1
Links: 1
Robots: Allowed

JSON: outputs/example-domain.json
Markdown: outputs/example-domain.md
```

For blocked URLs:

```text
Scrape blocked

Reason: Target resolves to a private network address.
```

---

# Security architecture

Keep the security checks centralized.

Conceptually:

```text
User URL
   ↓
URL Parser
   ↓
Scheme Validation
   ↓
Hostname Validation
   ↓
DNS Resolution
   ↓
IP Safety Validation
   ↓
robots.txt Fetch
   ↓
robots Policy Check
   ↓
HTTP Page Fetch
   ↓
Redirect Validation
   ↓
HTML Parser
   ↓
Cleaner
   ↓
Structured Result
   ↓
Exporter
```

Do not scatter security checks randomly throughout the application.

Create a clear security boundary before page content enters the parser.

---

# Important scope constraints

This first version is ONLY for normal publicly accessible HTML.

Do NOT implement:

* CAPTCHA bypass
* anti-bot bypass
* proxy rotation
* stealth browsers
* scraping private/internal services
* credential harvesting
* unrestricted crawling
* full-site crawling
* authentication bypass
* robots.txt bypass
* deliberate evasion of crawler policies

JavaScript-rendered pages can be treated as a later enhancement using Playwright.

For now, make normal HTML scraping excellent and safe.

---

# Testing strategy

Use a layered test suite.

## Unit tests

Test:

* URL validation
* scheme validation
* hostname validation
* IP classification
* SSRF blocking
* redirect validation
* robots parsing
* robots caching
* HTML parsing
* text cleaning
* exporter behavior

## Integration tests

Use mocked HTTP responses to test:

```text
URL
 ↓
SSRF validation
 ↓
robots.txt
 ↓
page request
 ↓
parser
 ↓
exporter
```

Do not depend on external internet connectivity for most tests.

## Live smoke test

Maintain a small optional smoke test that can run against a known public HTML page.

Do not make the entire test suite dependent on internet access.

---

# Code quality

Write production-minded code without turning this into enterprise Java.

Requirements:

* type hints
* reasonable function sizes
* clear names
* docstrings only where useful
* no unexplained magic numbers
* constants for limits/timeouts
* avoid global mutable state
* avoid unnecessary classes
* meaningful exceptions
* clean imports
* no dead code

Do not use clever Python just to look clever.

---

# README

Create a useful README that explains:

1. What ScrapeKit is
2. Features
3. Architecture
4. Installation
5. Running locally
6. CLI usage
7. Streamlit usage
8. Example output
9. Supported/unsupported pages
10. SSRF protection
11. robots.txt behavior
12. Security limitations
13. Future roadmap

Explicitly document:

* that robots.txt is respected
* what happens when robots.txt cannot be retrieved
* that private/local destinations are blocked
* that redirects are revalidated
* that this is a local MVP
* that SSRF protection is designed with future API exposure in mind

Do not make exaggerated claims about security.

---

# Git discipline

At each meaningful milestone:

* ensure the project runs
* run tests
* run linting/formatting if configured
* inspect the diff
* summarize changes

Do NOT make random unrelated changes.

If Git is available, suggest logical commit boundaries such as:

```text
feat: add URL validation and SSRF protection
feat: add robots policy enforcement
feat: add html fetcher
feat: add structured page parser
feat: add exporters
test: add scraper unit tests
feat: add streamlit interface
docs: document security model
```

Do not create commits automatically unless I explicitly ask you to.

---

# Verification philosophy

For every implementation step, actually verify the result.

Do not say "this should work" when you can run it.

Use local test fixtures whenever possible.

For live URLs, use safe public pages only.

When something fails:

1. identify the root cause
2. explain it briefly
3. fix it
4. rerun the relevant verification

Do not hide errors.

---

# Development sequence

Follow this order unless the repository state makes a different order clearly better.

## Phase 0 — Repository inspection

Inspect the repository and determine:

* current files
* current environment
* Python version
* existing dependencies
* existing code

Do not overwrite useful existing work.

## Phase 1 — Project skeleton

Create the minimal project structure.

Set up:

* package structure
* requirements
* `.gitignore`
* basic config if needed

Verify imports.

## Phase 2 — URL validation + security layer

Implement:

* scheme validation
* hostname normalization
* hostname/IP validation
* DNS resolution
* private/local/link-local/reserved address blocking
* redirect target validation
* bounded redirects
* relevant exceptions
* security logging

Write deterministic tests.

Do not move on until the security tests pass.

## Phase 3 — robots.txt layer

Implement:

* robots URL construction
* robots fetching
* robots parsing
* user-agent policy matching
* Allow/Disallow handling
* failure behavior
* cache
* safe redirect handling

Write deterministic tests using mocked responses.

Do not move on until robots tests pass.

## Phase 4 — HTTP fetcher

Integrate the security and robots layers into the actual HTTP fetch process.

Order must remain approximately:

```text
Validate URL
→
SSRF check
→
robots check
→
Fetch page
→
Validate response
```

Revalidate redirects before following them.

Verify with a real public HTML page.

## Phase 5 — HTML parser

Implement extraction of:

* title
* description
* canonical
* headings
* links
* text
* metadata

Write parser tests using local HTML fixtures.

## Phase 6 — Cleaner

Improve text quality:

* remove noise
* normalize whitespace
* deduplicate where appropriate
* preserve useful structure

Verify against realistic HTML fixtures.

## Phase 7 — Data model

Create a clean structured result model.

Ensure the parser returns that model rather than random dictionaries scattered throughout the codebase.

## Phase 8 — Exporters

Implement:

* JSON export
* Markdown export

Make filenames safe and deterministic.

Test generated files.

## Phase 9 — CLI

Wire the pipeline together.

Verify:

```bash
python main.py https://example.com
```

## Phase 10 — Streamlit UI

Build the local product interface.

Verify:

```bash
streamlit run app/ui.py
```

## Phase 11 — Polish

Add:

* better UX
* concise status messaging
* stronger validation
* cleaner error messages
* edge-case tests
* README
* security documentation
* cleanup

## Phase 12 — Product extension recommendations

ONLY after the MVP works, inspect the architecture and recommend the next 3 highest-value product extensions.

Potential directions:

1. website change monitoring
2. job listing extraction
3. product data extraction
4. documentation extraction
5. AI summarization
6. semantic search/RAG
7. scheduled scraping

Do not implement those yet unless I explicitly ask.

---

# How I want you to communicate

Keep explanations concise but technical.

For each step, use this format:

```text
STEP X — <name>

Goal
<1–3 sentences>

Changes
<what you are implementing>

Files
<files created/modified>

Verification
<commands/results>

Security Notes
<only when relevant>

Next
<next concrete step>
```

Do not overwhelm me with the entire roadmap every time.

I want to watch the project evolve.

---

# Critical instruction

Start NOW with Phase 0.

First inspect the repository and environment.

Do not start generating implementation files until you have inspected what already exists.

After inspection, tell me what you found and proceed to the smallest sensible next step.

When implementing the security layer, prioritize correctness over convenience.

Do not weaken SSRF protections merely to make a test or live site work.

Do not bypass robots.txt because a target website blocks the scraper.

From this point onward, behave as the engineer actually implementing the product inside the repository, not as someone merely giving me hypothetical code snippets.
