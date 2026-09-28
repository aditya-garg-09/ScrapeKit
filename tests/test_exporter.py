"""Unit tests for the ScrapeKit exporter module."""

import json
from pathlib import Path

import pytest

from app.exporter import export_json, export_markdown, make_safe_filename, render_markdown
from app.models import ContentInfo, PageInfo, ScrapeResult, SourceInfo, StatsInfo


@pytest.fixture
def sample_result():
    return ScrapeResult(
        source=SourceInfo(
            requested_url="https://example.com/blog/my-post?ref=test",
            final_url="https://example.com/blog/my-post",
            status_code=200,
            content_type="text/html; charset=utf-8",
            robots_checked=True,
            robots_allowed=True,
            robots_url="https://example.com/robots.txt",
        ),
        page=PageInfo(
            title="My Post Title",
            description="A post about testing.",
            canonical_url="https://example.com/blog/my-post",
        ),
        content=ContentInfo(
            headings=[
                {"level": 1, "text": "My Post Title"},
                {"level": 2, "text": "Introduction"},
            ],
            links=[
                {"href": "https://example.com/about", "text": "About"},
                {"href": "https://example.com/home", "text": "Home"},
            ],
            text="This is the main article content.\n\nHere is paragraph two.",
        ),
        stats=StatsInfo(
            word_count=12,
            character_count=65,
            heading_count=2,
            link_count=2,
        ),
        scraped_at="2026-09-28T14:30:00Z",
    )


class TestFilenameGeneration:
    def test_basic_slug(self):
        slug = make_safe_filename("https://example.com/path/to/page")
        assert slug == "example-com-path-to-page"

    def test_special_characters_removed(self):
        slug = make_safe_filename("https://example.com/search?q=hello&filter=1#tag")
        assert "?" not in slug
        assert "&" not in slug
        assert "#" not in slug
        assert slug.startswith("example-com-search")

    def test_length_capped(self):
        long_url = "https://example.com/" + ("subpath/" * 20)
        slug = make_safe_filename(long_url, max_length=50)
        assert len(slug) <= 50

    def test_empty_or_root_url(self):
        slug = make_safe_filename("https://example.com/")
        assert slug == "example-com"


class TestExportJson:
    def test_export_json_file(self, tmp_path, sample_result):
        json_file = export_json(sample_result, tmp_path)
        assert json_file.exists()
        assert json_file.suffix == ".json"

        with open(json_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        assert data["source"]["requested_url"] == "https://example.com/blog/my-post?ref=test"
        assert data["page"]["title"] == "My Post Title"
        assert len(data["content"]["headings"]) == 2
        assert data["stats"]["word_count"] == 12


class TestExportMarkdown:
    def test_render_markdown_content(self, sample_result):
        md = render_markdown(sample_result)
        assert "# My Post Title" in md
        assert "**Requested URL**: https://example.com/blog/my-post?ref=test" in md
        assert "## Headings" in md
        assert "# My Post Title" in md
        assert "## Introduction" in md
        assert "## Links" in md
        assert "- [About](https://example.com/about)" in md
        assert "## Content" in md
        assert "This is the main article content." in md

    def test_export_markdown_file(self, tmp_path, sample_result):
        md_file = export_markdown(sample_result, tmp_path)
        assert md_file.exists()
        assert md_file.suffix == ".md"

        content = md_file.read_text(encoding="utf-8")
        assert "# My Post Title" in content
