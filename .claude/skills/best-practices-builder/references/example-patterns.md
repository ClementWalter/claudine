# Example Patterns from Real Skills

Real-world examples extracted from production best practices skills.

## Quick Reference Table Examples

### DO/DON'T Format (Effect Style)

```markdown
| Category     | DO                                        | DON'T                                 |
| ------------ | ----------------------------------------- | ------------------------------------- |
| Services     | `Effect.Service` with `accessors: true`   | `Context.Tag` for business logic      |
| Dependencies | `dependencies: [Dep.Default]` in service  | Manual `Layer.provide` at usage sites |
| Errors       | `Schema.TaggedError` with structured data | Plain `Error` objects                 |
| Tracing      | `Effect.fn("Service.method")` wrappers    | Functions without span names          |
| Options      | `Option.filter`, `Option.orElse` chains   | `Option.isSome` checks                |
```

### Priority-Based Table (React/Vercel Style)

```markdown
| Priority | Category                  | Impact      | Prefix       |
| -------- | ------------------------- | ----------- | ------------ |
| 1        | Eliminating Waterfalls    | CRITICAL    | `async-`     |
| 2        | Bundle Size Optimization  | CRITICAL    | `bundle-`    |
| 3        | Server-Side Performance   | HIGH        | `server-`    |
| 4        | Client-Side Data Fetching | MEDIUM-HIGH | `client-`    |
| 5        | Re-render Optimization    | MEDIUM      | `rerender-`  |
| 6        | Rendering Performance     | MEDIUM      | `rendering-` |
| 7        | JavaScript Performance    | LOW-MEDIUM  | `js-`        |
| 8        | Advanced Patterns         | LOW         | `advanced-`  |
```

### Numbered Principles (Logging Style)

```markdown
## Core Principles

1. **One Wide Event Per Service Hop** (CRITICAL)
   - Emit a single, comprehensive event at the end of each service hop
   - Include all relevant context in that one event

2. **Context Over Cardinality** (CRITICAL)
   - Add rich context fields instead of multiple log lines
   - Keep cardinality manageable for metrics

3. **Single Logger Instance** (HIGH)
   - Use one configured logger throughout the application
   - Inject via middleware or DI container
```

## Code Example Styles

### Effect Style: CORRECT/WRONG with Comments

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

// WRONG - Context.Tag loses service features
const UserService = Context.Tag<UserService>("UserService");
```

### React/Vercel Style: Incorrect/Correct with Quantitative Impact

```markdown
**Incorrect (sequential execution, 3 round trips):**

\`\`\`typescript // Each await blocks the next - serial execution const user =
await fetchUser() // 100ms const posts = await fetchPosts() // 100ms const
comments = await fetchComments() // 100ms // Total: 300ms \`\`\`

**Correct (parallel execution, 1 round trip):**

\`\`\`typescript // All requests start simultaneously const [user, posts,
comments] = await Promise.all([ fetchUser(), fetchPosts(), fetchComments() ]) //
Total: ~100ms (limited by slowest request) \`\`\`
```

### Logging Style: Practical Business Context

```typescript
// Incorrect: Multiple log lines with scattered context
logger.info("Processing checkout");
logger.info(`User: ${userId}`);
logger.info(`Cart items: ${cart.items.length}`);
// ... later
logger.info("Checkout complete");

// Correct: Single wide event with all context
logger.info({
  event: "checkout.completed",
  user_id: userId,
  cart_items_count: cart.items.length,
  total_amount: cart.total,
  payment_method: payment.method,
  duration_ms: Date.now() - startTime,
});
```

## Anti-Pattern Section Styles

### FORBIDDEN Label (Effect Style)

```markdown
## FORBIDDEN: Async/Await in Effect Code

\`\`\`typescript // FORBIDDEN - breaks Effect's execution model const bad =
Effect.gen(function\* () { const data = await fetchData() // NO! Don't use await
return data }) \`\`\`

**Why:** Async/await breaks Effect's execution model, losing:

- Interruption support
- Proper error channel typing
- Tracing and observability

**Correct:**

\`\`\`typescript const good = Effect.gen(function* () { const data = yield*
Effect.tryPromise(() => fetchData()) return data }) \`\`\`
```

### Numbered Anti-Patterns (Logging Style)

```markdown
## Anti-Patterns to Avoid

1. **Logging inside loops** - Creates log spam, use aggregated events
2. **Sensitive data in logs** - Never log passwords, tokens, PII
3. **console.log in production** - Use structured logger with levels
4. **Catching and re-throwing without context** - Add context before re-throw
5. **Log level abuse** - ERROR is for errors, not warnings
```

## Impact Level Usage

### CRITICAL - Will Break Things

```markdown
### Always Parallelize Independent Requests

**Impact: CRITICAL** - Can cause 2-10x latency improvement

Sequential requests are the most common performance issue in web applications.
```

### HIGH - Important Best Practice

```markdown
### Use Server Components for Static Content

**Impact: HIGH** - Reduces client bundle size significantly

Server Components render on the server and send HTML, eliminating the need to
ship React runtime code for static content.
```

### MEDIUM - Good Practice

```markdown
### Memoize Expensive Computations

**Impact: MEDIUM** - Prevents unnecessary re-computation

Use `useMemo` for computationally expensive operations that depend on specific
values.
```

### LOW - Nice to Have

```markdown
### Prefer Map/Set Over Object for Dynamic Keys

**Impact: LOW** - Minor performance benefit for large collections

Map and Set have O(1) lookup and avoid prototype pollution risks.
```

## Reference File Organization

### By Domain (Effect)

```
references/
├── service-patterns.md       # Effect.Service patterns
├── error-patterns.md         # Schema.TaggedError patterns
├── layer-patterns.md         # Layer composition
├── schema-patterns.md        # Schema and branded types
├── observability-patterns.md # Logging, metrics, config
└── anti-patterns.md          # All forbidden patterns
```

### By Impact Level (React)

```
rules/
├── async-parallel-requests.md        # CRITICAL
├── async-server-components.md        # CRITICAL
├── bundle-code-splitting.md          # CRITICAL
├── server-streaming.md               # HIGH
├── client-swr-config.md              # MEDIUM-HIGH
├── rerender-memo-callbacks.md        # MEDIUM
└── advanced-virtualization.md        # LOW
```

### By Concept (Logging)

```
references/
├── wide-events.md    # Core concept: one event per hop
├── context.md        # What context to include
├── structure.md      # Logger setup and middleware
└── pitfalls.md       # Common mistakes
```

## Cross-Reference Style

### Inline Reference

```markdown
For detailed documentation on error handling patterns, see
`references/error-patterns.md`.
```

### Index Section

```markdown
## Guidelines Reference

### Wide Events (`references/wide-events.md`)

- Emit one wide event per service hop
- Include all relevant context
- Connect events with request ID
- Emit at request completion in finally block

### Context Management (`references/context.md`)

- Use correlation IDs for tracing
- Avoid high-cardinality fields in metrics
- Include business context (user, tenant, operation)
```

## External Reference Style

```markdown
## External Resources

- [Effect Documentation](https://effect.website/docs)
- [Effect Best Practices](https://effect.website/docs/guides/best-practices)

---

Reference:
[Stripe Engineering - Canonical Log Lines](https://stripe.com/blog/canonical-log-lines)
```
