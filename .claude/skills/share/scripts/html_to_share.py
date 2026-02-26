#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "markitdown>=0.1.0",
#   "markdown>=3.5",
#   "Pillow>=10.0",
#   "beautifulsoup4>=4.12",
#   "requests>=2.31",
# ]
# ///
"""Convert a browser-saved HTML file or a URL into a self-contained, shareable HTML page.

Accepts either:
- A local "Save As > Web Page, Complete" HTML file with its companion _files/ dir
- A URL (http/https) — uses `surf` CLI to navigate with your browser session,
  captures the rendered HTML, downloads images, and produces the output

Outputs a single lightweight HTML with inlined base64 images, clean typography,
and embedded CSS.
"""

import base64
import hashlib
import io
import json
import logging
import re
import shutil
import subprocess
import sys
import time
import unicodedata
from pathlib import Path
from urllib.parse import urljoin, urlparse

import markdown
import requests
from markitdown import MarkItDown
from PIL import Image

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

# -- Maximum image width for inlined images (pixels)
MAX_IMAGE_WIDTH = 1000
# -- JPEG compression quality for inlined images
JPEG_QUALITY = 72
# -- Cache directory for URL-fetched pages
CACHE_DIR = Path.home() / ".cache" / "share-skill"
# -- Default output directory for URL-mode
OUTPUT_DIR = Path.home() / "Desktop"

# -- CSS for the output HTML: Georgia serif, centered, readable
EMBEDDED_CSS = """\
* { margin: 0; padding: 0; box-sizing: border-box; }
body {
    font-family: Georgia, 'Times New Roman', serif;
    max-width: 720px;
    margin: 0 auto;
    padding: 2rem 1.5rem;
    line-height: 1.7;
    color: #1a1a1a;
    background: #fff;
}
h1 { font-size: 2.2rem; margin: 1rem 0 0.5rem; line-height: 1.2; }
h2 { font-size: 1.6rem; margin: 2rem 0 0.8rem; line-height: 1.3; }
h3 { font-size: 1.3rem; margin: 1.5rem 0 0.6rem; line-height: 1.3; }
p { margin: 0.8rem 0; }
img {
    max-width: 100%;
    height: auto;
    display: block;
    margin: 1.5rem 0;
    border-radius: 4px;
}
em { color: #555; }
blockquote {
    border-left: 3px solid #ccc;
    padding-left: 1rem;
    margin: 1rem 0;
    color: #555;
    font-style: italic;
}
hr { border: none; border-top: 1px solid #ddd; margin: 2rem 0; }
a { color: #0066cc; text-decoration: none; }
a:hover { text-decoration: underline; }
figcaption, .credit { font-size: 0.85rem; color: #777; margin-top: -1rem; margin-bottom: 1rem; }
"""


def find_files_dir(html_path: Path) -> Path | None:
    """Auto-detect the companion _files/ directory for a saved HTML page.

    Browsers create a directory named `<stem>_files` next to the HTML file.
    The stem may use smart quotes (Unicode) or plain ASCII quotes, so we try
    multiple normalization strategies.
    """
    parent = html_path.parent
    stem = html_path.stem

    # -- Direct match: same stem + _files
    candidate = parent / f"{stem}_files"
    if candidate.is_dir():
        return candidate

    # -- Try NFC/NFD normalization (macOS uses NFD for filesystem paths)
    for form in ("NFC", "NFD"):
        normalized = unicodedata.normalize(form, f"{stem}_files")
        candidate = parent / normalized
        if candidate.is_dir():
            return candidate

    # -- Fallback: scan parent directory for any dir ending in _files that
    #    shares a common prefix with the stem
    stem_lower = stem.lower()
    for entry in parent.iterdir():
        if entry.is_dir() and entry.name.endswith("_files"):
            entry_stem = entry.name[:-6].lower()
            # Allow fuzzy match: compare alphanumeric characters only
            clean_stem = re.sub(r"[^a-z0-9]", "", stem_lower)
            clean_entry = re.sub(r"[^a-z0-9]", "", entry_stem)
            if clean_stem == clean_entry:
                return entry

    return None


