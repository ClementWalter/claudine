---
name: best-practices-builder
description:
  Meta-skill for creating technology-specific best practices skills. Use when
  building a new skill that codifies patterns, anti-patterns, and guidelines for
  a framework, library, or development methodology. Triggers include "create
  best practices for X", "write a skill for Y patterns", or "codify guidelines
  for Z".
---

# Best Practices Skill Builder

Guide for creating well-structured best practices skills that effectively
communicate patterns, anti-patterns, and guidelines to Claude Code agents.

## When to Use This Skill

Use when:

- Creating a new skill for framework/library/development methodology best
  practices (React, Effect, etc.)
- Codifying team conventions into a reusable skill
- Building guidelines for development methodologies (logging, testing, security)
- Converting documentation into actionable agent instructions

## Skill Structure Overview

```
{skill-name}/
├── SKILL.md                  # Main skill file (required)
├── references/               # Detailed documentation (recommended)
│   ├── {topic-1}.md
│   ├── {topic-2}.md
│   └── anti-patterns.md
└── metadata.json             # Optional: version, references
```

## SKILL.md Template

### Frontmatter (Required)

```yaml
---
name: {technology}-best-practices
description:
  Brief description of what patterns this skill enforces. Mention key triggers
  (e.g., "Use when writing code with X, Y, or Z"). Keep under 200 characters.
---
```

### Section Order

1. **Title** - `# {Technology} Best Practices`
2. **Brief intro** - 1-2 sentences on purpose
3. **Quick Reference Table** - DO/DON'T at top for scannability
4. **When to Apply** - Bullet list of trigger conditions
5. **Core Principles** - Numbered list with impact labels
6. **Pattern Sections** - H2 for each major category
7. **Anti-Patterns** - Explicit forbidden patterns
8. **Reference Index** - Links to `references/` files
9. **External Resources** - Links to official docs

## Quick Reference Table Format

Place at the top for scannability:

```markdown
| Category | DO                                        | DON'T                                |
| -------- | ----------------------------------------- | ------------------------------------ |
| Services | `Effect.Service` with `accessors: true`   | `Context.Tag` for business logic     |
| Errors   | `Schema.TaggedError` with structured data | Plain `Error` objects                |
| Layers   | `dependencies: [Dep.Default]` in service  | Manual `Layer.provide` at call sites |
```

Alternative: Category-by-priority table

```markdown
| Priority | Category                 | Impact   | Prefix    |
| -------- | ------------------------ | -------- | --------- |
| 1        | Eliminating Waterfalls   | CRITICAL | `async-`  |
| 2        | Bundle Size Optimization | CRITICAL | `bundle-` |
| 3        | Server-Side Performance  | HIGH     | `server-` |
```

## Impact Labels

Use consistently throughout:

| Label      | Use For                                                   | Color Hint |
| ---------- | --------------------------------------------------------- | ---------- |
| `CRITICAL` | Will cause bugs, security issues, or severe perf problems | Red        |
| `HIGH`     | Important practices that significantly affect quality     | Orange     |
| `MEDIUM`   | Good practices, notable improvement                       | Yellow     |
| `LOW`      | Nice-to-have, minor improvements                          | Green      |

Format in skill: `**(CRITICAL)**` or `**Impact: CRITICAL**`

## Writing Style

### Voice

- **Imperative**: "Always use X", "Never do Y", "Use X for Y"
- **Opinionated**: Clear right/wrong distinctions
- **Concise**: No filler words

### Phrasing Patterns

```markdown
<!-- Prescriptive -->

Always use `Effect.Service` for business logic services. Never use `Context.Tag`
directly for services. Use `Schema.TaggedError` for all recoverable errors.

<!-- With rationale -->

Always use X because [reason]. Never use Y - it causes [problem].

<!-- Conditional -->

When X is needed, use Y. If using X, always ensure Y.
```

## Code Examples Format

### Basic Pattern: CORRECT/WRONG Labels

```typescript
// CORRECT - Use Effect.Service for business logic
export class UserService extends Effect.Service<UserService>()("UserService", {
  accessors: true,
  effect: Effect.gen(function* () {
    const db = yield* Database;
    return {
      findUser: (id: string) =>
        db.query(`SELECT * FROM users WHERE id = ?`, [id]),
    };
  }),
  dependencies: [Database.Default],
}) {}

// WRONG - Context.Tag for business logic loses service features
const UserService = Context.Tag<UserService>("UserService");
```

### Alternative: Incorrect/Correct (Vercel style)

```markdown
**Incorrect (sequential execution, 3 round trips):**

\`\`\`typescript const user = await fetchUser() const posts = await fetchPosts()
\`\`\`

**Correct (parallel execution, 1 round trip):**

\`\`\`typescript const [user, posts] = await Promise.all([fetchUser(),
fetchPosts()]) \`\`\`
```

### Code Example Best Practices

1. **Full context** - Show complete, runnable code (not fragments)
2. **Inline comments** - Explain WHY, not what
3. **Type annotations** - Include TypeScript types
4. **Both examples together** - Show contrast immediately
5. **Quantitative impact** - When measurable ("3 round trips" vs "1 round trip")

