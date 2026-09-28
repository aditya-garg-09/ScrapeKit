"""Unit tests for the HTML parser module."""

from pathlib import Path

import pytest

from app.parser import (
    ParsedContent,
    compute_stats,
    extract_canonical,
    extract_description,
    extract_headings,
    extract_links,
    extract_meta_tags,
    extract_title,
    parse_html,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def read_fixture(name: str) -> str:
    return (FIXTURES_DIR / name).read_text(encoding="utf-8")


class TestBasicParsing:
    def test_parse_basic_page(self):
        html = read_fixture("basic.html")
        result = parse_html(html, base_url="https://example.com/dir/page")

        assert result.title == "Basic Test Page"
        assert result.description == "A simple test page for ScrapeKit parser."
        assert result.canonical_url == "https://example.com/canonical-page"
        assert len(result.headings) == 3
        assert result.headings[0] == {"level": 1, "text": "Main Title"}
        assert result.headings[1] == {"level": 2, "text": "Section 1"}
        assert result.headings[2] == {"level": 3, "text": "Subsection 1.1"}

        assert len(result.links) == 1
        assert result.links[0] == {"href": "https://example.com/about", "text": "About Us"}

        assert result.meta_tags.get("author") == "ScrapeKit Team"
        assert result.meta_tags.get("description") == "A simple test page for ScrapeKit parser."

        assert result.stats["heading_count"] == 3
        assert result.stats["link_count"] == 1
        assert result.stats["word_count"] > 10
        assert result.stats["character_count"] > 50

    def test_parse_empty_html(self):
        result = parse_html("")
        assert result.title == ""
        assert result.description == ""
        assert result.canonical_url is None
        assert result.headings == []
        assert result.links == []
        assert result.meta_tags == {}
        assert result.text == ""

    def test_parse_whitespace_only_html(self):
        result = parse_html("   \n\t  ")
        assert result.title == ""
        assert result.headings == []


class TestLinkAbsolutization:
    def test_relative_links_resolution(self):
        html = read_fixture("relative_links.html")
        result = parse_html(html, base_url="https://example.com/docs/intro")

        hrefs = [link["href"] for link in result.links]
        assert "https://example.com/about" in hrefs
        assert "https://example.com/docs/contact.html" in hrefs
        assert "https://example.com/pricing" in hrefs
        assert "https://cdn.example.com/asset" in hrefs
        assert "https://external.com/docs" in hrefs

    def test_javascript_links_filtered_out(self):
        html = '<a href="javascript:void(0)">Click</a><a href="/safe">Safe</a>'
        result = parse_html(html, base_url="https://example.com")

        assert len(result.links) == 1
        assert result.links[0]["href"] == "https://example.com/safe"


class TestMissingElementsAndResilience:
    def test_no_meta_fixture(self):
        html = read_fixture("no_meta.html")
        result = parse_html(html, base_url="https://example.com")

        assert result.title == ""
        assert result.description == ""
        assert result.canonical_url is None
        assert result.headings == []
        assert result.links == []
        assert "Bare minimum page." in result.text

    def test_malformed_html_fixture(self):
        html = read_fixture("malformed.html")
        result = parse_html(html, base_url="https://example.com")

        assert "Unclosed tags test" in result.title
        assert len(result.headings) >= 1
        assert "Heading without close" in result.headings[0]["text"]
        assert len(result.links) >= 1
        assert result.links[0]["href"] == "https://example.com/unquoted-attr"

    def test_fallback_og_meta(self):
        html = """
        <html>
        <head>
            <meta property="og:title" content="OpenGraph Title">
            <meta property="og:description" content="OpenGraph Description">
        </head>
        <body><p>Body</p></body>
        </html>
        """
        result = parse_html(html)
        assert result.title == "OpenGraph Title"
        assert result.description == "OpenGraph Description"


class TestHeadingsAndStats:
    def test_heading_levels(self):
        html = """
        <h1>H1</h1>
        <h2>H2</h2>
        <h3>H3</h3>
        <h4>H4</h4>
        <h5>H5</h5>
        <h6>H6</h6>
        """
        result = parse_html(html)
        levels = [h["level"] for h in result.headings]
        assert levels == [1, 2, 3, 4, 5, 6]

    def test_compute_stats_calculation(self):
        text = "One two three four five"
        headings = [{"level": 1, "text": "H1"}]
        links = [{"href": "https://a.com", "text": "A"}]
        stats = compute_stats(text, headings, links)

        assert stats["word_count"] == 5
        assert stats["character_count"] == len(text)
        assert stats["heading_count"] == 1
        assert stats["link_count"] == 1
