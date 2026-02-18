# Claudine

Claudine is Claude's sister. She knows him well, and is your best gateway to
Claude.

## How to use Claudine

Claudine is basically a collection of skills and hooks or Claude so that Claude
doesn't get lost.

To use, either copy `cp -r .claude/ <some location>/.claude/` or symlink
`ln -s .claude/ <some location>/.claude/`.

Using symlinks is recommended because it allows Claudine to self-improves
easily.

If you want Claudine's twin, Codexine, it's fine. Just replace `.claude/` with
`.codex/`, there are the same (symlinked).

## Setup

Add the `CLAUDINE_DIR` env var to your shell so the sync script knows where to
find Claudine:

```bash
echo 'export CLAUDINE_DIR="'$(pwd)'"' >> ~/.zshrc
```

## Syncing skills

Use the `skill-sync` script to sync the skills to your current directory:

```bash
uv run scripts/skill_sync.py
```

This will create symlinks in your current directory to the skills in the
`.claude/` directory and update `.gitignore` accordingly.
