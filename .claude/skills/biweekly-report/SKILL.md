---
name: biweekly-report
description: |
  Generate a bi-weekly status report from Slack channels and GitHub repos.
  Use when the user asks to generate a sprint report, bi-weekly report,
  status update, or team summary.
  Triggers: "biweekly report", "sprint report", "status report", "generate report"
user-invocable: true
allowed-tools:
  - Bash
  - Read
  - Glob
  - Grep
  - AskUserQuestion
---

# Bi-Weekly Report Generator

Generates a concise status report from Slack channels and GitHub repos.

## Step 1: Gather inputs via AskUserQuestion

Ask the user in a **single** `AskUserQuestion` for:

1. **Slack channels** — comma-separated names or IDs (e.g. `business, labs, C077CHJ97EF`)
2. **GitHub repos** — comma-separated `org/repo` (e.g. `zama-ai/fhevm, zama-ai/relayer-sdk`)
3. **Start date** — ISO date for the period start (e.g. `2026-02-24`)

If the user already provided some of these in their initial message, only ask for
the missing ones.

## Step 2: Collect data

### Slack channels

For each channel, read recent messages since the start date:

```bash
uv run ~/.claude/skills/slack-user-cli/scripts/slack_user_cli.py read <channel> --limit 100
```

Filter to messages on or after the start date. For threads with replies, use
search to get thread content:

```bash
uv run ~/.claude/skills/slack-user-cli/scripts/slack_user_cli.py search "<keywords> in:<channel>" --count 15
```

Focus on: decisions made, milestones hit, blockers raised, action items.

### GitHub repos

For each repo, collect:

```bash
# Merged PRs in the period
gh pr list --repo <org/repo> --state merged --search "merged:>=<start_date>" --limit 30 --json title,number,mergedAt,author

# Open PRs (in-progress work)
gh pr list --repo <org/repo> --state open --limit 10 --json title,number,createdAt,author

# Recent issues opened or closed
gh issue list --repo <org/repo> --state all --search "created:>=<start_date>" --limit 20 --json title,number,state,createdAt,closedAt
```

## Step 3: Generate report

Synthesize all collected data into the following **plain text** template. Keep
each bullet to 1-2 sentences max. Be concrete (mention PRs, features, partners
by name). Do NOT use markdown headers — use the exact format below:

```
Main achievements / news:

- <bullet 1>
- <bullet 2>
[2-5 bullets]

Blockers or main challenges:

- <bullet 1>
[0-3 bullets, omit section if none]

What's next for the coming sprint:

- <bullet 1>
[0-3 bullets, omit section if none]

Something important leadership should know:

- <bullet 1>
[0-2 bullets, omit section if none]
```

### Guidelines

- **Achievements**: merged PRs with impact, milestones (mainnet deployments,
  first real tokens shielded), partnership progress, SDK releases
- **Blockers**: audit gaps, smart wallet incompatibilities, contract review
  findings, infra issues
- **Next sprint**: items with clear signals from threads (planned meetings,
  upcoming deployments, RFC work)
- **Leadership**: cross-team risks, partner-blocking issues, security concerns
  that need escalation

Output the report as plain text directly — no code blocks, no markdown formatting.
The user will copy-paste it into a larger document.
