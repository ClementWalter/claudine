#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "markitdown>=0.1.0",
#   "markdown>=3.5",
#   "Pillow>=10.0",
#   "beautifulsoup4>=4.12",
#   "pytest>=8.0",
# ]
# ///
"""Unit tests for the html_to_share skill script."""

import base64
import io
import os
import sys
import tempfile
from pathlib import Path

import pytest
from PIL import Image

# -- Import the module under test
sys.path.insert(0, str(Path(__file__).parent))
from html_to_share import (
    clean_markdown,
    find_files_dir,
    image_to_base64,
    inline_images,
    markdown_to_html,
    resolve_image_path,
)


# -- Fixtures


@pytest.fixture
def tmp_dir():
    """Create a temporary directory for test files."""
    with tempfile.TemporaryDirectory() as d:
        yield Path(d)


@pytest.fixture
def sample_html_with_files(tmp_dir):
    """Create a sample browser-saved HTML with companion _files dir."""
    html_content = "<html><body><h1>Test Article</h1><p>Hello world.</p></body></html>"
    html_path = tmp_dir / "Test Article.html"
    html_path.write_text(html_content)

    files_dir = tmp_dir / "Test Article_files"
    files_dir.mkdir()

    # Create a small test image
    img = Image.new("RGB", (200, 100), color="red")
    img_path = files_dir / "photo.jpg"
    img.save(str(img_path), "JPEG")

    return html_path, files_dir, img_path


@pytest.fixture
def large_test_image(tmp_dir):
    """Create a large test image (wider than MAX_IMAGE_WIDTH)."""
    img = Image.new("RGB", (2000, 1000), color="blue")
    img_path = tmp_dir / "large.png"
    img.save(str(img_path), "PNG")
    return img_path


@pytest.fixture
def rgba_test_image(tmp_dir):
    """Create a PNG with alpha channel."""
    img = Image.new("RGBA", (100, 100), color=(255, 0, 0, 128))
    img_path = tmp_dir / "alpha.png"
    img.save(str(img_path), "PNG")
    return img_path


# -- Tests for find_files_dir


class TestFindFilesDir:
    def test_finds_direct_match(self, sample_html_with_files):
        html_path, files_dir, _ = sample_html_with_files
        assert find_files_dir(html_path) == files_dir

    def test_returns_none_when_no_files_dir(self, tmp_dir):
        html_path = tmp_dir / "NoFiles.html"
        html_path.write_text("<html></html>")
        assert find_files_dir(html_path) is None

    def test_fuzzy_match_ignores_punctuation(self, tmp_dir):
        """Fuzzy match should find dir even with different quote chars."""
        html_path = tmp_dir / "Article 'test'.html"
        html_path.write_text("<html></html>")
        # Create dir with same alphanumeric chars
        files_dir = tmp_dir / "Article 'test'_files"
        files_dir.mkdir()
        result = find_files_dir(html_path)
        assert result is not None


# -- Tests for resolve_image_path


class TestResolveImagePath:
    def test_resolves_relative_path(self, sample_html_with_files):
        _, files_dir, img_path = sample_html_with_files
        result = resolve_image_path(f"./{files_dir.name}/photo.jpg", files_dir)
        assert result == img_path

    def test_resolves_filename_only(self, sample_html_with_files):
        _, files_dir, img_path = sample_html_with_files
        result = resolve_image_path("photo.jpg", files_dir)
        assert result == img_path

    def test_returns_none_for_missing_file(self, sample_html_with_files):
        _, files_dir, _ = sample_html_with_files
        assert resolve_image_path("nonexistent.jpg", files_dir) is None

    def test_returns_none_when_no_files_dir(self):
        assert resolve_image_path("photo.jpg", None) is None


# -- Tests for image_to_base64


class TestImageToBase64:
    def test_produces_data_uri(self, sample_html_with_files):
        _, _, img_path = sample_html_with_files
        result = image_to_base64(img_path)
        assert result is not None
        assert result.startswith("data:image/jpeg;base64,")

    def test_resizes_large_image(self, large_test_image):
        result = image_to_base64(large_test_image)
        assert result is not None
        # Decode and check the width
        b64_data = result.split(",", 1)[1]
        img_bytes = base64.b64decode(b64_data)
        img = Image.open(io.BytesIO(img_bytes))
        assert img.width <= 1000

    def test_converts_rgba_to_rgb(self, rgba_test_image):
        result = image_to_base64(rgba_test_image)
        assert result is not None
        assert result.startswith("data:image/jpeg;base64,")

    def test_returns_none_for_invalid_file(self, tmp_dir):
        bad_path = tmp_dir / "not_an_image.txt"
        bad_path.write_text("not an image")
        assert image_to_base64(bad_path) is None


# -- Tests for clean_markdown


