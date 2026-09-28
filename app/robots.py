"""robots.txt fetching, parsing, in-memory caching, and policy enforcement.

Failure policy (conservative):
  - robots.txt timeout or connection error  → block scrape
  - robots.txt returns non-200 / non-404    → block scrape
  - robots.txt returns 404                  → allow all  (standard semantics)
  - robots.txt parse error                  → block scrape

This is documented in README.md under "robots.txt Behavior".
"""

import logging
import time
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import httpx

logger = logging.getLogger(__name__)

USER_AGENT: str = "ScrapeKit/0.1 (+local-web-scraper)"

ROBOTS_CACHE_TTL: int = 300          # seconds per origin
ROBOTS_CONNECT_TIMEOUT: float = 10.0
ROBOTS_READ_TIMEOUT: float = 15.0
ROBOTS_MAX_BYTES: int = 512 * 1024   # cap robots.txt at 512 KB


class RobotsError(Exception):
    """Raised when robots.txt cannot be safely fetched or parsing fails."""


class RobotsChecker:
    """Fetches, parses, and caches robots.txt for each origin.

    Thread-safety: not thread-safe. Designed for single-threaded local use.

    Example::

        checker = RobotsChecker()
        if not checker.is_allowed("https://example.com/page"):
            raise RobotsError("robots.txt disallows this URL")
    """

    def __init__(self, cache_ttl: int = ROBOTS_CACHE_TTL) -> None:
        # origin → (parser | None, fetched_at_monotonic)
        self._cache: dict[str, tuple[RobotFileParser | None, float]] = {}
        self._cache_ttl = cache_ttl

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def is_allowed(self, url: str) -> bool:
        """Return True if the URL is allowed by the site's robots.txt.

        Returns:
            True  → scraping permitted.
            False → scraping disallowed by robots.txt.

        Raises:
            RobotsError: If robots.txt could not be safely retrieved.
        """
        parsed = urlparse(url)
        origin = f"{parsed.scheme}://{parsed.netloc}"

        parser = self._get_parser(origin)

        if parser is None:
            # 404 → no robots.txt present → allow all (standard semantics)
            logger.info("No robots.txt at %s — treating as allow all.", origin)
            return True

        allowed = parser.can_fetch(USER_AGENT, url)
        if not allowed:
            logger.warning(
                "robots.txt at %s disallows '%s' from %s.",
                origin, USER_AGENT, url,
            )
        return allowed

    def clear_cache(self) -> None:
        """Evict all cached robots.txt entries."""
        self._cache.clear()
        logger.debug("robots.txt cache cleared.")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_parser(self, origin: str) -> RobotFileParser | None:
        """Return a cached or freshly fetched parser for *origin*.

        Returns None for a 404 (allow all).
        Raises RobotsError on any fetch failure.
        """
        now = time.monotonic()
        if origin in self._cache:
            parser, fetched_at = self._cache[origin]
            if now - fetched_at < self._cache_ttl:
                logger.debug("robots.txt cache hit for %s.", origin)
                return parser
            logger.debug("robots.txt cache expired for %s — re-fetching.", origin)

        parser = self._fetch_and_parse(origin)
        self._cache[origin] = (parser, now)
        return parser

    def _fetch_and_parse(self, origin: str) -> RobotFileParser | None:
        """Fetch robots.txt from *origin* and return a parser.

        Returns None for HTTP 404 (standard: allow all).
        Raises RobotsError for network failures or unexpected status codes.
        """
        robots_url = f"{origin}/robots.txt"
        logger.info("Fetching robots.txt: %s", robots_url)

        try:
            with httpx.Client(
                follow_redirects=True,
                max_redirects=3,
                timeout=httpx.Timeout(
                    connect=ROBOTS_CONNECT_TIMEOUT,
                    read=ROBOTS_READ_TIMEOUT,
                    write=5.0,
                    pool=5.0,
                ),
            ) as client:
                response = client.get(
                    robots_url,
                    headers={"User-Agent": USER_AGENT},
                )
        except httpx.TimeoutException as exc:
            raise RobotsError(
                f"robots.txt fetch timed out for {origin}. "
                "Scrape blocked (conservative policy)."
            ) from exc
        except httpx.RequestError as exc:
            raise RobotsError(
                f"robots.txt could not be retrieved for {origin}: {exc}. "
                "Scrape blocked."
            ) from exc

        if response.status_code == 404:
            logger.info(
                "robots.txt absent (404) at %s — allow all (standard semantics).", origin
            )
            return None

        if response.status_code != 200:
            raise RobotsError(
                f"robots.txt returned HTTP {response.status_code} for {origin}. "
                "Scrape blocked (conservative policy)."
            )

        content = response.text[:ROBOTS_MAX_BYTES]
        logger.debug("Parsing robots.txt for %s (%d chars).", origin, len(content))

        parser = RobotFileParser()
        parser.set_url(robots_url)
        try:
            parser.parse(content.splitlines())
        except Exception as exc:
            raise RobotsError(
                f"Failed to parse robots.txt for {origin}: {exc}. "
                "Scrape blocked (conservative policy)."
            ) from exc

        return parser
