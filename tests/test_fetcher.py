"""Deterministic tests for the HTTP fetcher.

All DNS lookups are mocked via unittest.mock.patch.
All HTTP interactions are mocked via pytest-httpx.
No real network traffic is generated.
"""

from unittest.mock import MagicMock, patch

import httpx
import pytest

from app.fetcher import (
    ContentTypeError,
    FetchError,
    RedirectError,
    ResponseSizeError,
    fetch,
)
from app.robots import RobotsChecker, RobotsError
from app.security import SecurityError

PUBLIC_IPV4 = "93.184.216.34"
PUBLIC_DNS_RESULT = [
    (2, 1, 6, "", (PUBLIC_IPV4, 0)),
]
PRIVATE_DNS_RESULT = [
    (2, 1, 6, "", ("192.168.1.100", 0)),
]
LOOPBACK_DNS_RESULT = [
    (2, 1, 6, "", ("127.0.0.1", 0)),
]


@pytest.fixture(autouse=True)
def mock_dns():
    """Default DNS mock: all hostnames resolve to a safe public IP."""
    with patch("socket.getaddrinfo", return_value=PUBLIC_DNS_RESULT):
        yield


class TestFetchSuccess:
    def test_fetch_html_page_success(self, httpx_mock):
        httpx_mock.add_response(
            url="https://example.com/robots.txt",
            text="User-agent: *\nDisallow:\n",
        )
        httpx_mock.add_response(
            url="https://example.com/page",
            text="<!DOCTYPE html><html><body><h1>Hello World</h1></body></html>",
            headers={"Content-Type": "text/html; charset=utf-8"},
        )

        result = fetch("https://example.com/page")

        assert result.status_code == 200
        assert result.final_url == "https://example.com/page"
        assert result.requested_url == "https://example.com/page"
        assert "Hello World" in result.html
        assert result.robots_allowed is True
        assert result.robots_checked is True

    def test_fetch_with_safe_redirect(self, httpx_mock):
        httpx_mock.add_response(
            url="https://example.com/robots.txt",
            text="User-agent: *\nDisallow:\n",
        )
        httpx_mock.add_response(
            url="https://example.com/start",
            status_code=302,
            headers={"Location": "https://example.com/destination"},
        )
        httpx_mock.add_response(
            url="https://example.com/destination",
            status_code=200,
            text="<html><body><p>Destination</p></body></html>",
            headers={"Content-Type": "text/html"},
        )

        result = fetch("https://example.com/start")

        assert result.status_code == 200
        assert result.final_url == "https://example.com/destination"
        assert "Destination" in result.html

    def test_fetch_relative_redirect(self, httpx_mock):
        httpx_mock.add_response(
            url="https://example.com/robots.txt",
            text="User-agent: *\nDisallow:\n",
        )
        httpx_mock.add_response(
            url="https://example.com/old-path",
            status_code=301,
            headers={"Location": "/new-path"},
        )
        httpx_mock.add_response(
            url="https://example.com/new-path",
            status_code=200,
            text="<html><body><p>New</p></body></html>",
            headers={"Content-Type": "text/html"},
        )

        result = fetch("https://example.com/old-path")

        assert result.final_url == "https://example.com/new-path"
        assert result.status_code == 200


class TestFetchRedirectSecurity:
    def test_redirect_to_private_ip_is_blocked(self, httpx_mock):
        httpx_mock.add_response(
            url="https://example.com/robots.txt",
            text="User-agent: *\nDisallow:\n",
        )
        httpx_mock.add_response(
            url="https://example.com/page",
            status_code=302,
            headers={"Location": "http://192.168.1.1/admin"},
        )

        # DNS resolution for the redirect target resolves to private IP
        with patch("socket.getaddrinfo", side_effect=[PUBLIC_DNS_RESULT, PRIVATE_DNS_RESULT]):
            with pytest.raises(RedirectError, match="Blocked unsafe redirect target"):
                fetch("https://example.com/page")

    def test_redirect_to_loopback_is_blocked(self, httpx_mock):
        httpx_mock.add_response(
            url="https://example.com/robots.txt",
            text="User-agent: *\nDisallow:\n",
        )
        httpx_mock.add_response(
            url="https://example.com/page",
            status_code=302,
            headers={"Location": "http://127.0.0.1:8080/internal"},
        )

        with patch("socket.getaddrinfo", side_effect=[PUBLIC_DNS_RESULT, LOOPBACK_DNS_RESULT]):
            with pytest.raises(RedirectError, match="Blocked unsafe redirect target"):
                fetch("https://example.com/page")

    def test_redirect_to_disallowed_scheme_is_blocked(self, httpx_mock):
        httpx_mock.add_response(
            url="https://example.com/robots.txt",
            text="User-agent: *\nDisallow:\n",
        )
        httpx_mock.add_response(
            url="https://example.com/page",
            status_code=302,
            headers={"Location": "file:///etc/passwd"},
        )

        with pytest.raises(RedirectError, match="Blocked unsafe redirect target"):
            fetch("https://example.com/page")

    def test_redirect_limit_exceeded_raises_error(self, httpx_mock):
        httpx_mock.add_response(
            url="https://example.com/robots.txt",
            text="User-agent: *\nDisallow:\n",
        )
        # 4 redirects when limit is 3 will hit max_redirects limit
        for i in range(4):
            httpx_mock.add_response(
                url=f"https://example.com/hop{i}",
                status_code=302,
                headers={"Location": f"https://example.com/hop{i+1}"},
            )

        with pytest.raises(RedirectError, match="Exceeded maximum redirect limit"):
            fetch("https://example.com/hop0", max_redirects=3)

    def test_redirect_missing_location_header_raises_error(self, httpx_mock):
        httpx_mock.add_response(
            url="https://example.com/robots.txt",
            text="User-agent: *\nDisallow:\n",
        )
        httpx_mock.add_response(
            url="https://example.com/page",
            status_code=302,
            # No Location header
        )

        with pytest.raises(RedirectError, match="missing Location header"):
            fetch("https://example.com/page")


