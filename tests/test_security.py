"""Deterministic SSRF and URL validation tests.

No real DNS lookups or network requests are made.
All DNS resolution is mocked via ``unittest.mock.patch``.
"""

import socket
from unittest.mock import patch

import pytest

from app.security import (
    SecurityError,
    validate_redirect_target,
    validate_request_url,
    validate_url,
)


def _addr4(ip: str) -> list:
    """Build a minimal IPv4 getaddrinfo result for the given IP."""
    return [(socket.AF_INET, socket.SOCK_STREAM, 0, "", (ip, 80))]


def _addr6(ip: str) -> list:
    """Build a minimal IPv6 getaddrinfo result for the given IP."""
    return [(socket.AF_INET6, socket.SOCK_STREAM, 0, "", (ip, 80, 0, 0))]


# ---------------------------------------------------------------------------
# validate_url — scheme and structure only (no DNS)
# ---------------------------------------------------------------------------


class TestValidateUrl:
    def test_empty_url_raises(self):
        with pytest.raises(SecurityError, match="empty"):
            validate_url("")

    def test_whitespace_only_raises(self):
        with pytest.raises(SecurityError, match="empty"):
            validate_url("   ")

    def test_http_accepted(self):
        assert validate_url("http://example.com") == "http://example.com"

    def test_https_accepted(self):
        assert validate_url("https://example.com") == "https://example.com"

    def test_scheme_normalized_to_lowercase(self):
        result = validate_url("HTTPS://Example.COM/Path")
        assert result.startswith("https://")
        assert "Example.COM" not in result

    def test_host_normalized_to_lowercase(self):
        result = validate_url("https://EXAMPLE.COM/")
        assert "example.com" in result

    def test_fragment_stripped(self):
        result = validate_url("https://example.com/page#section")
        assert "#section" not in result

    def test_file_scheme_blocked(self):
        with pytest.raises(SecurityError, match="Unsupported"):
            validate_url("file:///etc/passwd")

    def test_ftp_scheme_blocked(self):
        with pytest.raises(SecurityError, match="Unsupported"):
            validate_url("ftp://example.com/file.txt")

    def test_javascript_scheme_blocked(self):
        with pytest.raises(SecurityError, match="Unsupported"):
            validate_url("javascript://evil.com/xss")

    def test_data_scheme_blocked(self):
        with pytest.raises(SecurityError, match="Unsupported"):
            validate_url("data:text/html,<h1>hi</h1>")

    def test_gopher_scheme_blocked(self):
        with pytest.raises(SecurityError, match="Unsupported"):
            validate_url("gopher://evil.com/")

    def test_no_hostname_raises(self):
        with pytest.raises(SecurityError, match="hostname"):
            validate_url("https://")

    def test_path_and_query_preserved(self):
        result = validate_url("https://example.com/path?key=value")
        assert "/path" in result
        assert "key=value" in result


# ---------------------------------------------------------------------------
# validate_request_url — scheme + DNS + IP safety
# ---------------------------------------------------------------------------


