"""CLI entry point for ScrapeKit.

Usage:
    python main.py <url>
    python main.py https://example.com
    python main.py --help
"""

import argparse
import logging
import sys
from pathlib import Path

from app.exporter import export_json, export_markdown
from app.fetcher import ContentTypeError, FetchError, RedirectError, ResponseSizeError, fetch
from app.models import ContentInfo, PageInfo, ScrapeResult, SourceInfo, StatsInfo
from app.parser import parse_html
from app.robots import RobotsChecker, RobotsError
from app.security import SecurityError

OUTPUTS_DIR = Path("outputs")


def setup_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def scrape_url(url: str, output_dir: Path = OUTPUTS_DIR, verbose: bool = False) -> ScrapeResult:
    """Run full scraping pipeline on *url* and export structured outputs."""
    setup_logging(verbose)
    logger = logging.getLogger("scrapekit")
    logger.info("Starting scrape pipeline for: %s", url)

    # 1. Fetch page with SSRF and robots validation
    robots_checker = RobotsChecker()
    fetch_result = fetch(url, robots_checker=robots_checker)

    # 2. Parse HTML and clean text
    parsed = parse_html(fetch_result.html, base_url=fetch_result.final_url)

    # 3. Assemble ScrapeResult
    result = ScrapeResult(
        source=SourceInfo(
            requested_url=fetch_result.requested_url,
            final_url=fetch_result.final_url,
            status_code=fetch_result.status_code,
            content_type=fetch_result.content_type,
            robots_checked=fetch_result.robots_checked,
            robots_allowed=fetch_result.robots_allowed,
            robots_url=fetch_result.robots_url,
        ),
        page=PageInfo(
            title=parsed.title,
            description=parsed.description,
            canonical_url=parsed.canonical_url,
        ),
        content=ContentInfo(
            headings=parsed.headings,
            links=parsed.links,
            text=parsed.text,
        ),
        stats=StatsInfo(
            word_count=parsed.stats.get("word_count", 0),
            character_count=parsed.stats.get("character_count", 0),
            heading_count=parsed.stats.get("heading_count", 0),
            link_count=parsed.stats.get("link_count", 0),
        ),
    )

    # 4. Export JSON & Markdown
    json_path = export_json(result, output_dir)
    md_path = export_markdown(result, output_dir)

    return result, json_path, md_path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="ScrapeKit: Local, secure, robots-respecting web scraper.",
        prog="scrapekit",
    )
    parser.add_argument("url", help="Target public HTTP/HTTPS URL to scrape")
    parser.add_argument(
        "--output-dir",
        "-o",
        default="outputs",
        help="Directory to save JSON and Markdown results (default: outputs)",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable detailed debug logs",
    )

    args = parser.parse_args()

    try:
        result, json_path, md_path = scrape_url(
            args.url,
            output_dir=Path(args.output_dir),
            verbose=args.verbose,
        )

        print("\nScrape completed\n")
        print(f"Title: {result.page.title or '(No title)'}")
        print(f"Words: {result.stats.word_count}")
        print(f"Headings: {result.stats.heading_count}")
        print(f"Links: {result.stats.link_count}")
        print(f"Robots: {'Allowed' if result.source.robots_allowed else 'Blocked'}\n")
        print(f"JSON: {json_path}")
        print(f"Markdown: {md_path}")
        sys.exit(0)

    except SecurityError as exc:
        print(f"\nScrape blocked: Security validation failed\nReason: {exc}", file=sys.stderr)
        sys.exit(1)
    except RobotsError as exc:
        print(f"\nScrape blocked: robots.txt policy\nReason: {exc}", file=sys.stderr)
        sys.exit(1)
    except ContentTypeError as exc:
        print(f"\nScrape failed: Non-HTML content\nReason: {exc}", file=sys.stderr)
        sys.exit(1)
    except ResponseSizeError as exc:
        print(f"\nScrape failed: Response size exceeded limit\nReason: {exc}", file=sys.stderr)
        sys.exit(1)
    except RedirectError as exc:
        print(f"\nScrape failed: Redirect error\nReason: {exc}", file=sys.stderr)
        sys.exit(1)
    except FetchError as exc:
        print(f"\nScrape failed: Fetch error\nReason: {exc}", file=sys.stderr)
        sys.exit(1)
    except Exception as exc:
        print(f"\nScrape failed: Unexpected error\nReason: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