class TestCleanMarkdown:
    def test_strips_content_before_first_heading(self):
        md = "nav stuff\nmore nav\n# Article Title\nContent here"
        result = clean_markdown(md)
        assert result.startswith("# Article Title")

    def test_removes_tracking_pixels(self):
        md = "# Title\n\n![](https://example.com/pixel.gif)\n\nReal content."
        result = clean_markdown(md)
        assert "pixel" not in result
        assert "Real content" in result

    def test_removes_play_labels(self):
        md = "# Title\n\nplay\n\nActual text."
        result = clean_markdown(md)
        assert "play" not in result.lower().split("\n")
        assert "Actual text" in result

    def test_removes_share_buttons_list_items(self):
        md = (
            "# Title\n\n"
            "* [Share on X, formerly known as Twitter (opens a new window)](https://x.com)\n"
            "* [Share on Facebook (opens a new window)](https://fb.com)\n"
            "\nReal content."
        )
        result = clean_markdown(md)
        assert "Twitter" not in result
        assert "Facebook" not in result
        assert "Real content" in result

    def test_removes_sharing_link_text(self):
        md = "# Title\n\nSharing link\nLink copied to clipboard.\n\nContent."
        result = clean_markdown(md)
        assert "Sharing link" not in result
        assert "Link copied" not in result
        assert "Content" in result

    def test_removes_ft_copyright(self):
        md = "# Title\n\nContent.\n\n[Copyright](url) The Financial Times Limited 2026."
        result = clean_markdown(md)
        assert "Financial Times" not in result
        assert "Content" in result

    def test_italicizes_copyright_lines(self):
        md = "# Title\n\n© Reuters/Photo Agency"
        result = clean_markdown(md)
        assert "*© Reuters/Photo Agency*" in result

    def test_removes_scrim_images(self):
        md = "# Title\n\n![overlay](path/to/image-scrim.png)\n\nContent."
        result = clean_markdown(md)
        assert "scrim" not in result
        assert "Content" in result

    def test_removes_browser_doesnt_support(self):
        md = "# Title\n\nYour browser doesn't support HTML5 video.\n\nContent."
        result = clean_markdown(md)
        assert "browser" not in result.lower()
        assert "Content" in result


# -- Tests for inline_images


class TestInlineImages:
    def test_inlines_local_image(self, sample_html_with_files):
        _, files_dir, _ = sample_html_with_files
        md = f"# Title\n\n![Photo](./{files_dir.name}/photo.jpg)"
        result, count = inline_images(md, files_dir)
        assert count == 1
        assert "data:image/jpeg;base64," in result

    def test_skips_remote_images(self, sample_html_with_files):
        _, files_dir, _ = sample_html_with_files
        md = "# Title\n\n![Remote](https://example.com/photo.jpg)"
        result, count = inline_images(md, files_dir)
        assert count == 0
        assert "https://example.com/photo.jpg" in result

    def test_skips_already_inlined(self, sample_html_with_files):
        _, files_dir, _ = sample_html_with_files
        md = "# Title\n\n![Inline](data:image/jpeg;base64,abc123)"
        result, count = inline_images(md, files_dir)
        assert count == 0

    def test_returns_zero_when_no_files_dir(self):
        md = "# Title\n\n![Photo](photo.jpg)"
        result, count = inline_images(md, None)
        assert count == 0


# -- Tests for markdown_to_html


class TestMarkdownToHtml:
    def test_produces_valid_html_structure(self):
        html = markdown_to_html("# Hello\n\nWorld")
        assert "<!DOCTYPE html>" in html
        assert "<style>" in html
        assert "Georgia" in html
        assert "<h1>" in html
        assert "World" in html

    def test_includes_viewport_meta(self):
        html = markdown_to_html("# Test")
        assert "viewport" in html


# -- Integration test with the full pipeline (simple page)


class TestIntegrationSimplePage:
    def test_end_to_end_with_simple_html(self, tmp_dir):
        """Full pipeline test: HTML with image -> self-contained shareable file."""
        # Create a simple HTML page
        html_content = """<html>
<head><title>Simple Test</title></head>
<body>
<h1>My Simple Article</h1>
<p>This is a paragraph of text.</p>
<img src="./Simple Test_files/photo.jpg" alt="A photo">
<p>More content here.</p>
</body>
</html>"""
        html_path = tmp_dir / "Simple Test.html"
        html_path.write_text(html_content)

        # Create companion directory with image
        files_dir = tmp_dir / "Simple Test_files"
        files_dir.mkdir()
        img = Image.new("RGB", (500, 300), color="green")
        img.save(str(files_dir / "photo.jpg"), "JPEG")

        # Run the full pipeline via subprocess
        import subprocess

        result = subprocess.run(
            [
                sys.executable,
                str(Path(__file__).parent / "html_to_share.py"),
                str(html_path),
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0

        # Verify output file
        output_path = tmp_dir / "Simple Test-share.html"
        assert output_path.exists()

        content = output_path.read_text()
        assert "data:image/jpeg;base64," in content
        assert "_files" not in content
        assert "My Simple Article" in content


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
