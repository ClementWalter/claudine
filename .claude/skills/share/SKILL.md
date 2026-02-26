---
name: "share"
description:
  "Convert browser-saved HTML files (Save As > Web Page, Complete) into
  self-contained, lightweight, shareable HTML with inlined images. Use when the
  user provides a locally saved .html file and asks to make it shareable,
  readable, or sendable via email/Slack."
---

# Share Skill

## When to use

- User provides a browser-saved HTML file and wants a clean, shareable version.
- User mentions making an article "shareable", "sendable", or "self-contained".
- User has a `<name>.html` + `<name>_files/` pair from "Save As > Web Page,
  Complete".

## Workflow

1. Run the conversion script on the input HTML file:

```bash
uv run ~/.claude/skills/share/scripts/html_to_share.py "<path_to_html>"
```

2. Report to the user:
   - Output file path (`<stem>-share.html` next to the original)
   - File size
   - Number of images inlined
   - Suggest opening in browser to verify

## What it does

- Converts HTML → Markdown (via MarkItDown) → cleans content → converts back to
  styled HTML
- Inlines all local images as base64 data URIs (resized to max 1000px, JPEG Q72)
- Strips tracking, navigation, footer, duplicate responsive images, and other
  web artifacts
- Produces a single self-contained HTML file with embedded CSS (Georgia serif,
  720px max-width, clean typography)

## Limitations

- Only processes local images from the companion `_files/` directory
- Remote images referenced by URL are left as-is
- Very large image-heavy articles may produce files of 5+ MB
