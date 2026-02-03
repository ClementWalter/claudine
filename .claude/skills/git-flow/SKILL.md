---
name: git-flow
description: |
  Git workflow automation for Zama repositories. Use when:
  (1) Committing changes with minimal, meaningful messages
  (2) Creating PRs that close issues
  (3) Ensuring clean git state before operations
  Triggers: "commit", "pr", "push", "create pr", "open pr"
allowed-tools: [Bash, Read, Write, Edit, Grep, Glob]
---

# Git Flow

Automated git workflow for commits and pull requests. Enforces issue linking,
minimal commit messages, and clean git state.

---

## Commit Command

**Trigger**: "commit", "commit changes", "save changes"

### Workflow

1. **Check git status**:

   ```bash
   git status --porcelain
   ```

   If empty, inform user: "Nothing to commit - working tree is clean."

2. **If dirty, analyze changes**:

   ```bash
   git diff --stat
   git diff
   ```

3. **Group changes semantically**:
   - Identify logical units of work
   - Each unit becomes one commit
   - Prefer fewer, meaningful commits over many small ones

4. **Create commits**:

   For each logical group:

   ```bash
   git add <files>
   git commit -m "<type>(<scope>): <description>"
   ```

### Commit Message Format

See [references/commit-conventions.md](references/commit-conventions.md) for
full details.

```text
<type>(<scope>): <description>

Types: feat, fix, chore, docs, test, refactor, ci
Scope: optional component name
Description: imperative mood, no period, max 50 chars
```

**Examples**:

- `feat(kms): add retry logic for gRPC calls`
- `fix(gw-listener): handle null block events`
- `chore: bump dependencies`
- `docs: update API reference`

### Rules

- **Never** add Claude attribution or co-author lines
- Keep descriptions under 50 characters
- Use imperative mood ("add" not "added")
- No period at the end

---

## PR Command

**Trigger**: "pr", "create pr", "open pr", "push pr"

### Workflow

1. **Ask for issue reference**:

   Prompt user: "Which issue(s) does this PR close? (e.g., #42 or
   owner/repo#42)"
   - If user provides issue(s): continue to step 2
   - If user has no issue: offer to create one
     - Ask: "Would you like to create an issue first? I'll ask a few questions."
     - If yes: run the **Issue Command** interview, then use the new issue
     - If no: warn that PRs without issues are discouraged, but allow proceeding

2. **Ensure clean tree**:

   ```bash
   git status --porcelain
   ```

   If dirty, invoke the **Commit Command** first.

3. **Fetch issue context**:

   ```bash
   gh issue view <number> --json title,body
   ```

   Understand what the issue asks for.

4. **Compare with main**:

   ```bash
   git diff main...HEAD --stat
   git log main..HEAD --oneline
   ```

   - Compare actual changes to issue scope
   - **Warn** if significant divergence (work outside issue scope)
   - Do **NOT** block - just inform user

5. **Push and create PR**:

   ```bash
   git push -u origin HEAD
   ```

   ```bash
   gh pr create --title "<concise title>" --body "$(cat <<'EOF'
   <summary in 1-3 sentences>

   Closes #<issue-number>
   EOF
   )"
   ```

### PR Description Format

See [references/pr-template.md](references/pr-template.md) for the template.

**Key elements**:

- **Summary**: 1-3 sentences explaining what and why
- **Closes keyword**: `Closes #N` for EACH linked issue (auto-closes on merge)

**Example**:

```markdown
Add retry logic for gRPC calls to handle transient KMS failures.

Closes #42
```

For multiple issues:

```markdown
Refactor error handling across all KMS services.

Closes #42 Closes #43
```

---

## Issue Command

**Trigger**: "create issue", "new issue", "issue for"

Use this command to create a well-structured issue following the Why/What/How
format. Also invoked from PR Command when no issue exists.

### Interview Workflow

1. **Ask for repository** (CRITICAL - issues often belong to a different repo):

   "Which repository should this issue be created in? (e.g., owner/repo)"

2. **Why - Problem/Motivation** (always ask):

   "What problem are you solving? Why does this matter?"

3. **What - Desired Outcome**:
   - If creating issue during PR flow: derive from the actual code changes
   - If standalone: ask "What should the end result look like?"

4. **How - Approach**:
   - If creating issue during PR flow: derive from implementation in the diff
   - If standalone: ask "Do you have a preferred approach or constraints?"

### Synthesize the Issue

**CRITICAL**: Do NOT copy raw interview answers. Transform them into
professional, structured content.

- **Title**: Concise action phrase (e.g., "Add retry logic for gRPC calls")
- **Why**: Synthesize motivation into context paragraph
- **What**: Describe expected behavior/outcome
- **How**: Low-level bullet points (concise, not verbose)

See [references/issue-template.md](references/issue-template.md) for the full
template and examples.

### Create the Issue

```bash
gh issue create --repo <owner/repo> --title "<title>" --body "$(cat <<'EOF'
## Why

<synthesized motivation paragraph>

## What

<synthesized outcome description>

## How

- <implementation point 1>
- <implementation point 2>
- <implementation point 3>
EOF
)"
```

After creation, return the issue number to use in the PR.

---

## Key Behaviors

| Behavior              | Description                                                       |
| --------------------- | ----------------------------------------------------------------- |
| Issue Requirement     | PRs should close at least one issue - offers to create if missing |
| Issue Interview       | Creates issues via Why/What/How format, synthesizes answers       |
| Minimal Messages      | Commit messages are concise (50 char), not verbose                |
| Non-blocking Warnings | Divergence check warns but doesn't prevent PR                     |
| Clean State           | PR command invokes commit if tree is dirty                        |
| GitHub Keywords       | Always use `Closes #N` to auto-close issues on merge              |

---

## Quick Reference

### Commit Types

| Type     | Use Case                     |
| -------- | ---------------------------- |
| feat     | New feature                  |
| fix      | Bug fix                      |
| chore    | Maintenance, dependencies    |
| docs     | Documentation only           |
| test     | Adding or fixing tests       |
| refactor | Code change without feat/fix |
| ci       | CI/CD configuration          |

### GitHub Close Keywords

These keywords auto-close issues when the PR is merged:

- `Closes #N`
- `Fixes #N`
- `Resolves #N`

Always use `Closes` for consistency.
