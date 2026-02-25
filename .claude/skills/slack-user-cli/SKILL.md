---
name: slack-user-cli
description:
  "Read and write Slack channels, DMs, threads, and search from the terminal
  using slack_user_cli. Use when the user asks to interact with Slack
  workspaces, read messages, send messages, or search Slack."
allowed-tools:
  - Bash
  - Read
---

# Slack User CLI

Terminal access to Slack using browser session credentials (`xoxc-` token + `d`
cookie). Located at `~/.claude/skills/slack-user-cli/scripts/slack_user_cli.py`.

## Running

All commands use `uv run`:

```bash
uv run ~/.claude/skills/slack-user-cli/scripts/slack_user_cli.py <command> [options]
```

## Authentication

Must be logged in before using any command. Credentials are stored in
`~/.config/slack-user-cli/config.json`.

```bash
# Auto-extract from Slack desktop app (close Slack first)
slack_user_cli login --auto

# Import all workspaces from browser — copies to clipboard, reads via pbpaste
slack_user_cli login --browser

# Add a single workspace manually
slack_user_cli login --manual
```

## Global Options

| Option                            | Description                                 |
| --------------------------------- | ------------------------------------------- |
| `-w <name>`, `--workspace <name>` | Use a specific workspace instead of default |
| `--debug`                         | Enable debug logging                        |

## Commands Reference

### Workspace Management

```bash
# List all saved workspaces
slack_user_cli workspaces

# Set default workspace
slack_user_cli default "Workspace Name"

# Force-refresh the channel and user cache
slack_user_cli refresh
```

### Reading

```bash
# List joined channels (add --all for every visible channel)
slack_user_cli channels
slack_user_cli channels --all
slack_user_cli channels --type "public_channel,private_channel,mpim,im"

# Read recent messages from a channel (by name or ID)
slack_user_cli read <channel_name_or_id> --limit 20

# Read thread replies (use --dm when CHANNEL is a user name, not a channel)
slack_user_cli thread <channel_name_or_id> <message_ts>
slack_user_cli thread --dm <user_name_or_id> <message_ts>

# Read a thread directly from a Slack permalink URL
slack_user_cli url "https://workspace.slack.com/archives/C.../p..."

# List workspace members
slack_user_cli users

# List channels a user is a member of (by username or user ID)
slack_user_cli user-channels <user_name_or_id>
slack_user_cli user-channels <user_name_or_id> --type "public_channel,private_channel,mpim"
```

### Writing

**CRITICAL: Before sending any message to a main channel (i.e. a `send` command
WITHOUT `--thread`), you MUST use `AskUserQuestion` to get explicit approval.**
Posting to a main channel is visible to everyone and cannot be undone. Always
confirm with the user first. Thread replies (`--thread`) do not require this
approval.

**Permalink timestamp parsing:** When replying to a thread from a Slack
permalink URL (e.g. `https://...slack.com/archives/C.../p1772027814307689`),
extract the thread_ts by inserting a dot before the last 6 digits of the `p`
value: `p1772027814307689` → `1772027814.307689`. Double-check this conversion
before sending.

```bash
# Send a message to a channel (use --thread to reply in a thread)
slack_user_cli send <channel_name_or_id> "message text"
slack_user_cli send <channel_name_or_id> "reply text" --thread <message_ts>

# DM a user (by display name or user ID; use --thread for thread replies)
slack_user_cli dm <user_name_or_id> "message text"
slack_user_cli dm <user_name_or_id> "reply text" --thread <message_ts>

# Read DM history (omit message)
slack_user_cli dm <user_name_or_id>
```

### File Uploads

**Same approval rules as Writing above** — uploading to a main channel (without
`--thread`) requires `AskUserQuestion` confirmation first.

