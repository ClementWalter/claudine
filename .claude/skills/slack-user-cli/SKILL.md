---
name: slack-user-cli
description: "Read and write Slack channels, DMs, threads, and search from the terminal using slack_user_cli. Use when the user asks to interact with Slack workspaces, read messages, send messages, or search Slack."
allowed-tools:
  - Bash
  - Read
---

# Slack User CLI

Terminal access to Slack using browser session credentials (`xoxc-` token + `d`
cookie). Located at `/Users/clementwalter/Documents/slack-user-cli/slack_user_cli.py`.

## Running

All commands use `uv run`:

```bash
uv run /Users/clementwalter/Documents/slack-user-cli/slack_user_cli.py <command> [options]
```

If symlinked to PATH as `slack_user_cli`:

```bash
slack_user_cli <command> [options]
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

| Option | Description |
|--------|-------------|
| `-w <name>`, `--workspace <name>` | Use a specific workspace instead of default |
| `--debug` | Enable debug logging |

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
```

### Writing

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

### Important: DM User Name Resolution

When using `dm`, the USER argument must match the Slack **username** (e.g.
`mathieu.saugier`), not the display name with spaces (e.g. `Mathieu Saugier`).
Use `search "from:<username>"` to discover the correct username format.

### Search

```bash
# Search messages
slack_user_cli search "query" --count 20 --page 1
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
- **Files**: `channels.json` (name→id map), `users.json` (id→display,
  name→id, display→id maps)
- **TTL**: 1 hour — cache auto-expires and is rebuilt on next use
- **Refresh**: run `slack_user_cli refresh` to force-rebuild both caches
- **Behavior**: `resolve_user()` passively reads disk cache, falling back to a
  single `users_info` API call — never triggers a full `users_list` build.
  `resolve_channel()` and `_resolve_user_by_name()` will auto-build the cache
  on first use if it doesn't exist.

Run `refresh` after joining new channels or when user lookups return IDs
instead of names.

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
- **"Workspace not found"**: check available names with `slack_user_cli workspaces`
- **Token expired**: tokens expire on Slack logout; re-run `login`
- **Too many channels**: `channels` shows only joined by default; this is correct
- **macOS Keychain prompt**: expected when using `--auto` (cookie decryption)
- **User shows as ID instead of name**: run `slack_user_cli refresh` to rebuild
  the user cache
- **Channel not found after joining**: run `slack_user_cli refresh` to rebuild
  the channel cache