def resolve_image_path(img_ref: str, files_dir: Path | None) -> Path | None:
    """Resolve a markdown image reference to a local file path.

    Handles both relative paths (from _files/) and references that include
    the _files directory name.
    """
    if files_dir is None:
        return None

    # -- Strip leading ./ if present
    cleaned = img_ref.lstrip("./")

    # -- Try direct resolution relative to the _files dir's parent
    candidate = files_dir.parent / cleaned
    if candidate.is_file():
        return candidate

    # -- Try as a filename within _files/
    candidate = files_dir / Path(cleaned).name
    if candidate.is_file():
        return candidate

    # -- Try URL-decoded version (spaces encoded as %20, etc.)
    try:
        from urllib.parse import unquote
        decoded = unquote(cleaned)
        candidate = files_dir.parent / decoded
        if candidate.is_file():
            return candidate
        candidate = files_dir / Path(decoded).name
        if candidate.is_file():
            return candidate
    except Exception:
        pass

    return None


def image_to_base64(img_path: Path) -> str | None:
    """Resize, compress, and encode an image as a JPEG base64 data URI."""
    try:
        with Image.open(img_path) as img:
            # -- Convert to RGB (handles PNG with alpha, WEBP, etc.)
            if img.mode in ("RGBA", "P", "LA"):
                img = img.convert("RGB")
            elif img.mode != "RGB":
                img = img.convert("RGB")

            # -- Resize if wider than MAX_IMAGE_WIDTH
            if img.width > MAX_IMAGE_WIDTH:
                ratio = MAX_IMAGE_WIDTH / img.width
                new_height = int(img.height * ratio)
                img = img.resize((MAX_IMAGE_WIDTH, new_height), Image.LANCZOS)

            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=JPEG_QUALITY, optimize=True)
            b64 = base64.b64encode(buf.getvalue()).decode("ascii")
            return f"data:image/jpeg;base64,{b64}"
    except Exception as exc:
        logger.warning("Failed to process image %s: %s", img_path, exc)
        return None


