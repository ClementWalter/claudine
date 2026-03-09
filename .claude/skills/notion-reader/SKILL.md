---
name: notion-reader
description:
  "Read Notion pages using browser session cookies (token_v2). Use when the
  user asks to read, fetch, or summarize Notion pages."
allowed-tools:
  - Bash
  - Read
---

# Notion Reader

Read Notion pages using browser session cookies (`token_v2`), similar to the
Slack User CLI approach. Located at
`~/.claude/skills/notion-reader/scripts/notion_reader.py`.

## Running

```bash
uv run ~/.claude/skills/notion-reader/scripts/notion_reader.py <command> [options]
```

## Authentication

```bash
# Auto-extract from Notion desktop app
notion_reader login --auto

# Enter token_v2 manually (from browser DevTools → Cookies)
notion_reader login --manual
```

Credentials stored in `~/.config/notion-reader/config.json`.

## Commands

```bash
# Read a page by URL
notion_reader read "https://www.notion.so/zamaai/Page-Title-abc123..."

# Read a page by ID
notion_reader read "abc123def456..."

# Dump raw JSON (for debugging)
notion_reader read-raw "https://www.notion.so/..."
```

## Getting token_v2 manually

1. Open Notion in your browser
2. DevTools → Application → Cookies → `notion.so`
3. Copy the value of `token_v2`

## Key Details

- **Auth**: `token_v2` cookie from Notion desktop app or browser
- **Config**: `~/.config/notion-reader/config.json`
- **API**: Uses Notion's internal `loadPageChunk` API (not the official API)
- **Limitations**: Internal API may change; large pages may need multiple chunks