```bash
# Upload a file to a channel
slack_user_cli upload <channel_name_or_id> /path/to/file.png

# Upload with a message and title
slack_user_cli upload <channel_name_or_id> /path/to/file.png --message "Here's the report" --title "Q1 Report"

# Upload in a thread
slack_user_cli upload <channel_name_or_id> /path/to/file.png --thread <message_ts>

# Upload a file via DM
slack_user_cli dm-upload <user_name_or_id> /path/to/file.png

# DM upload with message and in a thread
slack_user_cli dm-upload <user_name_or_id> /path/to/file.png --message "See attached" --thread <message_ts>
```

### Important: DM User Name Resolution

When using `dm`, the USER argument must match the Slack **username** (e.g.
`first.last`), not the display name with spaces (e.g. `First Last`). Use
`search "from:<username>"` to discover the correct username format.

### Search

```bash
# Search messages
slack_user_cli search "query" --count 20 --page 1
```

### Canvases

```bash
# Read a canvas by URL (outputs plain text by default)
slack_user_cli canvas "https://workspace.slack.com/docs/TEAM_ID/FILE_ID"

# Read a canvas by file ID
slack_user_cli canvas F0ADRFZ3UUV

# Get raw HTML output
slack_user_cli canvas "https://workspace.slack.com/docs/TEAM_ID/FILE_ID" --html

# Append markdown to a canvas (default: insert_at_end)
slack_user_cli canvas-edit F0ADRFZ3UUV "## New Section\nSome text"

# Replace entire canvas content
slack_user_cli canvas-edit F0ADRFZ3UUV "## Fresh Start" --operation replace

# Prepend content
slack_user_cli canvas-edit F0ADRFZ3UUV "## Header" --operation insert_at_start

# Pipe content from a file or heredoc
cat summary.md | slack_user_cli canvas-edit F0ADRFZ3UUV --operation replace
```

### Cross-workspace Usage

```bash
# Read from a specific workspace
slack_user_cli -w "Other Workspace" channels
slack_user_cli -w "Other Workspace" read general --limit 5
```

## Cache

Channel and user data is cached to disk for fast resolution:

- **Location**: `~/.config/slack-user-cli/cache/<workspace>/`
- **Files**: `channels.json` (name→id map), `users.json` (id→display, name→id,
  display→id maps)
- **TTL**: 1 hour — cache auto-expires and is rebuilt on next use
- **Refresh**: run `slack_user_cli refresh` to force-rebuild both caches
- **Behavior**: `resolve_user()` passively reads disk cache, falling back to a
  single `users_info` API call — never triggers a full `users_list` build.
  `resolve_channel()` and `_resolve_user_by_name()` will auto-build the cache on
  first use if it doesn't exist.

Run `refresh` after joining new channels or when user lookups return IDs instead
of names.

## Key Details

- **Auth model**: `xoxc-` token (per-workspace) + `d` cookie (shared across
  workspaces), extracted from browser or Slack desktop app
- **Config location**: `~/.config/slack-user-cli/config.json`
- **Cache location**: `~/.config/slack-user-cli/cache/<workspace>/`
- **Multi-workspace**: stores all workspaces; use `-w` to switch or `default` to
  set the default
- **Channel resolution**: accepts channel names (without `#`) or IDs (starting
  with C/D/G); uses disk cache for fast lookup
- **User resolution**: accepts display names, usernames, or user IDs (starting
  with U); uses disk cache + single API fallback
- **Pagination**: handled automatically for channels, users, messages, and
  threads
- **Search**: uses page-based pagination (`--page`, `--count`)
- **Output**: formatted with Rich tables and colored text
- **Timestamps**: message timestamps (`ts`) are displayed as `YYYY-MM-DD HH:MM`
  UTC

## Troubleshooting

- **"Not logged in"**: run `slack_user_cli login --browser` or `--manual`
- **"Workspace not found"**: check available names with
  `slack_user_cli workspaces`
- **Token expired**: tokens expire on Slack logout; re-run `login`
- **Too many channels**: `channels` shows only joined by default; this is
  correct
- **macOS Keychain prompt**: expected when using `--auto` (cookie decryption)
- **User shows as ID instead of name**: run `slack_user_cli refresh` to rebuild
  the user cache
- **Channel not found after joining**: run `slack_user_cli refresh` to rebuild
  the channel cache
