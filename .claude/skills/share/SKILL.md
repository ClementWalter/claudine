---
name: "share"
description:
  "Convert browser-saved HTML files or URLs into self-contained, lightweight,
  shareable HTML with inlined images. Use when the user provides a locally saved
  .html file or a URL and asks to make it shareable, readable, or sendable via
  email/Slack."
---

# Share Skill

## When to use

- User provides a browser-saved HTML file and wants a clean, shareable version.
- User provides a URL and wants a shareable, self-contained copy.
- User mentions making an article "shareable", "sendable", or "self-contained".
- User has a `<name>.html` + `<name>_files/` pair from "Save As > Web Page,
  Complete".

## Workflow

### From a local HTML file

1. Run the conversion script on the input HTML file:

```bash
uv run ~/.claude/skills/share/scripts/html_to_share.py "<path_to_html>"
```

2. Report to the user:
   - Output file path (`<stem>-share.html` next to the original)
   - File size
   - Number of images inlined
   - Suggest opening in browser to verify

### From a URL

1. Ensure surf CLI is available (the user's browser must be running with the surf
   extension).

2. Run the conversion script with the URL:

```bash
uv run ~/.claude/skills/share/scripts/html_to_share.py "<url>"
```

3. Report to the user:
   - Output file path (`~/Desktop/<slug>-share.html`)
   - File size
   - Number of images inlined
   - Suggest opening in browser to verify

## What it does

- **File mode**: Reads the saved HTML + companion `_files/` directory
- **URL mode**: Uses `surf` CLI to navigate with the user's live browser session
  (preserving auth/cookies), captures the rendered DOM, and downloads images
- Converts HTML → Markdown (via MarkItDown) → cleans content → converts back to
  styled HTML
- Inlines all images as base64 data URIs (resized to max 1000px, JPEG Q72)
- Strips tracking, navigation, footer, duplicate responsive images, and other
  web artifacts
- Produces a single self-contained HTML file with embedded CSS (Georgia serif,
  720px max-width, clean typography)

## Limitations

- URL mode requires `surf` CLI and a running Chrome browser with the surf
  extension
- URL mode uses the user's browser session — the page must be visible/accessible
  in the browser
- Very large image-heavy articles may produce files of 5+ MB
- Paywalled content requires an active subscription in the browser session
