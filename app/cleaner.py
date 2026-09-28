"""HTML Cleaner module.

Responsible for removing noise and normalizing content:
  - Decomposes non-content HTML elements (<script>, <style>, <noscript>, <svg>, <canvas>, <iframe>, <template>).
  - Strips HTML comments.
  - Normalizes excessive whitespace and collapses redundant blank lines while preserving paragraph boundaries.
  - Deduplicates extracted links while maintaining document order.

Security note:
  This module only sanitizes text and markup structure for clean presentation/export.
  Network security and SSRF validation are strictly in app/security.py.
"""

import logging
import re
from typing import Any

from bs4 import BeautifulSoup, Comment

logger = logging.getLogger(__name__)

# Non-content tags that should be completely removed before text extraction
NOISE_TAGS: frozenset[str] = frozenset({
    "script",
    "style",
    "noscript",
    "svg",
    "canvas",
    "iframe",
    "template",
    "object",
    "embed",
})


def remove_noise_elements(soup: BeautifulSoup) -> None:
    """Decompose noise tags and strip HTML comments from BeautifulSoup tree in-place."""
    for tag_name in NOISE_TAGS:
        for element in soup.find_all(tag_name):
            element.decompose()

    for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
        comment.extract()


def normalize_whitespace(text: str) -> str:
    """Normalize text whitespace.

    - Replaces tabs and non-breaking spaces with standard space.
    - Strips trailing/leading spaces per line.
    - Collapses 3 or more consecutive newlines into double newlines (\n\n)
      to preserve paragraph breaks without excessive blank space.
    - Strips overall leading and trailing whitespace.
    """
    if not text:
        return ""

    # Replace non-breaking spaces and tabs with regular space
    text = text.replace("\xa0", " ").replace("\t", " ")

    # Collapse horizontal whitespace within each line
    lines = [re.sub(r" {2,}", " ", line).strip() for line in text.splitlines()]

    # Reassemble with single newlines
    joined = "\n".join(lines)

    # Collapse multiple consecutive blank lines into double newlines
    normalized = re.sub(r"\n{3,}", "\n\n", joined)

    return normalized.strip()


def extract_clean_text(soup: BeautifulSoup) -> str:
    """Extract visible page text after removing noise elements and formatting paragraphs."""
    # Work on a copy if needed, or if caller already called remove_noise_elements
    remove_noise_elements(soup)

    # Extract block elements separated by newlines
    raw_text = soup.get_text(separator="\n")
    return normalize_whitespace(raw_text)


def deduplicate_links(links: list[dict[str, str]]) -> list[dict[str, str]]:
    """Deduplicate links by href while preserving document order.

    If an earlier occurrence has empty anchor text and a later occurrence
    has descriptive text, updates the anchor text.
    """
    seen: dict[str, dict[str, str]] = {}
    for link in links:
        href = link.get("href", "").strip()
        if not href:
            continue

        text = link.get("text", "").strip()

        if href not in seen:
            seen[href] = {"href": href, "text": text}
        else:
            # Upgrade text if previous was empty
            if not seen[href]["text"] and text:
                seen[href]["text"] = text

    return list(seen.values())