def clean_markdown(md_text: str) -> str:
    """Clean markdown output from MarkItDown by removing web artifacts."""
    lines = md_text.split("\n")

    # -- Strip everything before the first # heading (navigation, menus, etc.)
    first_heading_idx = None
    for i, line in enumerate(lines):
        if re.match(r"^#{1,2}\s+\S", line):
            first_heading_idx = i
            break
    if first_heading_idx is not None and first_heading_idx > 0:
        lines = lines[first_heading_idx:]

    text = "\n".join(lines)

    # -- Remove tracking pixels: zero-size images, 1x1 images, spoor/analytics
    text = re.sub(
        r"!\[[^\]]*\]\([^)]*(?:pixel|track|beacon|1x1|px\.gif|spoor|analytics)[^)]*\)",
        "",
        text,
        flags=re.IGNORECASE,
    )

    # -- Remove "play" labels (video overlay artifacts)
    text = re.sub(r"^play\s*$", "", text, flags=re.MULTILINE | re.IGNORECASE)

    # -- Remove "Your browser doesn't support" text (including surrounding links)
    text = re.sub(
        r"\[?\s*your browser[^]]*(?:support|video|audio)[^\]]*\.?\s*\]?\([^)]*\)?",
        "",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(
        r".*your browser[^.\n]*(?:support|video|audio)[^.\n]*\.?\s*",
        "",
        text,
        flags=re.IGNORECASE,
    )

    # -- Remove share button list items: linked or plain text
    text = re.sub(
        r"^\*\s*\[?Share[^\n]*(?:Twitter|Facebook|LinkedIn|Whatsapp|X,|"
        r"opens a new window)[^\n]*$",
        "",
        text,
        flags=re.MULTILINE | re.IGNORECASE,
    )

    # -- Remove bare "* Share" list items (share buttons with link text stripped)
    text = re.sub(r"^\*\s+Share\s*$", "", text, flags=re.MULTILINE | re.IGNORECASE)

    # -- Remove all "Share ... on <platform>" inline patterns
    text = re.sub(
        r"\[?Share[^\]\n]*(?:Twitter|Facebook|LinkedIn|Whatsapp|X,)[^\]\n]*\]?"
        r"(?:\([^)]*\))?",
        "",
        text,
        flags=re.IGNORECASE,
    )

    # -- Remove standalone share/social lines and UI text artifacts
    text = re.sub(
        r"(?:^|\n)\s*(?:Share|Tweet|Email|Copy link|Save|Reuse|Print|"
        r"Sharing link|Link copied to clipboard\.?|current progress \d+%)\s*(?:\n|$)",
        "\n",
        text,
        flags=re.IGNORECASE,
    )
    # -- Also remove these when they appear mid-line
    text = re.sub(r"Sharing link", "", text, flags=re.IGNORECASE)
    text = re.sub(r"Link copied to clipboard\.?", "", text, flags=re.IGNORECASE)
    text = re.sub(r"current progress \d+%", "", text, flags=re.IGNORECASE)

    # -- Remove common footer/nav sections
    footer_patterns = [
        r"\n#{1,3}\s*(?:Latest on|Related articles?|More (?:from|on)|"
        r"Support|Legal\s*(?:&|and)\s*Privacy|Follow us|Newsletter|"
        r"Sign up|Subscribe|Comments|Promoted content|"
        r"Explore the series|More in this series|Tools|"
        r"Community\s*(?:&|and)\s*Events|More from the FT|Services).*",
    ]
    for pattern in footer_patterns:
        text = re.sub(pattern, "", text, flags=re.IGNORECASE | re.DOTALL)

    # -- Remove FT copyright footer and similar publication footers
    text = re.sub(
        r"(?:Markets data|© THE FINANCIAL TIMES|FT and .Financial Times.|"
        r"Copyright The Financial Times).*",
        "",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )

    # -- Deduplicate responsive image sets: when multiple sizes (S, M, L, XL)
    #    of the same image appear, keep only the largest
    seen_image_bases = {}
    img_pattern = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")

    def _image_base_key(path_str: str) -> str:
        """Extract the base name without size suffix (S, M, L, XL)."""
        name = Path(path_str).stem
        # Remove size suffixes like -S, -M, -L, -XL and hash suffixes
        cleaned = re.sub(r"[-.](?:S|M|L|XL)(?:[-_.]|$)", ".", name, flags=re.IGNORECASE)
        cleaned = re.sub(r"\.[A-Za-z0-9_-]{6,}$", "", cleaned)
        return cleaned.lower()

    def _size_rank(path_str: str) -> int:
        """Rank image by size suffix: XL=4, L=3, M=2, S=1, unknown=0."""
        name = Path(path_str).stem.upper()
        if "-XL" in name or ".XL" in name or "_XL" in name:
            return 4
        if "-L." in name or "-L-" in name or ".L." in name or "_L." in name:
            return 3
        if "-M." in name or "-M-" in name or ".M." in name or "_M." in name:
            return 2
        if "-S." in name or "-S-" in name or ".S." in name or "_S." in name:
            return 1
        return 0

    # -- First pass: identify the best version of each responsive image
    for match in img_pattern.finditer(text):
        img_src = match.group(2)
        base_key = _image_base_key(img_src)
        rank = _size_rank(img_src)
        if base_key not in seen_image_bases or rank > seen_image_bases[base_key][1]:
            seen_image_bases[base_key] = (img_src, rank)

    # -- Second pass: remove duplicate smaller versions
    def _replace_image(match: re.Match) -> str:
        alt = match.group(1)
        src = match.group(2)
        base_key = _image_base_key(src)
        if base_key in seen_image_bases and seen_image_bases[base_key][0] != src:
            # This is a smaller duplicate — remove it
            return ""
        return match.group(0)

    text = img_pattern.sub(_replace_image, text)

    # -- Remove scrim overlay images (semi-transparent overlays)
    text = re.sub(r"!\[[^\]]*\]\([^)]*scrim[^)]*\)", "", text, flags=re.IGNORECASE)

    # -- Italicize photo credit lines (lines containing ©)
    text = re.sub(
        r"^([^*\n]*©[^\n]*)$",
        r"*\1*",
        text,
        flags=re.MULTILINE,
    )

    # -- Consolidate repeated short-line blocks (infographic labels):
    #    detect 3+ consecutive lines of ≤30 chars and collapse duplicates
    result_lines = []
    prev_short_block: list[str] = []
    seen_short_blocks: set[str] = set()
    for line in text.split("\n"):
        stripped = line.strip()
        if 0 < len(stripped) <= 30 and not stripped.startswith("#") and not stripped.startswith("!"):
            prev_short_block.append(stripped)
        else:
            if len(prev_short_block) >= 3:
                block_key = "|".join(prev_short_block)
                if block_key not in seen_short_blocks:
                    seen_short_blocks.add(block_key)
                    result_lines.extend(prev_short_block)
            else:
                result_lines.extend(prev_short_block)
            prev_short_block = []
            result_lines.append(line)
    # -- Flush remaining short block
    if len(prev_short_block) >= 3:
        block_key = "|".join(prev_short_block)
        if block_key not in seen_short_blocks:
            result_lines.extend(prev_short_block)
    else:
        result_lines.extend(prev_short_block)

    text = "\n".join(result_lines)

    # -- Remove orphaned empty list items left after share button removal
    text = re.sub(r"^\*\s*$", "", text, flags=re.MULTILINE)

    # -- Remove standalone "Share" words left after link text was stripped
    text = re.sub(r"^\s*Share\s*$", "", text, flags=re.MULTILINE | re.IGNORECASE)

    # -- Final pass: remove any remaining copyright/legal footers
    #    Handles both plain text and markdown link form: [Copyright](url)
    text = re.sub(
        r"(?:\[Copyright\]\([^)]*\)\s*)?(?:Copyright\s+)?The Financial Times.*",
        "",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )

    # -- Collapse excessive blank lines (3+ → 2)
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()


def inline_images(md_text: str, files_dir: Path | None) -> tuple[str, int]:
    """Replace local image references with base64 data URIs.

    Returns the modified markdown and the count of inlined images.
    """
    if files_dir is None:
        return md_text, 0

    count = 0
    img_pattern = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")

    def _replace(match: re.Match) -> str:
        nonlocal count
        alt = match.group(1)
        src = match.group(2)

        # -- Skip already-inlined images and remote URLs
        if src.startswith("data:") or src.startswith("http://") or src.startswith("https://"):
            return match.group(0)

        img_path = resolve_image_path(src, files_dir)
        if img_path is None:
            logger.debug("Image not found locally: %s", src)
            return match.group(0)

        data_uri = image_to_base64(img_path)
        if data_uri is None:
            return match.group(0)

        count += 1
        return f"![{alt}]({data_uri})"

    result = img_pattern.sub(_replace, md_text)
    return result, count


def markdown_to_html(md_text: str) -> str:
    """Convert cleaned markdown to styled HTML with embedded CSS."""
    # -- Use the markdown library with common extensions
    html_body = markdown.markdown(
        md_text,
        extensions=["extra", "smarty", "sane_lists"],
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<style>
{EMBEDDED_CSS}
</style>
</head>
<body>
{html_body}
</body>
</html>"""


def _is_url(arg: str) -> bool:
    """Check whether the argument looks like a URL rather than a file path."""
    return arg.startswith("http://") or arg.startswith("https://")


def _slug_from_url(url: str) -> str:
    """Derive a filesystem-safe slug from a URL for cache directory naming."""
    parsed = urlparse(url)
    # -- Combine host and path into a readable slug
    raw = f"{parsed.netloc}{parsed.path}".rstrip("/")
    # -- Replace non-alphanumeric chars with hyphens, collapse multiples
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", raw).strip("-").lower()
    # -- Append a short hash for uniqueness
    url_hash = hashlib.md5(url.encode()).hexdigest()[:8]  # noqa: S324
    return f"{slug}-{url_hash}"


def _run_surf(args: list[str], *, timeout: int = 60) -> str:
    """Run a surf CLI command and return its stdout.

    Raises RuntimeError if surf fails or is not found.
    """
    cmd = ["surf", *args]
    logger.debug("Running: %s", " ".join(cmd))
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except FileNotFoundError as exc:
        msg = "surf CLI not found — install it or use file mode instead"
        raise RuntimeError(msg) from exc
    except subprocess.TimeoutExpired as exc:
        msg = f"surf command timed out after {timeout}s: {' '.join(cmd)}"
        raise RuntimeError(msg) from exc

    if result.returncode != 0:
        logger.error("surf stderr: %s", result.stderr.strip())
        msg = f"surf command failed (exit {result.returncode}): {' '.join(cmd)}"
        raise RuntimeError(msg)

    return result.stdout


def fetch_page_with_surf(url: str) -> tuple[Path, Path | None]:
    """Navigate to a URL with surf and download the page HTML + images.

    Uses the user's live browser session (authentication/cookies preserved).
    Returns (html_path, files_dir) in the cache directory.
    """
    slug = _slug_from_url(url)
    page_dir = CACHE_DIR / slug
    files_dir = page_dir / "images"
    page_dir.mkdir(parents=True, exist_ok=True)
    files_dir.mkdir(parents=True, exist_ok=True)

    # -- Step 1: Navigate to the URL in the user's browser
    logger.info("Navigating to %s via surf...", url)
    _run_surf(["navigate", url], timeout=30)

    # -- Step 2: Wait for page to settle (dynamic content, lazy images)
    time.sleep(3)

    # -- Step 3: Capture the fully-rendered HTML from the DOM
    logger.info("Capturing rendered HTML...")
    html_content = _run_surf(
        ["js", "document.documentElement.outerHTML"],
        timeout=15,
    )
    # -- surf js output may be JSON-encoded (quoted string); unwrap it
    if html_content.startswith('"') and html_content.rstrip().endswith('"'):
        try:
            html_content = json.loads(html_content)
        except json.JSONDecodeError:
            pass

    html_path = page_dir / "page.html"
    html_path.write_text(html_content, encoding="utf-8")
    logger.info("Saved HTML: %d chars", len(html_content))

    # -- Step 4: Extract all image URLs from the page via JavaScript
    logger.info("Extracting image URLs...")
    js_extract = """
    JSON.stringify(
        [...document.querySelectorAll('img[src]')]
            .map(i => i.src)
            .filter(s => s.startsWith('http'))
            .filter((v, i, a) => a.indexOf(v) === i)
    )
    """
    img_urls_raw = _run_surf(["js", js_extract.strip()], timeout=15)
    try:
        img_urls = json.loads(img_urls_raw)
        if isinstance(img_urls, str):
            # -- Double-encoded: surf wrapped it in quotes
            img_urls = json.loads(img_urls)
    except (json.JSONDecodeError, TypeError):
        logger.warning("Could not parse image URLs from surf output")
        img_urls = []

    logger.info("Found %d image URLs", len(img_urls))

    # -- Step 5: Download each image to the cache files directory
    for img_url in img_urls:
        try:
            # -- Derive a filename from the URL path
            parsed = urlparse(img_url)
            filename = Path(parsed.path).name or "image"
            # -- Avoid collisions by prefixing with a short hash
            url_hash = hashlib.md5(img_url.encode()).hexdigest()[:6]  # noqa: S324
            safe_name = f"{url_hash}-{filename}"
            dest = files_dir / safe_name

            if dest.exists():
                continue

            resp = requests.get(img_url, timeout=15)
            resp.raise_for_status()
            dest.write_bytes(resp.content)
            logger.debug("Downloaded: %s -> %s", img_url, safe_name)
        except Exception as exc:
            logger.warning("Failed to download image %s: %s", img_url, exc)

    logger.info("Downloaded images to %s", files_dir)
    return html_path, files_dir


def _inline_remote_images(md_text: str) -> tuple[str, int]:
    """Download and inline any remaining remote image URLs as base64.

    This handles images that weren't in the local _files/ directory —
    typically from URL-mode where MarkItDown preserved absolute URLs.
    """
    count = 0
    img_pattern = re.compile(r"!\[([^\]]*)\]\((https?://[^)]+)\)")

    def _replace(match: re.Match) -> str:
        nonlocal count
        alt = match.group(1)
        url = match.group(2)

        try:
            resp = requests.get(url, timeout=15)
            resp.raise_for_status()
        except Exception as exc:
            logger.warning("Failed to fetch remote image %s: %s", url, exc)
            return match.group(0)

        try:
            img = Image.open(io.BytesIO(resp.content))
            if img.mode in ("RGBA", "P", "LA"):
                img = img.convert("RGB")
            elif img.mode != "RGB":
                img = img.convert("RGB")

            if img.width > MAX_IMAGE_WIDTH:
                ratio = MAX_IMAGE_WIDTH / img.width
                img = img.resize(
                    (MAX_IMAGE_WIDTH, int(img.height * ratio)), Image.LANCZOS
                )

            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=JPEG_QUALITY, optimize=True)
            b64 = base64.b64encode(buf.getvalue()).decode("ascii")
            count += 1
            return f"![{alt}](data:image/jpeg;base64,{b64})"
        except Exception as exc:
            logger.warning("Failed to process remote image %s: %s", url, exc)
            return match.group(0)

    result = img_pattern.sub(_replace, md_text)
    return result, count


def process_html(
    html_path: Path,
    files_dir: Path | None,
    output_path: Path,
) -> tuple[Path, int]:
    """Core pipeline: HTML → markdown → clean → inline images → styled HTML.

    Returns (output_path, image_count).
    """
    # -- Convert HTML → markdown via MarkItDown
    converter = MarkItDown()
    result = converter.convert(str(html_path))
    md_text = result.text_content
    logger.info("Converted to markdown: %d characters", len(md_text))

    # -- Clean the markdown
    md_text = clean_markdown(md_text)
    logger.info("Cleaned markdown: %d characters", len(md_text))

    # -- Inline local images as base64
    md_text, img_count = inline_images(md_text, files_dir)
    logger.info("Inlined %d local images", img_count)

    # -- Inline any remaining remote images (URL-mode leftovers)
    md_text, remote_count = _inline_remote_images(md_text)
    if remote_count:
        logger.info("Inlined %d remote images", remote_count)
    total_images = img_count + remote_count

    # -- Convert to styled HTML
    html_output = markdown_to_html(md_text)

    # -- Write output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html_output, encoding="utf-8")

    return output_path, total_images


def _log_output_stats(output_path: Path, img_count: int) -> None:
    """Log the output file path, size, and image count."""
    size_kb = output_path.stat().st_size / 1024
    size_unit = "KB" if size_kb < 1024 else "MB"
    size_display = size_kb if size_kb < 1024 else size_kb / 1024

    logger.info("Output: %s", output_path)
    logger.info("Size: %.1f %s", size_display, size_unit)
    logger.info("Images inlined: %d", img_count)


def main() -> None:
    """Entry point: convert a browser-saved HTML file or URL to a shareable page."""
    if len(sys.argv) < 2:
        logger.error("Usage: html_to_share.py <input.html | URL>")
        sys.exit(1)

    arg = sys.argv[1]

    if _is_url(arg):
        # -- URL mode: fetch with surf, then process
        logger.info("URL mode: %s", arg)
        html_path, files_dir = fetch_page_with_surf(arg)
        slug = _slug_from_url(arg)
        output_path = OUTPUT_DIR / f"{slug}-share.html"
        output_path, img_count = process_html(html_path, files_dir, output_path)
        _log_output_stats(output_path, img_count)
    else:
        # -- File mode: process local HTML with companion _files/ dir
        input_path = Path(arg).resolve()
        if not input_path.is_file():
            logger.error("File not found: %s", input_path)
            sys.exit(1)

        logger.info("Processing: %s", input_path)

        files_dir = find_files_dir(input_path)
        if files_dir:
            logger.info("Found companion directory: %s", files_dir)
        else:
            logger.warning(
                "No companion _files/ directory found — images won't be inlined"
            )

        output_path = input_path.parent / f"{input_path.stem}-share.html"
        output_path, img_count = process_html(input_path, files_dir, output_path)
        _log_output_stats(output_path, img_count)


if __name__ == "__main__":
    main()
