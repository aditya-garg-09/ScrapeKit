"""robots.txt policy tests — all HTTP is mocked via pytest-httpx."""

import time

import httpx
import pytest

from app.robots import RobotsChecker, RobotsError


@pytest.fixture
def checker():
    """Fresh RobotsChecker (empty cache) for each test."""
    return RobotsChecker()


# ---------------------------------------------------------------------------
# Allow / Disallow rules
# ---------------------------------------------------------------------------


class TestRobotsPolicy:
    def test_wildcard_empty_disallow_allows_all(self, httpx_mock, checker):
        httpx_mock.add_response(
            url="https://example.com/robots.txt",
            text="User-agent: *\nDisallow:\n",
        )
        assert checker.is_allowed("https://example.com/page") is True

    def test_disallow_path_blocks_matching_url(self, httpx_mock, checker):
        httpx_mock.add_response(
            url="https://example.com/robots.txt",
            text="User-agent: *\nDisallow: /private/\n",
        )
        assert checker.is_allowed("https://example.com/private/secret") is False

    def test_disallow_path_does_not_affect_other_paths(self, httpx_mock, checker):
        httpx_mock.add_response(
            url="https://example.com/robots.txt",
            text="User-agent: *\nDisallow: /private/\n",
        )
        assert checker.is_allowed("https://example.com/public/page") is True

    def test_disallow_root_blocks_everything(self, httpx_mock, checker):
        httpx_mock.add_response(
            url="https://example.com/robots.txt",
            text="User-agent: *\nDisallow: /\n",
        )
        assert checker.is_allowed("https://example.com/anything") is False

    def test_specific_agent_group_matched(self, httpx_mock, checker):
        """ScrapeKit-specific Disallow must block even when wildcard allows."""
        robots = (
            "User-agent: ScrapeKit\n"
            "Disallow: /blocked/\n"
            "\n"
            "User-agent: *\n"
            "Disallow:\n"
        )
        httpx_mock.add_response(url="https://example.com/robots.txt", text=robots)
        assert checker.is_allowed("https://example.com/blocked/page") is False

    def test_allow_before_disallow_overrides(self, httpx_mock, checker):
        """Allow rule for a more specific path must win over a broader Disallow."""
        robots = (
            "User-agent: *\n"
            "Allow: /api/public/\n"
            "Disallow: /api/\n"
        )
        httpx_mock.add_response(url="https://example.com/robots.txt", text=robots)
        assert checker.is_allowed("https://example.com/api/public/data") is True

    def test_disallow_still_blocks_other_api_paths(self, httpx_mock, checker):
        robots = (
            "User-agent: *\n"
            "Allow: /api/public/\n"
            "Disallow: /api/\n"
        )
        httpx_mock.add_response(url="https://example.com/robots.txt", text=robots)
        assert checker.is_allowed("https://example.com/api/private/data") is False


# ---------------------------------------------------------------------------
# robots.txt absence / fetch failures
# ---------------------------------------------------------------------------


class TestRobotsMissingOrUnavailable:
    def test_404_means_allow_all(self, httpx_mock, checker):
        """Standard semantics: no robots.txt → unrestricted crawling."""
        httpx_mock.add_response(url="https://example.com/robots.txt", status_code=404)
        assert checker.is_allowed("https://example.com/page") is True

    def test_non_200_non_404_raises_robots_error(self, httpx_mock, checker):
        httpx_mock.add_response(url="https://example.com/robots.txt", status_code=500)
        with pytest.raises(RobotsError, match="HTTP 500"):
            checker.is_allowed("https://example.com/page")

    def test_403_on_robots_raises_robots_error(self, httpx_mock, checker):
        httpx_mock.add_response(url="https://example.com/robots.txt", status_code=403)
        with pytest.raises(RobotsError, match="HTTP 403"):
            checker.is_allowed("https://example.com/page")

    def test_read_timeout_raises_robots_error(self, httpx_mock, checker):
        httpx_mock.add_exception(
            httpx.ReadTimeout("read timed out"),
            url="https://example.com/robots.txt",
        )
        with pytest.raises(RobotsError, match="timed out"):
            checker.is_allowed("https://example.com/page")

    def test_connect_error_raises_robots_error(self, httpx_mock, checker):
        httpx_mock.add_exception(
            httpx.ConnectError("connection refused"),
            url="https://example.com/robots.txt",
        )
        with pytest.raises(RobotsError, match="could not be retrieved"):
            checker.is_allowed("https://example.com/page")

    def test_network_error_raises_robots_error(self, httpx_mock, checker):
        httpx_mock.add_exception(
            httpx.NetworkError("network unreachable"),
            url="https://example.com/robots.txt",
        )
        with pytest.raises(RobotsError):
            checker.is_allowed("https://example.com/page")


# ---------------------------------------------------------------------------
# Caching behaviour
# ---------------------------------------------------------------------------


class TestRobotsCache:
    def test_cache_hit_prevents_second_fetch(self, httpx_mock, checker):
        """Second call to is_allowed must use the cache — only one HTTP request."""
        httpx_mock.add_response(
            url="https://example.com/robots.txt",
            text="User-agent: *\nDisallow:\n",
        )
        checker.is_allowed("https://example.com/page1")
        # If cache works: no second request is made, mock still has 0 consumed extras.
        # If cache is broken: a second request would raise because no more responses queued.
        checker.is_allowed("https://example.com/page2")

    def test_cache_expires_after_ttl(self, httpx_mock, checker):
        """After TTL expires the checker must re-fetch and pick up rule changes."""
        httpx_mock.add_response(
            url="https://example.com/robots.txt",
            text="User-agent: *\nDisallow:\n",
        )
        httpx_mock.add_response(
            url="https://example.com/robots.txt",
            text="User-agent: *\nDisallow: /\n",
        )
        checker.is_allowed("https://example.com/page")

        # Backdate the cache entry to simulate expiry
        origin = "https://example.com"
        parser, _ = checker._cache[origin]
        checker._cache[origin] = (parser, time.monotonic() - checker._cache_ttl - 1)

        result = checker.is_allowed("https://example.com/page")
        assert result is False  # second fetch returned Disallow: /

    def test_clear_cache_forces_refetch(self, httpx_mock, checker):
        httpx_mock.add_response(
            url="https://example.com/robots.txt",
            text="User-agent: *\nDisallow:\n",
        )
        httpx_mock.add_response(
            url="https://example.com/robots.txt",
            text="User-agent: *\nDisallow: /\n",
        )
        checker.is_allowed("https://example.com/page")
        checker.clear_cache()

        result = checker.is_allowed("https://example.com/page")
        assert result is False

    def test_different_origins_cached_independently(self, httpx_mock, checker):
        httpx_mock.add_response(
            url="https://site-a.com/robots.txt",
            text="User-agent: *\nDisallow: /\n",
        )
        httpx_mock.add_response(
            url="https://site-b.com/robots.txt",
            text="User-agent: *\nDisallow:\n",
        )
        assert checker.is_allowed("https://site-a.com/page") is False
        assert checker.is_allowed("https://site-b.com/page") is True
