"""Export module for ScrapeKit.

Saves structured ScrapeResult objects as JSON and Markdown files.
Generates filesystem-safe, clean file slugs based on domain and path.
"""

import json
import logging
import re
from pathlib import Path
from urllib.parse import urlparse

from app.models import ScrapeResult

logger = logging.getLogger(__name__)


def make_safe_filename(url: str, max_length: int = 80) -> str:
    """Derive a safe filesystem slug from a URL.

    Example:
        https://example.com/blog/article-1 -> example-com-blog-article-1
    """
    parsed = urlparse(url)
    netloc = parsed.netloc or "page"
    path = parsed.path or ""

    # Combine host and path
    combined = f"{netloc}{path}".strip("/")

    # Replace all non-alphanumeric chars with hyphens
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", combined).strip("-").lower()

    if not slug:
        slug = "scrape-output"

    return slug[:max_length].rstrip("-")


def export_json(result: ScrapeResult, output_dir: Path | str) -> Path:
    """Export ScrapeResult as a formatted JSON file.

    Returns the Path of the saved file.
    """
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    slug = make_safe_filename(result.source.requested_url)
    file_path = out_path / f"{slug}.json"

    data = result.to_dict()
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    logger.info("Exported JSON scrape result to %s", file_path)
    return file_path


def render_markdown(result: ScrapeResult) -> str:
    """Generate Markdown representation of a ScrapeResult."""
    title = result.page.title or "Untitled Page"
    lines = [
        f"# {title}",
        "",
        f"- **Requested URL**: {result.source.requested_url}",
        f"- **Final URL**: {result.source.final_url}",
        f"- **Scraped At**: {result.scraped_at}",
        f"- **Status**: {result.source.status_code} ({result.source.content_type})",
        f"- **robots.txt**: {'Allowed' if result.source.robots_allowed else 'Blocked'}",
    ]

    if result.page.canonical_url:
        lines.append(f"- **Canonical URL**: {result.page.canonical_url}")
    if result.page.description:
        lines.append(f"- **Description**: {result.page.description}")

    lines.extend([
        "",
        f"**Stats**: {result.stats.word_count} words | {result.stats.character_count} characters | "
        f"{result.stats.heading_count} headings | {result.stats.link_count} links",
        "",
    ])

    if result.content.headings:
        lines.append("## Headings")
        lines.append("")
        for h in result.content.headings:
            level = h.get("level", 1)
            prefix = "#" * min(level, 6)
            lines.append(f"{prefix} {h.get('text', '')}")
        lines.append("")

    if result.content.links:
        lines.append("## Links")
        lines.append("")
        for link in result.content.links:
            href = link.get("href", "")
            text = link.get("text", "") or href
            lines.append(f"- [{text}]({href})")
        lines.append("")

    lines.append("## Content")
    lines.append("")
    lines.append(result.content.text or "*No visible text extracted.*")
    lines.append("")

    return "\n".join(lines)


def export_markdown(result: ScrapeResult, output_dir: Path | str) -> Path:
    """Export ScrapeResult as a clean Markdown file.

    Returns the Path of the saved file.
    """
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    slug = make_safe_filename(result.source.requested_url)
    file_path = out_path / f"{slug}.md"

    md_content = render_markdown(result)
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(md_content)

    logger.info("Exported Markdown scrape result to %s", file_path)
    return file_path