## Anti-Patterns Section

Dedicate a section to forbidden patterns:

```markdown
## Anti-Patterns

### FORBIDDEN: Using Context.Tag for Services

\`\`\`typescript // FORBIDDEN - loses service composition benefits const
UserService = Context.Tag<UserService>("UserService") \`\`\`

**Why:** Context.Tag doesn't support `accessors`, making service composition
verbose and error-prone.

**Correct:**

\`\`\`typescript export class UserService extends
Effect.Service<UserService>()("UserService", { accessors: true, // ... }) {}
\`\`\`
```

## Reference Files Structure

Each file in `references/` should follow:

```markdown
---
title: {Topic} Patterns
impact: CRITICAL|HIGH|MEDIUM|LOW
tags: tag1, tag2, tag3
---

## {Topic} Patterns

**Impact: {LEVEL}**

Brief explanation of why this matters (1-2 paragraphs).

### Pattern 1: {Name}

Explanation of the pattern.

**Incorrect:**

\`\`\`typescript // Bad code \`\`\`

**Correct:**

\`\`\`typescript // Good code \`\`\`

### Pattern 2: {Name}

...

### When to Use/Not Use

- Use when: [conditions]
- Don't use when: [conditions]

### Reference

- [Official Docs](https://...)
```

## Creating a Best Practices Skill

### Step 1: Research the Technology

1. Read official documentation
2. Study existing best practices guides
3. Identify common pitfalls and anti-patterns
4. Find quantitative data on impact where possible

### Step 2: Categorize Patterns

Group patterns by:

- **Domain** (services, errors, state, etc.)
- **Impact level** (CRITICAL → LOW)
- **Phase** (setup, development, deployment)

### Step 3: Write the Quick Reference

Start with the DO/DON'T table - it forces clarity:

```markdown
| Category | DO  | DON'T |
| -------- | --- | ----- |
| ...      | ... | ...   |
```

### Step 4: Detail Each Pattern

For each pattern:

1. Write the rule in imperative form
2. Show CORRECT code example
3. Show WRONG code example
4. Explain WHY (the rationale)
5. Note exceptions if any

### Step 5: Extract to References

Move detailed explanations to `references/` when:

- Pattern has multiple sub-patterns
- Explanation exceeds ~50 lines
- Content is useful for deep dives but not quick reference

### Step 6: Add Anti-Patterns Section

List explicitly forbidden patterns with:

- The bad code
- Why it's bad
- The correct alternative

### Step 7: Review Checklist

- [ ] Frontmatter has name and description
- [ ] Quick reference table at top
- [ ] All patterns have impact labels
- [ ] Code examples show both CORRECT and WRONG
- [ ] WHY is explained for each rule
- [ ] Anti-patterns are explicitly forbidden
- [ ] References are cross-linked
- [ ] External docs are referenced

## Example Skills to Study

| Skill                  | Repository               | Notable Pattern               |
| ---------------------- | ------------------------ | ----------------------------- |
| Effect Best Practices  | Makisuo/skills           | Comprehensive reference files |
| React Best Practices   | vercel-labs/agent-skills | Priority-based categorization |
| Logging Best Practices | boristane/agent-skills   | Concise, focused rules        |

## Common Mistakes to Avoid

### Mistake 1: Too Much Prose, Not Enough Code

**Wrong:**

> The service pattern in Effect is important because it provides composition
> benefits and allows for better testability through dependency injection...

**Right:**

```typescript
// CORRECT - Effect.Service with accessors
export class UserService extends Effect.Service<UserService>()("UserService", {
  accessors: true,
})
```

### Mistake 2: Subjective Guidelines

**Wrong:**

> Consider using X when appropriate. You might want to think about Y.

**Right:**

> Always use X for [specific situation]. Never use Y because [specific problem].

### Mistake 3: Missing the "Why"

**Wrong:**

> Use Schema.TaggedError for errors.

**Right:**

> Use Schema.TaggedError for errors. This enables pattern matching on error
> types and preserves type safety across Effect boundaries.

### Mistake 4: No Anti-Patterns Section

Always include explicit forbidden patterns - agents need to know what NOT to do.

## Output Checklist

When creating a best practices skill, verify:

1. **Structure**
   - [ ] `SKILL.md` with proper frontmatter
   - [ ] `references/` folder if >3 detailed patterns
   - [ ] Logical section hierarchy

2. **Content**
   - [ ] Quick reference table at top
   - [ ] Impact labels on all patterns
   - [ ] CORRECT/WRONG code examples
   - [ ] WHY explanations
   - [ ] Anti-patterns section
   - [ ] External references

3. **Style**
   - [ ] Imperative voice
   - [ ] Concise phrasing
   - [ ] Full, runnable code examples
   - [ ] Consistent formatting

## Resources

- `references/skill-template.md` - Empty template to copy
- `references/example-patterns.md` - Example patterns from real skills
