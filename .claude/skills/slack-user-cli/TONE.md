# Slack Message Tone Guide

## Do's

- **Start with humility** when outside your core expertise ("I'm def not a
  security expert so won't comment on this part")
- **Use casual connectors**: "def", "like", "also", "though"
- **Build on the conversation** with "also", "maybe" — don't redirect or
  reframe
- **Use parentheses for asides**, not em dashes
- **Keep it one paragraph** — no bullet points, no headers, no sign-offs
- **Be constructive** — suggest improvements, don't just agree or critique
- **Be concrete** — name specific tools/approaches (Dockerfile, reusable GH
  workflow) rather than abstract principles

## Don'ts

- **Don't be assertive on topics outside your expertise** — hedge or
  acknowledge limits
- **Don't add a punchy closing summary** ("Turns X into Y") — just end
  naturally
- **Don't use formal connectors** — no em dashes (—), no "Essentially:",
  no "That way..."
- **Don't use marketing-speak** — no "infra-as-code", "idempotent by design",
  "versionable, testable, and auditable"
- **Don't number items** — list things inline with commas, not 1. 2. 3.
- **Don't overclaim** — say "it looks solid" not "the security design is solid"
  when you haven't deeply reviewed it
- **Don't add context the other person already knows** — they know what bash
  concerns are, don't re-explain

## Examples

**Too formal (bad):**
> Agreed on the bash concern. The security design is solid though. Turns the
> README from docs into infra-as-code.

**Right tone (good):**
> I'm def not a security expert so won't comment on this part, it looks solid
> though. Maybe the repo could also ship actual provisioning tooling like a
> Dockerfile for the runner, reusable GH workflow that target repos just uses:,
> and a bootstrap script (for CODEOWNERS + branch protection)
