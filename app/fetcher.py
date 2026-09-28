"""HTTP Fetcher module.

Wires URL validation, SSRF protection, robots.txt verification, and safe HTTP
fetching into a robust pipeline.

Security controls enforced:
  - Pre-request URL validation and DNS SSRF verification.
  - robots.txt checked before fetching any target content.
  - Redirect interception with SSRF re-validation on every redirect hop.
  - Bounded redirect limit (default 5).
  - Connect and read timeouts to prevent hanging.
  - Content-Type enforcement (HTML only).
  - Maximum response body size limits (default 5 MB).
"""

import logging
from dataclasses import dataclass
from urllib.parse import urljoin, urlparse

import httpx

from app.robots import RobotsChecker, RobotsError, USER_AGENT
from app.security import (
    SecurityError,
    validate_redirect_target,
    validate_request_url,
)

logger = logging.getLogger(__name__)

CONNECT_TIMEOUT: float = 10.0
READ_TIMEOUT: float = 20.0
MAX_REDIRECTS: int = 5
MAX_RESPONSE_BYTES: int = 5 * 1024 * 1024  # 5 MB
ALLOWED_CONTENT_TYPES: tuple[str, ...] = ("text/html", "application/xhtml+xml")


class FetchError(Exception):
    """Base exception for HTTP fetch failures."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class ContentTypeError(FetchError):
    """Raised when the response is not valid HTML."""


class ResponseSizeError(FetchError):
    """Raised when the response exceeds maximum allowed size."""


class RedirectError(FetchError):
    """Raised on redirect loop, max redirects exceeded, or unsafe redirect."""


@dataclass
class FetchResult:
    """Result of a safe HTTP fetch operation."""

    requested_url: str
    final_url: str
    status_code: int
    content_type: str
    html: str
    robots_checked: bool
    robots_allowed: bool
    robots_url: str


def fetch(
    url: str,
    *,
    robots_checker: RobotsChecker | None = None,
    client: httpx.Client | None = None,
    max_redirects: int = MAX_REDIRECTS,
    max_bytes: int = MAX_RESPONSE_BYTES,
    connect_timeout: float = CONNECT_TIMEOUT,
    read_timeout: float = READ_TIMEOUT,
    check_robots: bool = True,
    raise_for_status: bool = True,
) -> FetchResult:
    """Safely fetch HTML content from *url*.

    Pipeline:
      1. SSRF validation of initial URL.
      2. robots.txt policy check (if check_robots is True).
      3. HTTP GET with manual redirect loop.
      4. SSRF re-validation on every redirect hop.
      5. Content-Type and response size checks.

    Returns:
      FetchResult containing retrieved HTML and metadata.

    Raises:
      SecurityError: If any target or redirect IP/scheme is unsafe.
      RobotsError: If robots.txt cannot be safely fetched or disallows the URL.
      FetchError: On network errors, timeouts, non-HTML content, or HTTP error codes.
    """
    logger.info("Starting scrape fetch for %s", url)

    # 1. SSRF validation on initial URL
    logger.debug("Validating URL and SSRF safety: %s", url)
    normalized_url = validate_request_url(url)

    # 2. robots.txt check
    parsed_initial = urlparse(normalized_url)
    origin = f"{parsed_initial.scheme}://{parsed_initial.netloc}"
    robots_url = f"{origin}/robots.txt"
    robots_checked = False
    robots_allowed = False

    if check_robots:
        checker = robots_checker or RobotsChecker()
        logger.info("Checking robots.txt for %s", normalized_url)
        robots_checked = True
        try:
            allowed = checker.is_allowed(normalized_url)
        except RobotsError as exc:
            logger.error("robots.txt retrieval failed: %s", exc)
            raise

        if not allowed:
            logger.warning("Scrape blocked: robots.txt disallows %s", normalized_url)
            raise RobotsError(
                f"Scrape blocked: robots.txt disallows '{USER_AGENT}' from accessing '{normalized_url}'."
            )
        robots_allowed = True
        logger.info("robots.txt allows target: %s", normalized_url)

    # 3. HTTP GET with manual redirect inspection
    current_url = normalized_url
    redirect_count = 0
    timeout = httpx.Timeout(
        connect=connect_timeout,
        read=read_timeout,
        write=5.0,
        pool=5.0,
    )
    headers = {"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml"}

    should_close_client = False
    if client is None:
        client = httpx.Client(follow_redirects=False, timeout=timeout)
        should_close_client = True

    try:
        while True:
            logger.info("Fetching page: %s (redirect hop %d)", current_url, redirect_count)
            try:
                response = client.get(current_url, headers=headers)
            except httpx.TimeoutException as exc:
                raise FetchError(f"Request to '{current_url}' timed out: {exc}") from exc
            except httpx.RequestError as exc:
                raise FetchError(f"Network error connecting to '{current_url}': {exc}") from exc

            # Handle redirects
            if response.is_redirect:
                redirect_count += 1
                if redirect_count > max_redirects:
                    raise RedirectError(
                        f"Exceeded maximum redirect limit of {max_redirects}."
                    )

                location = response.headers.get("Location")
                if not location:
                    raise RedirectError(
                        f"Redirect response {response.status_code} from '{current_url}' missing Location header."
                    )

                next_url = urljoin(current_url, location)
                logger.info("Redirect detected: %s -> %s", current_url, next_url)

                # Revalidate redirect target for SSRF
                try:
                    next_url = validate_redirect_target(next_url)
                except SecurityError as exc:
                    logger.error("Blocked unsafe redirect target %s: %s", next_url, exc)
                    raise RedirectError(f"Blocked unsafe redirect target '{next_url}': {exc}") from exc

                current_url = next_url
                continue

            break

        # Check HTTP status code
        if raise_for_status and response.is_error:
            raise FetchError(
                f"HTTP request failed with status {response.status_code} ({response.reason_phrase}).",
                status_code=response.status_code,
            )

        # Check response size via header first
        content_length_hdr = response.headers.get("Content-Length")
        if content_length_hdr:
            try:
                cl = int(content_length_hdr)
                if cl > max_bytes:
                    raise ResponseSizeError(
                        f"Response size ({cl} bytes) exceeds maximum limit of {max_bytes} bytes."
                    )
            except ValueError:
                pass

        # Check actual body size
        content_bytes = response.content
        if len(content_bytes) > max_bytes:
            raise ResponseSizeError(
                f"Response body length ({len(content_bytes)} bytes) exceeds limit of {max_bytes} bytes."
            )

        # Check content type
        content_type = response.headers.get("Content-Type", "")
        ct_lower = content_type.lower()
        if not any(allowed in ct_lower for allowed in ALLOWED_CONTENT_TYPES):
            raise ContentTypeError(
                f"Unsupported Content-Type '{content_type}'. ScrapeKit only processes HTML content."
            )

        # Empty response check
        html_text = response.text
        if not html_text.strip():
            raise FetchError("Received empty HTML response from server.", status_code=response.status_code)

        logger.info(
            "Fetch succeeded for %s (status=%d, bytes=%d)",
            current_url,
            response.status_code,
            len(content_bytes),
        )

        return FetchResult(
            requested_url=url,
            final_url=current_url,
            status_code=response.status_code,
            content_type=content_type,
            html=html_text,
            robots_checked=robots_checked,
            robots_allowed=robots_allowed,
            robots_url=robots_url,
        )

    finally:
        if should_close_client:
            client.close()
