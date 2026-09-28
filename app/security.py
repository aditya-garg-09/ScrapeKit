"""URL validation and SSRF protection layer.

Every URL — initial target, robots.txt URL, and every redirect destination —
must pass through this module before any network request is made.

Security is centralized here. No security checks live in parser, cleaner, or exporter.
"""

import logging
import socket
from urllib.parse import urlparse, urlunparse

from app.validators import is_public_ip

logger = logging.getLogger(__name__)

ALLOWED_SCHEMES: frozenset[str] = frozenset({"http", "https"})


class SecurityError(Exception):
    """Raised when a URL fails any security validation check."""


def validate_url(url: str) -> str:
    """Validate URL scheme and structure. Return a normalized URL.

    Accepts only ``http://`` and ``https://``.
    Strips fragment identifiers (not sent to server).
    Normalizes scheme and hostname to lowercase.

    Raises:
        SecurityError: For empty URLs, unsupported schemes, or missing hostname.
    """
    url = url.strip()
    if not url:
        raise SecurityError("URL must not be empty.")

    try:
        parsed = urlparse(url)
    except Exception as exc:
        raise SecurityError(f"Malformed URL: {exc}") from exc

    scheme = parsed.scheme.lower()
    if scheme not in ALLOWED_SCHEMES:
        if scheme:
            raise SecurityError(
                f"Unsupported URL scheme '{parsed.scheme}'. "
                "Only http and https are allowed."
            )
        raise SecurityError(
            f"URL has no recognizable scheme: '{url}'. "
            "Only http and https are allowed."
        )

    if not parsed.netloc:
        raise SecurityError(f"URL has no hostname: '{url}'.")

    # Normalize: lowercase scheme + host, strip fragment
    normalized = urlunparse((
        scheme,
        parsed.netloc.lower(),
        parsed.path,
        parsed.params,
        parsed.query,
        "",  # fragment — never sent to the server
    ))
    return normalized


def resolve_and_check_hostname(hostname: str) -> list[str]:
    """Resolve *hostname* to IP addresses and verify all are publicly routable.

    DNS-resolves the hostname and rejects the request if any returned address
    falls within a private, reserved, loopback, link-local, or otherwise
    non-public range.

    Returns:
        List of resolved IP strings.

    Raises:
        SecurityError: If DNS fails or any IP is private/reserved.
    """
    hostname = hostname.rstrip(".").lower()  # strip trailing FQDN dot

    if not hostname:
        raise SecurityError("Hostname is empty after normalization.")

    logger.debug("DNS-resolving '%s' for SSRF validation.", hostname)

    try:
        results = socket.getaddrinfo(hostname, None)
    except socket.gaierror as exc:
        raise SecurityError(
            f"DNS resolution failed for '{hostname}': {exc}"
        ) from exc

    if not results:
        raise SecurityError(f"No DNS results returned for '{hostname}'.")

    resolved_ips: list[str] = []
    for _family, _type, _proto, _canonname, sockaddr in results:
        ip = sockaddr[0]
        resolved_ips.append(ip)
        if not is_public_ip(ip):
            raise SecurityError(
                f"Hostname '{hostname}' resolves to a private or reserved "
                f"address ({ip}). Request blocked for SSRF protection."
            )

    logger.debug("Hostname '%s' resolved to %s — all addresses public.", hostname, resolved_ips)
    return resolved_ips


def validate_request_url(url: str) -> str:
    """Full pre-request validation: scheme, structure, DNS, and IP safety.

    Returns:
        Normalized URL if all checks pass.

    Raises:
        SecurityError: On any validation failure.
    """
    logger.info("Validating URL: %s", url)
    normalized = validate_url(url)

    parsed = urlparse(normalized)
    hostname = parsed.hostname or ""
    resolve_and_check_hostname(hostname)

    logger.info("SSRF validation passed: %s", normalized)
    return normalized


def validate_redirect_target(redirect_url: str) -> str:
    """Re-run full SSRF validation on a redirect destination.

    Must be called before following any HTTP redirect.

    Returns:
        Normalized redirect URL if safe.

    Raises:
        SecurityError: If the redirect target is unsafe.
    """
    logger.info("Validating redirect target: %s", redirect_url)
    return validate_request_url(redirect_url)
