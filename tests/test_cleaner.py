"""Unit tests for the HTML cleaner module."""

from pathlib import Path

import pytest
from bs4 import BeautifulSoup

from app.cleaner import (
    deduplicate_links,
    extract_clean_text,
    normalize_whitespace,
    remove_noise_elements,
)
from app.parser import parse_html

FIXTURES_DIR = Path(__file__).parent / "fixtures"


class TestNoiseRemoval:
    def test_removes_script_and_style(self):
        html = """
        <html>
        <head>
            <style>body { color: red; }</style>
        </head>
        <body>
            <script>console.log('secret');</script>
            <p>Real content</p>
        </body>
        </html>
        """
        soup = BeautifulSoup(html, "html.parser")
        remove_noise_elements(soup)

        assert soup.find("script") is None
        assert soup.find("style") is None
        assert "Real content" in soup.get_text()
        assert "secret" not in soup.get_text()

    def test_removes_noscript_and_svg_and_canvas(self):
        html = """
        <div>
            <noscript>Please enable JS</noscript>
            <svg><circle cx="50" cy="50" r="40"/></svg>
            <canvas id="myCanvas"></canvas>
            <iframe src="https://ads.example.com"></iframe>
            <template><p>Template content</p></template>
            <p>Legitimate text</p>
        </div>
        """
        soup = BeautifulSoup(html, "html.parser")
        remove_noise_elements(soup)

        text = soup.get_text()
        assert "Please enable JS" not in text
        assert "Template content" not in text
        assert "Legitimate text" in text

    def test_removes_html_comments(self):
        html = "<div><!-- Secret internal note -->Visible content</div>"
        soup = BeautifulSoup(html, "html.parser")
        remove_noise_elements(soup)

        assert "Secret internal note" not in soup.get_text()
        assert "Visible content" in soup.get_text()


class TestWhitespaceNormalization:
    def test_collapses_horizontal_whitespace(self):
        raw = "Word1     Word2\t\tWord3\xa0\xa0Word4"
        normalized = normalize_whitespace(raw)
        assert normalized == "Word1 Word2 Word3 Word4"

    def test_collapses_excessive_blank_lines(self):
        raw = "Paragraph 1\n\n\n\n\nParagraph 2\n\n\n\nParagraph 3"
        normalized = normalize_whitespace(raw)
        assert normalized == "Paragraph 1\n\nParagraph 2\n\nParagraph 3"

    def test_handles_empty_or_whitespace_input(self):
        assert normalize_whitespace("") == ""
        assert normalize_whitespace("   \n\t\n   ") == ""

    def test_strips_per_line_edges(self):
        raw = "  Line 1  \n   Line 2   "
        normalized = normalize_whitespace(raw)
        assert normalized == "Line 1\nLine 2"


class TestLinkDeduplication:
    def test_deduplicates_by_href_preserving_order(self):
        links = [
            {"href": "https://example.com/a", "text": "A1"},
            {"href": "https://example.com/b", "text": "B"},
            {"href": "https://example.com/a", "text": "A2"},
        ]
        deduped = deduplicate_links(links)
        assert len(deduped) == 2
        assert deduped[0] == {"href": "https://example.com/a", "text": "A1"}
        assert deduped[1] == {"href": "https://example.com/b", "text": "B"}

    def test_upgrades_empty_text_with_later_text(self):
        links = [
            {"href": "https://example.com/about", "text": ""},
            {"href": "https://example.com/about", "text": "About Us"},
        ]
        deduped = deduplicate_links(links)
        assert len(deduped) == 1
        assert deduped[0]["text"] == "About Us"

    def test_skips_empty_hrefs(self):
        links = [
            {"href": "", "text": "Empty"},
            {"href": "https://example.com", "text": "Home"},
        ]
        deduped = deduplicate_links(links)
        assert len(deduped) == 1
        assert deduped[0]["href"] == "https://example.com"


class TestCleanerIntegration:
    def test_extract_clean_text_end_to_end(self):
        html = """
        <!DOCTYPE html>
        <html>
        <head>
            <style>body { font-size: 14px; }</style>
        </head>
        <body>
            <!-- banner -->
            <h1>Article Title</h1>
            <script>var x = 1;</script>
            <p>First paragraph with some text.</p>


            <p>Second paragraph after big gap.</p>
            <svg><path d="M0 0"/></svg>
        </body>
        </html>
        """
        soup = BeautifulSoup(html, "html.parser")
        clean = extract_clean_text(soup)

        assert "Article Title" in clean
        assert "First paragraph with some text." in clean
        assert "Second paragraph after big gap." in clean
        assert "font-size" not in clean
        assert "var x = 1" not in clean
        assert "banner" not in clean
        # Paragraph break preserved
        assert "\n\n" in clean

    def test_duplicate_links_fixture_deduped_in_parser(self):
        fixture_path = FIXTURES_DIR / "duplicate_links.html"
        html = fixture_path.read_text(encoding="utf-8")

        result = parse_html(html, base_url="https://example.com")
        # In fixture: /same-page x3 and /unique x1 -> should become 2 unique links
        assert len(result.links) == 2
        hrefs = [l["href"] for l in result.links]
        assert hrefs == ["https://example.com/same-page", "https://example.com/unique"]