class TestSsrfProtection:
    """All DNS lookups are mocked. No real network activity."""

    def test_loopback_127_blocked(self):
        with patch("app.security.socket.getaddrinfo", return_value=_addr4("127.0.0.1")):
            with pytest.raises(SecurityError, match="private or reserved"):
                validate_request_url("http://localhost/")

    def test_direct_127_ip_blocked(self):
        with patch("app.security.socket.getaddrinfo", return_value=_addr4("127.0.0.1")):
            with pytest.raises(SecurityError, match="private or reserved"):
                validate_request_url("http://127.0.0.1/")

    def test_private_10_blocked(self):
        with patch("app.security.socket.getaddrinfo", return_value=_addr4("10.0.0.1")):
            with pytest.raises(SecurityError, match="private or reserved"):
                validate_request_url("http://internal.corp/")

    def test_private_172_16_blocked(self):
        with patch("app.security.socket.getaddrinfo", return_value=_addr4("172.16.0.5")):
            with pytest.raises(SecurityError, match="private or reserved"):
                validate_request_url("http://internal.corp/")

    def test_private_172_31_blocked(self):
        with patch("app.security.socket.getaddrinfo", return_value=_addr4("172.31.255.255")):
            with pytest.raises(SecurityError, match="private or reserved"):
                validate_request_url("http://internal.corp/")

    def test_private_192_168_blocked(self):
        with patch("app.security.socket.getaddrinfo", return_value=_addr4("192.168.1.100")):
            with pytest.raises(SecurityError, match="private or reserved"):
                validate_request_url("http://router.local/")

    def test_link_local_aws_metadata_blocked(self):
        """169.254.169.254 is the AWS instance metadata endpoint — must always block."""
        with patch("app.security.socket.getaddrinfo", return_value=_addr4("169.254.169.254")):
            with pytest.raises(SecurityError, match="private or reserved"):
                validate_request_url("http://169.254.169.254/latest/meta-data/")

    def test_cgnat_blocked(self):
        with patch("app.security.socket.getaddrinfo", return_value=_addr4("100.64.0.1")):
            with pytest.raises(SecurityError, match="private or reserved"):
                validate_request_url("http://cgnat.example/")

    def test_zero_network_blocked(self):
        with patch("app.security.socket.getaddrinfo", return_value=_addr4("0.0.0.1")):
            with pytest.raises(SecurityError, match="private or reserved"):
                validate_request_url("http://zero.example/")

    def test_multicast_blocked(self):
        with patch("app.security.socket.getaddrinfo", return_value=_addr4("224.0.0.1")):
            with pytest.raises(SecurityError, match="private or reserved"):
                validate_request_url("http://mcast.example/")

    def test_ipv6_loopback_blocked(self):
        with patch("app.security.socket.getaddrinfo", return_value=_addr6("::1")):
            with pytest.raises(SecurityError, match="private or reserved"):
                validate_request_url("http://[::1]/")

    def test_ipv6_unique_local_blocked(self):
        with patch("app.security.socket.getaddrinfo", return_value=_addr6("fd00::1")):
            with pytest.raises(SecurityError, match="private or reserved"):
                validate_request_url("http://internal.v6.example/")

    def test_ipv4_mapped_ipv6_loopback_blocked(self):
        """::ffff:127.0.0.1 must be treated as 127.0.0.1 (private)."""
        with patch("app.security.socket.getaddrinfo", return_value=_addr6("::ffff:127.0.0.1")):
            with pytest.raises(SecurityError, match="private or reserved"):
                validate_request_url("http://mapped.example/")

    def test_ipv4_mapped_ipv6_private_blocked(self):
        with patch("app.security.socket.getaddrinfo", return_value=_addr6("::ffff:192.168.1.1")):
            with pytest.raises(SecurityError, match="private or reserved"):
                validate_request_url("http://mapped2.example/")

    def test_dns_failure_blocked(self):
        with patch(
            "app.security.socket.getaddrinfo",
            side_effect=socket.gaierror("Name or service not known"),
        ):
            with pytest.raises(SecurityError, match="DNS resolution failed"):
                validate_request_url("http://nonexistent.invalid/")

    def test_public_ip_allowed(self):
        with patch("app.security.socket.getaddrinfo", return_value=_addr4("93.184.216.34")):
            result = validate_request_url("https://example.com")
            assert "example.com" in result

    def test_public_google_dns_allowed(self):
        with patch("app.security.socket.getaddrinfo", return_value=_addr4("8.8.8.8")):
            result = validate_request_url("https://google.com")
            assert result == "https://google.com"

    def test_any_private_ip_among_multiple_blocks_request(self):
        """One private IP mixed with public IPs must block the whole request."""
        mixed = [
            (socket.AF_INET, socket.SOCK_STREAM, 0, "", ("93.184.216.34", 80)),
            (socket.AF_INET, socket.SOCK_STREAM, 0, "", ("10.0.0.1", 80)),  # private
        ]
        with patch("app.security.socket.getaddrinfo", return_value=mixed):
            with pytest.raises(SecurityError, match="private or reserved"):
                validate_request_url("https://dual-stack.example/")


# ---------------------------------------------------------------------------
# validate_redirect_target — must revalidate every redirect hop
# ---------------------------------------------------------------------------


class TestRedirectValidation:
    def test_redirect_to_private_ip_blocked(self):
        with patch("app.security.socket.getaddrinfo", return_value=_addr4("127.0.0.1")):
            with pytest.raises(SecurityError, match="private or reserved"):
                validate_redirect_target("http://127.0.0.1:8080/internal")

    def test_redirect_to_file_scheme_blocked(self):
        with pytest.raises(SecurityError, match="Unsupported"):
            validate_redirect_target("file:///etc/shadow")

    def test_redirect_to_public_url_allowed(self):
        with patch("app.security.socket.getaddrinfo", return_value=_addr4("93.184.216.34")):
            result = validate_redirect_target("https://example.com/page")
            assert "example.com" in result

    def test_redirect_to_link_local_blocked(self):
        with patch("app.security.socket.getaddrinfo", return_value=_addr4("169.254.169.254")):
            with pytest.raises(SecurityError, match="private or reserved"):
                validate_redirect_target("http://169.254.169.254/metadata")
