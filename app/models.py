"""Data models for ScrapeKit.

Defines typed, structured dataclasses for scrape results and export payloads.
"""

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


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
    headings: list[dict[str, Any]]
    links: list[dict[str, str]]
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
    scraped_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> dict[str, Any]:
        """Convert ScrapeResult to a JSON-serializable dictionary."""
        return asdict(self)
