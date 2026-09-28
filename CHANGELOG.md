# Changelog

All notable changes to ScrapeKit are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [Unreleased]

### Phase 1 — Project Skeleton — 2026-09-28

#### Added
- `.gitignore` — Python/venv/output exclusions
- `requirements.txt` — httpx, beautifulsoup4, lxml, pydantic, streamlit, pytest, pytest-httpx
- `pyproject.toml` — project metadata, pytest config with `live` marker
- `app/__init__.py` — package marker
- `app/ui.py` — placeholder (Phase 10)
- `tests/__init__.py` — package marker
- `tests/fixtures/` — directory for local HTML test fixtures
- `outputs/` — directory for generated scrape files (gitignored)
- `README.md` — full skeleton with all 13 sections
- `CHANGELOG.md` — this file

#### Changed
- n/a

### Phase 2 — URL Validation + SSRF Security Layer — 2026-09-28

#### Added
- `app/validators.py`: IP classification helpers (`is_public_ip`) using stdlib `ipaddress` for IPv4, IPv6, IPv4-mapped IPv6, RFC 1918, link-local, loopback, multicast, CGNAT, documentation, and reserved ranges
- `app/security.py`: Centralized security module (`validate_url`, `resolve_and_check_hostname`, `validate_request_url`, `validate_redirect_target`, `SecurityError`)
- `tests/test_security.py`: 36 deterministic SSRF and URL validation tests with mocked DNS (0 real network calls)

---

### Phase 3 — robots.txt Layer — 2026-09-28

#### Added
- `app/robots.py`: `RobotsChecker` with in-memory TTL caching, conservative failure policy (network error/timeout/HTTP error → block scrape), 404 → allow all (standard semantics), `User-Agent: ScrapeKit/0.1 (+local-web-scraper)`
- `tests/test_robots.py`: 17 deterministic unit tests covering wildcard, specific agent group, allow-overrides-disallow, 404, 500, 403, timeouts, network errors, and cache TTL / clear behavior

---

### Phase 4 — HTTP Fetcher — 2026-09-28

#### Added
- `app/fetcher.py`: `fetch()` pipeline coordinating pre-request SSRF validation, `robots.txt` policy verification, bounded redirect loop (default 5) with SSRF revalidation at each redirect hop, `Content-Type` enforcement (`text/html`), and response body/Content-Length size capping (5 MB)
- `tests/test_fetcher.py`: 20 deterministic tests with mocked HTTP and DNS covering successful retrieval, redirect handling, SSRF redirect blocks, infinite redirect loops, robots disallow blocks, Content-Type enforcement, response size limits, and HTTP status errors

---

### Phase 5 — HTML Parser — 2026-09-28

#### Added
- `app/parser.py`: Structured HTML parser extracting `<title>`, meta description (with OG fallback), canonical URL (absolutized), headings (H1–H6 in document order), hyperlinks with absolutized href and anchor text, all metadata key/values, page text, and content statistics
- `tests/fixtures/`: Real local HTML test fixtures (`basic.html`, `relative_links.html`, `no_meta.html`, `duplicate_links.html`, `malformed.html`)
- `tests/test_parser.py`: 10 comprehensive tests validating field extraction, relative-to-absolute URL resolution, javascript: link filtering, resilience against missing metadata and malformed HTML tags

---

### Phase 6 — HTML Cleaner — 2026-09-28

#### Added
- `app/cleaner.py`: Noise element decomposer (removes `<script>`, `<style>`, `<noscript>`, `<svg>`, `<canvas>`, `<iframe>`, `<template>`, and HTML comments), whitespace normalizer (collapses excess horizontal whitespace and consecutive blank lines into clean paragraphs), link deduplication preserving document order and updating empty anchor text
- `tests/test_cleaner.py`: 12 deterministic unit tests verifying noise tag stripping, comment extraction, whitespace normalization, link deduplication semantics, and end-to-end clean text extraction

#### Changed
- `app/parser.py`: Integrated `cleaner.extract_clean_text` and `cleaner.deduplicate_links` into the HTML parsing pipeline

---

### Phase 7 — Data Model — 2026-09-28

#### Added
- `app/models.py`: Strongly typed dataclasses `ScrapeResult`, `SourceInfo`, `PageInfo`, `ContentInfo`, and `StatsInfo` with ISO UTC timestamp generation and `to_dict()` serialization

---

### Phase 8 — Exporters — 2026-09-28

#### Added
- `app/exporter.py`: URL slug generator (`make_safe_filename`), JSON exporter (`export_json`), and structured Markdown exporter (`export_markdown`, `render_markdown`)
- `tests/test_exporter.py`: 7 deterministic tests validating file slug safety, JSON schema/keys, Markdown headings and link formatting

---

### Phase 9 — CLI Interface — 2026-09-28

#### Added
- `main.py`: Command-line interface with argparse, `--output-dir` and `--verbose` options, clean status reporting, and exit code semantics

---

### Phase 10 — Streamlit UI — 2026-09-28

#### Added
- `app/ui.py`: Streamlit web application providing URL input, live progress, metric cards, interactive tabs for text, headings, links, and raw JSON, and download buttons