class TestFetchRobotsEnforcement:
    def test_robots_disallow_blocks_scrape(self, httpx_mock):
        httpx_mock.add_response(
            url="https://example.com/robots.txt",
            text="User-agent: *\nDisallow: /secret/\n",
        )

        with pytest.raises(RobotsError, match="robots.txt disallows"):
            fetch("https://example.com/secret/data")

    def test_robots_error_blocks_scrape(self, httpx_mock):
        httpx_mock.add_response(
            url="https://example.com/robots.txt",
            status_code=500,
        )

        with pytest.raises(RobotsError, match="HTTP 500"):
            fetch("https://example.com/page")

    def test_bypass_robots_when_disabled(self, httpx_mock):
        httpx_mock.add_response(
            url="https://example.com/page",
            text="<html><body><p>Content</p></body></html>",
            headers={"Content-Type": "text/html"},
        )

        result = fetch("https://example.com/page", check_robots=False)

        assert result.robots_checked is False
        assert result.robots_allowed is False
        assert "Content" in result.html


class TestFetchContentAndSizeLimits:
    def test_non_html_content_type_rejected(self, httpx_mock):
        httpx_mock.add_response(
            url="https://example.com/robots.txt",
            text="User-agent: *\nDisallow:\n",
        )
        httpx_mock.add_response(
            url="https://example.com/file.pdf",
            text="%PDF-1.4 ...",
            headers={"Content-Type": "application/pdf"},
        )

        with pytest.raises(ContentTypeError, match="Unsupported Content-Type 'application/pdf'"):
            fetch("https://example.com/file.pdf")

    def test_json_content_type_rejected(self, httpx_mock):
        httpx_mock.add_response(
            url="https://example.com/robots.txt",
            text="User-agent: *\nDisallow:\n",
        )
        httpx_mock.add_response(
            url="https://example.com/api/data",
            text='{"key": "value"}',
            headers={"Content-Type": "application/json"},
        )

        with pytest.raises(ContentTypeError, match="Unsupported Content-Type"):
            fetch("https://example.com/api/data")

    def test_response_size_exceeding_content_length_header(self, httpx_mock):
        httpx_mock.add_response(
            url="https://example.com/robots.txt",
            text="User-agent: *\nDisallow:\n",
        )
        httpx_mock.add_response(
            url="https://example.com/big",
            text="<html>big</html>",
            headers={"Content-Type": "text/html", "Content-Length": "10000000"},
        )

        with pytest.raises(ResponseSizeError, match="exceeds maximum limit"):
            fetch("https://example.com/big", max_bytes=1000)

    def test_response_size_exceeding_body_length(self, httpx_mock):
        httpx_mock.add_response(
            url="https://example.com/robots.txt",
            text="User-agent: *\nDisallow:\n",
        )
        httpx_mock.add_response(
            url="https://example.com/big",
            text="<html>" + ("x" * 2000) + "</html>",
            headers={"Content-Type": "text/html"},
        )

        with pytest.raises(ResponseSizeError, match="exceeds"):
            fetch("https://example.com/big", max_bytes=500)

    def test_empty_response_raises_error(self, httpx_mock):
        httpx_mock.add_response(
            url="https://example.com/robots.txt",
            text="User-agent: *\nDisallow:\n",
        )
        httpx_mock.add_response(
            url="https://example.com/empty",
            text="   \n  ",
            headers={"Content-Type": "text/html"},
        )

        with pytest.raises(FetchError, match="Received empty HTML response"):
            fetch("https://example.com/empty")


class TestFetchHttpErrors:
    def test_http_404_raises_fetch_error_when_raise_for_status(self, httpx_mock):
        httpx_mock.add_response(
            url="https://example.com/robots.txt",
            text="User-agent: *\nDisallow:\n",
        )
        httpx_mock.add_response(
            url="https://example.com/missing",
            status_code=404,
            text="<html>404 Not Found</html>",
            headers={"Content-Type": "text/html"},
        )

        with pytest.raises(FetchError) as exc_info:
            fetch("https://example.com/missing")
        assert exc_info.value.status_code == 404

    def test_http_500_raises_fetch_error(self, httpx_mock):
        httpx_mock.add_response(
            url="https://example.com/robots.txt",
            text="User-agent: *\nDisallow:\n",
        )
        httpx_mock.add_response(
            url="https://example.com/server-error",
            status_code=500,
            headers={"Content-Type": "text/html"},
        )

        with pytest.raises(FetchError) as exc_info:
            fetch("https://example.com/server-error")
        assert exc_info.value.status_code == 500

    def test_timeout_raises_fetch_error(self, httpx_mock):
        httpx_mock.add_response(
            url="https://example.com/robots.txt",
            text="User-agent: *\nDisallow:\n",
        )
        httpx_mock.add_exception(
            httpx.ReadTimeout("Read timed out"),
            url="https://example.com/timeout",
        )

        with pytest.raises(FetchError, match="timed out"):
            fetch("https://example.com/timeout")

    def test_initial_url_private_ip_rejected_by_ssrf(self):
        with patch("socket.getaddrinfo", return_value=PRIVATE_DNS_RESULT):
            with pytest.raises(SecurityError, match="private or reserved address"):
                fetch("https://internal.corp/admin")
