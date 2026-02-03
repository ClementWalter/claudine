# Best Practices Skill Template

Copy this template when creating a new best practices skill.

## SKILL.md Template

```markdown
---
name: {technology}-best-practices
description:
  {Brief description - what patterns this enforces and when to use it.
  Mention key triggers. Keep under 200 characters.}
---

# {Technology} Best Practices

{1-2 sentence intro explaining what this skill covers.}

## Quick Reference

| Category     | DO               | DON'T           |
| ------------ | ---------------- | --------------- |
| {Category 1} | `{good pattern}` | `{bad pattern}` |
| {Category 2} | `{good pattern}` | `{bad pattern}` |
| {Category 3} | `{good pattern}` | `{bad pattern}` |

## When to Apply

Use this skill when:

- {Trigger condition 1}
- {Trigger condition 2}
- {Trigger condition 3}

## Core Principles

1. **{Principle 1}** (CRITICAL)
   - {Brief explanation}

2. **{Principle 2}** (HIGH)
   - {Brief explanation}

3. **{Principle 3}** (MEDIUM)
   - {Brief explanation}

---

## {Pattern Category 1}

### {Pattern 1.1 Name}

**Impact: CRITICAL**

{1-2 sentences explaining why this matters.}

**Incorrect:**

\`\`\`{language} // {What's wrong with this} {bad code} \`\`\`

**Correct:**

\`\`\`{language} // {Why this is better} {good code} \`\`\`

### {Pattern 1.2 Name}

**Impact: HIGH**

{Explanation}

**Incorrect:**

\`\`\`{language} {bad code} \`\`\`

**Correct:**

\`\`\`{language} {good code} \`\`\`

---

## {Pattern Category 2}

### {Pattern 2.1 Name}

{Continue pattern...}

---

## Anti-Patterns

### FORBIDDEN: {Anti-Pattern 1 Name}

\`\`\`{language} // FORBIDDEN - {brief reason} {bad code} \`\`\`

**Why:** {Detailed explanation of the problem.}

**Correct:**

\`\`\`{language} {good code} \`\`\`

### FORBIDDEN: {Anti-Pattern 2 Name}

{Continue pattern...}

---

## Guidelines Reference

For detailed documentation on specific topics:

- **`references/{topic-1}.md`** - {Brief description}
- **`references/{topic-2}.md`** - {Brief description}
- **`references/anti-patterns.md`** - {All forbidden patterns in detail}

## External Resources

- [{Technology} Official Docs]({url})
- [{Best Practices Guide}]({url})
- [{Style Guide}]({url})
```

## Reference File Template

Create in `references/{topic}.md`:

```markdown
---
title: {Topic} Patterns
impact: CRITICAL|HIGH|MEDIUM|LOW
tags: {tag1}, {tag2}, {tag3}
---

## {Topic} Patterns

**Impact: {LEVEL}**

{2-3 paragraphs explaining:

- What this topic covers
- Why it matters
- Key concepts to understand}

### Pattern 1: {Name}

{Detailed explanation of when and why to use this pattern.}

**Incorrect:**

\`\`\`{language} // {Explanation of the problem} {bad code with inline comments}
\`\`\`

**Correct:**

\`\`\`{language} // {Explanation of why this is better} {good code with inline
comments} \`\`\`

{Optional: Additional context or variations.}

### Pattern 2: {Name}

{Continue with same structure...}

### When to Use

- Use when: {condition 1}
- Use when: {condition 2}

### When NOT to Use

- Don't use when: {exception 1}
- Don't use when: {exception 2}

### Common Mistakes

1. **{Mistake 1}** - {Brief explanation}
2. **{Mistake 2}** - {Brief explanation}

### References

- [{Related Doc}]({url})
- [{Official Guide}]({url})
```

## Directory Structure

```
{skill-name}/
├── SKILL.md                      # Main skill file
├── references/
│   ├── {core-pattern}.md         # Most important patterns (CRITICAL)
│   ├── {secondary-pattern}.md    # Important patterns (HIGH)
│   ├── {tertiary-pattern}.md     # Good practices (MEDIUM)
│   └── anti-patterns.md          # All forbidden patterns
└── metadata.json                 # Optional metadata
```

## metadata.json Template (Optional)

```json
{
  "version": "1.0.0",
  "organization": "{your-org}",
  "date": "{YYYY-MM-DD}",
  "abstract": "{One sentence description}",
  "references": [
    "https://example.com/official-docs",
    "https://example.com/best-practices"
  ]
}
```
