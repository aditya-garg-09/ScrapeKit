"""HTML Parser module.

Extracts structured data from HTML pages:
  - Title
  - Meta description
  - Canonical URL (absolutized)
  - Headings (H1–H6 in document order)
  - Links (href absolutized, with anchor text)
  - Meta tags (all key/value pairs)
  - Page text
  - Basic content statistics

Security note:
  This module strictly processes HTML markup using BeautifulSoup.
  No networking, DNS lookups, or security validation live here.
"""

import logging
import re
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from app.cleaner import deduplicate_links, extract_clean_text

logger = logging.getLogger(__name__)


@dataclass
class HeadingItem:
    level: int
    text: str

    def to_dict(self) -> dict[str, Any]:
        return {"level": self.level, "text": self.text}


@dataclass
class LinkItem:
    href: str
    text: str

    def to_dict(self) -> dict[str, str]:
        return {"href": self.href, "text": self.text}


@dataclass
class ParsedContent:
    title: str = ""
    description: str = ""
    canonical_url: str | None = None
    headings: list[dict[str, Any]] = field(default_factory=list)
    links: list[dict[str, str]] = field(default_factory=list)
    meta_tags: dict[str, str] = field(default_factory=dict)
    text: str = ""
    stats: dict[str, int] = field(default_factory=dict)


def _get_soup(html: str) -> BeautifulSoup:
    """Parse HTML with lxml parser if available, falling back to html.parser."""
    try:
        return BeautifulSoup(html, "lxml")
    except Exception:
        return BeautifulSoup(html, "html.parser")


def extract_title(soup: BeautifulSoup) -> str:
    """Extract page title from <title> tag, or fallback to og:title."""
    title_tag = soup.find("title")
    if title_tag and title_tag.string:
        return title_tag.get_text().strip()

    og_title = soup.find("meta", property="og:title")
    if og_title and og_title.get("content"):
        return str(og_title["content"]).strip()

    return ""


def extract_description(soup: BeautifulSoup) -> str:
    """Extract meta description from name='description' or og:description."""
    desc_tag = soup.find("meta", attrs={"name": re.compile(r"^description$", re.I)})
    if desc_tag and desc_tag.get("content"):
        return str(desc_tag["content"]).strip()

    og_desc = soup.find("meta", property=re.compile(r"^og:description$", re.I))
    if og_desc and og_desc.get("content"):
        return str(og_desc["content"]).strip()

    return ""


def extract_canonical(soup: BeautifulSoup, base_url: str = "") -> str | None:
    """Extract and absolutize canonical URL from <link rel='canonical'>."""
    canonical_tag = soup.find("link", rel=re.compile(r"^canonical$", re.I))
    if canonical_tag and canonical_tag.get("href"):
        href = str(canonical_tag["href"]).strip()
        if href:
            return urljoin(base_url, href) if base_url else href
    return None


def extract_headings(soup: BeautifulSoup) -> list[dict[str, Any]]:
    """Extract H1-H6 headings in document order."""
    headings: list[dict[str, Any]] = []
    heading_tags = soup.find_all(re.compile(r"^h[1-6]$", re.I))
    for tag in heading_tags:
        text = tag.get_text().strip()
        if text:
            try:
                level = int(tag.name[1])
            except (IndexError, ValueError):
                level = 1
            headings.append({"level": level, "text": text})
    return headings


def extract_links(soup: BeautifulSoup, base_url: str = "") -> list[dict[str, str]]:
    """Extract all hyperlinks with absolutized href and trimmed anchor text."""
    links: list[dict[str, str]] = []
    for a in soup.find_all("a", href=True):
        raw_href = str(a["href"]).strip()
        if not raw_href or raw_href.startswith("javascript:"):
            continue

        resolved_href = urljoin(base_url, raw_href) if base_url else raw_href
        anchor_text = a.get_text().strip()
        links.append({"href": resolved_href, "text": anchor_text})
    return links


def extract_meta_tags(soup: BeautifulSoup) -> dict[str, str]:
    """Extract all metadata key/value pairs from <meta> tags."""
    meta_dict: dict[str, str] = {}
    for meta in soup.find_all("meta"):
        key = meta.get("name") or meta.get("property") or meta.get("http-equiv")
        content = meta.get("content")
        if key and content is not None:
            meta_dict[str(key).strip()] = str(content).strip()
    return meta_dict


def compute_stats(text: str, headings: list[dict[str, Any]], links: list[dict[str, str]]) -> dict[str, int]:
    """Compute character, word, heading, and link counts."""
    words = text.split()
    return {
        "word_count": len(words),
        "character_count": len(text),
        "heading_count": len(headings),
        "link_count": len(links),
    }


def parse_html(html: str, base_url: str = "") -> ParsedContent:
    """Parse HTML and extract all structured content elements.

    Args:
        html: Raw HTML string.
        base_url: Optional base URL for resolving relative links/canonical.

    Returns:
        ParsedContent dataclass.
    """
    if not html or not html.strip():
        return ParsedContent()

    logger.debug("Parsing HTML (length: %d chars, base_url: %s)", len(html), base_url)
    soup = _get_soup(html)

    title = extract_title(soup)
    description = extract_description(soup)
    canonical = extract_canonical(soup, base_url)
    headings = extract_headings(soup)
    raw_links = extract_links(soup, base_url)
    links = deduplicate_links(raw_links)
    meta_tags = extract_meta_tags(soup)
    clean_text = extract_clean_text(soup)
    stats = compute_stats(clean_text, headings, links)

    return ParsedContent(
        title=title,
        description=description,
        canonical_url=canonical,
        headings=headings,
        links=links,
        meta_tags=meta_tags,
        text=clean_text,
        stats=stats,
    )
