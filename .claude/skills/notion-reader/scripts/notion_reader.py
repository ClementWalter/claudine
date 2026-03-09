#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.11"
# dependencies = ["requests", "click", "rich"]
# ///
"""Read Notion pages using browser session cookies (token_v2).

Extracts authentication from the Notion desktop app cookie store
and fetches page content via Notion's internal API.
"""

import json
import logging
import os
import re
import sqlite3
import subprocess
import tempfile
import shutil
from pathlib import Path

import click
import requests
from rich.console import Console
from rich.markdown import Markdown

logger = logging.getLogger(__name__)
console = Console()

CONFIG_DIR = Path.home() / ".config" / "notion-reader"
CONFIG_FILE = CONFIG_DIR / "config.json"

# Notion desktop app cookie paths on macOS
NOTION_COOKIE_PATHS = [
    Path.home() / "Library" / "Application Support" / "Notion" / "Cookies",
    Path.home() / "Library" / "Application Support" / "Notion Enhanced" / "Cookies",
]

NOTION_API_BASE = "https://www.notion.so/api/v3"


def _load_config() -> dict:
    """Load saved configuration from disk."""
    if CONFIG_FILE.exists():
        return json.loads(CONFIG_FILE.read_text())
    return {}


def _save_config(config: dict) -> None:
    """Persist configuration to disk."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(config, indent=2))


def _extract_token_from_notion_app() -> str | None:
    """Extract token_v2 from the Notion desktop app's cookie database.

    Copies the DB to a temp file to avoid SQLite locking issues
    when Notion is running.
    """
    for cookie_path in NOTION_COOKIE_PATHS:
        if not cookie_path.exists():
            continue

        # Copy to temp to avoid lock contention with running Notion app
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            shutil.copy2(str(cookie_path), tmp_path)
            conn = sqlite3.connect(tmp_path)
            cursor = conn.cursor()

            # Chromium-based cookie DB schema
            cursor.execute(
                "SELECT name, value FROM cookies "
                "WHERE host_key LIKE '%notion%' AND name = 'token_v2'"
            )
            row = cursor.fetchone()
            conn.close()

            if row and row[1]:
                return row[1]

            # If value is empty, it may be encrypted (Chromium v10+)
            # Fall back to manual entry
            logger.debug("token_v2 found but value is encrypted or empty")
        except Exception as exc:
            logger.debug("Failed to read cookie DB %s: %s", cookie_path, exc)
        finally:
            os.unlink(tmp_path)

    return None


def _get_token() -> str:
    """Retrieve the Notion token_v2, from config or environment."""
    # Environment override
    env_token = os.environ.get("NOTION_TOKEN_V2")
    if env_token:
        return env_token

    config = _load_config()
    token = config.get("token_v2")
    if token:
        return token

    raise click.ClickException(
        "No Notion token found. Run: notion_reader login"
    )


def _notion_request(endpoint: str, payload: dict, token: str) -> dict:
    """Make an authenticated request to Notion's internal API.

    Uses the same headers and cookies a browser session would send,
    including the Notion-specific audit log header required by the v3 API.
    """
    resp = requests.post(
        f"{NOTION_API_BASE}/{endpoint}",
        json=payload,
        cookies={"token_v2": token},
        headers={
            "Content-Type": "application/json",
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/131.0.0.0 Safari/537.36"
            ),
            "accept": "application/json",
            "accept-language": "en-US,en;q=0.9",
            # Notion's internal API requires this header for authenticated calls
            "notion-audit-log-platform": "web",
            "notion-client-version": "23.13.0.2",
        },
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def _parse_notion_url(url: str) -> str:
    """Extract page ID from a Notion URL.

    Supports formats:
      - https://www.notion.so/workspace/Page-Title-abc123def456...
      - https://www.notion.so/abc123def456...
      - abc123def456 (raw ID with or without dashes)
      - URL with anchor #section_id
    """
    # Strip anchor for the page ID (we'll handle sections separately)
    url = url.split("#")[0].split("?")[0]

    # Extract the hex ID (32 chars) from the URL or raw input
    match = re.search(r"([a-f0-9]{32})", url.replace("-", ""))
    if match:
        raw = match.group(1)
        # Format as UUID: 8-4-4-4-12
        return f"{raw[:8]}-{raw[8:12]}-{raw[12:16]}-{raw[16:20]}-{raw[20:]}"

    raise click.ClickException(f"Could not extract page ID from: {url}")


def _blocks_to_text(block_map: dict, block_id: str, indent: int = 0) -> str:
    """Recursively convert Notion block data to readable text."""
    lines = []
    block_data = block_map.get(block_id, {})
    block_value = block_data.get("value", {})

    block_type = block_value.get("type", "")
    properties = block_value.get("properties", {})
    title_parts = properties.get("title", [])

    # Extract text from rich text array
    text = ""
    for part in title_parts:
        if isinstance(part, list) and len(part) > 0:
            text += part[0] if isinstance(part[0], str) else ""

    prefix = "  " * indent

    if block_type == "header":
        lines.append(f"\n{'#' * 1} {text}")
    elif block_type == "sub_header":
        lines.append(f"\n{'#' * 2} {text}")
    elif block_type == "sub_sub_header":
        lines.append(f"\n{'#' * 3} {text}")
    elif block_type == "bulleted_list":
        lines.append(f"{prefix}• {text}")
    elif block_type == "numbered_list":
        lines.append(f"{prefix}1. {text}")
    elif block_type == "to_do":
        checked = properties.get("checked", [["No"]])[0][0]
        marker = "[x]" if checked == "Yes" else "[ ]"
        lines.append(f"{prefix}{marker} {text}")
    elif block_type == "toggle":
        lines.append(f"{prefix}▸ {text}")
    elif block_type == "quote":
        lines.append(f"{prefix}> {text}")
    elif block_type == "code":
        language = properties.get("language", [[""]])[0][0]
        lines.append(f"{prefix}```{language}")
        lines.append(f"{prefix}{text}")
        lines.append(f"{prefix}```")
    elif block_type == "callout":
        lines.append(f"{prefix}💡 {text}")
    elif block_type == "divider":
        lines.append(f"{prefix}---")
    elif block_type == "table_row":
        cells = properties.get("title", [])
        # table_row properties are different
        pass
    elif block_type in ("page", "collection_view_page"):
        if text:
            lines.append(f"\n{'#' * 1} {text}")
    elif text:
        lines.append(f"{prefix}{text}")

    # Recurse into children
    content_ids = block_value.get("content", [])
    for child_id in content_ids:
        child_text = _blocks_to_text(block_map, child_id, indent + 1)
        if child_text:
            lines.append(child_text)

    return "\n".join(lines)


def _fetch_page_content(page_id: str, token: str) -> str:
    """Fetch a Notion page and return its text content."""
    # Load the page's block tree
    data = _notion_request(
        "loadPageChunk",
        {
            "pageId": page_id,
            "limit": 100,
            "cursor": {"stack": []},
            "chunkNumber": 0,
            "verticalColumns": False,
        },
        token,
    )

    block_map = data.get("recordMap", {}).get("block", {})
    if not block_map:
        raise click.ClickException("No content found for this page.")

    return _blocks_to_text(block_map, page_id)


@click.group()
@click.option("--debug", is_flag=True, help="Enable debug logging")
def cli(debug: bool) -> None:
    """Read Notion pages using browser session cookies."""
    if debug:
        logging.basicConfig(level=logging.DEBUG)


@cli.command()
@click.option("--auto", "method", flag_value="auto", default=True,
              help="Extract from Notion desktop app (default)")
@click.option("--manual", "method", flag_value="manual",
              help="Enter token_v2 manually")
def login(method: str) -> None:
    """Save Notion authentication credentials."""
    token = None

    if method == "auto":
        console.print("Extracting token from Notion desktop app...")
        token = _extract_token_from_notion_app()
        if not token:
            console.print(
                "[yellow]Could not extract token automatically. "
                "The cookie value may be encrypted.[/yellow]\n"
                "To get your token manually:\n"
                "1. Open Notion in your browser\n"
                "2. Open DevTools → Application → Cookies → notion.so\n"
                "3. Copy the value of 'token_v2'"
            )
            token = click.prompt("Paste your token_v2")

    elif method == "manual":
        console.print(
            "To get your token:\n"
            "1. Open Notion in your browser\n"
            "2. Open DevTools → Application → Cookies → notion.so\n"
            "3. Copy the value of 'token_v2'"
        )
        token = click.prompt("Paste your token_v2")

    if token:
        config = _load_config()
        config["token_v2"] = token.strip()
        _save_config(config)
        console.print("[green]Token saved successfully.[/green]")


@cli.command()
@click.argument("url")
def read(url: str) -> None:
    """Read a Notion page by URL or ID.

    URL can be a full Notion URL or just the page ID.
    """
    token = _get_token()
    page_id = _parse_notion_url(url)
    logger.debug("Fetching page %s", page_id)

    content = _fetch_page_content(page_id, token)
    console.print(content)


@cli.command()
@click.argument("url")
def read_raw(url: str) -> None:
    """Read a Notion page and dump the raw block JSON (for debugging)."""
    token = _get_token()
    page_id = _parse_notion_url(url)

    data = _notion_request(
        "loadPageChunk",
        {
            "pageId": page_id,
            "limit": 100,
            "cursor": {"stack": []},
            "chunkNumber": 0,
            "verticalColumns": False,
        },
        token,
    )

    console.print_json(json.dumps(data, indent=2, default=str))


if __name__ == "__main__":
    cli()
