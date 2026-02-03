# Issue Template

Standard format for issues in Zama repositories using the Why/What/How
structure.

---

## Format Overview

Every issue should answer three questions:

| Section | Purpose                  | Required |
| ------- | ------------------------ | -------- |
| Why     | Problem and motivation   | Yes      |
| What    | Desired outcome          | Yes      |
| How     | Approach and constraints | Optional |

---

## Why (Required)

Context and motivation. This section should answer:

- What problem exists today?
- Why does it matter?
- What's the impact of not addressing it?

**Good Why**:

> gRPC calls to KMS Core occasionally fail with transient errors (network
> timeouts, service unavailable). Currently these failures cause the entire
> operation to fail, requiring manual intervention and leaving users waiting.

**Bad Why**:

> We need retry logic.

---

## What (Required)

Desired outcome and expected behavior. This section should answer:

- What should happen after this is implemented?
- What's the expected behavior?
- What are the acceptance criteria?

**Good What**:

> Implement automatic retry with exponential backoff for recoverable gRPC
> errors. After N retries, mark the operation as failed and continue processing
> other requests. Users should see faster recovery from transient failures.

**Bad What**:

> Add retries to the code.

---

## How (Optional)

Approach, constraints, or implementation guidance. Include when:

- There's a preferred solution approach
- There are technical constraints to consider
- Specific requirements or dependencies exist

Format as **concise bullet points**:

**Good How**:

- Use the existing `RETRYABLE_GRPC_CODE` list for error classification
- Accumulate error count in DB across retries (persist across restarts)
- Apply different thresholds: 200 for decryptions, unlimited for key management
- Log each retry attempt with error details

**Bad How**:

> I think we should probably use some kind of retry mechanism, maybe with
> backoff, and we need to make sure it works with the database somehow.

---

## Complete Example

**Title**: Add retry logic for gRPC calls

**Body**:

```markdown
## Why

gRPC calls to KMS Core occasionally fail with transient errors (network
timeouts, service unavailable). Currently these failures cause the entire
operation to fail, requiring manual intervention and blocking the processing
queue.

## What

Implement automatic retry with exponential backoff for recoverable gRPC errors.
After reaching the retry limit, mark the operation as failed and continue
processing other requests. The system should self-heal from transient network
issues.

## How

- Use existing `RETRYABLE_GRPC_CODE` list: Unavailable, ResourceExhausted,
  Aborted, Unknown
- Persist error count in DB to survive worker restarts
- Decryption requests: max 200 attempts, then delete
- Key management requests: unlimited retries (critical, prefer human
  intervention)
- Treat `AlreadyExists` as success (idempotent operation completed earlier)
```

---

## Anti-patterns

### Don't copy raw interview answers

**Bad**:

> Why: "Because the thing keeps breaking and it's annoying" What: "Make it not
> break" How: "IDK, fix it somehow"

**Good**: Synthesize into professional, actionable content.

### Don't be too verbose

Keep each section focused. If How is getting long, the issue might need to be
split.

### Don't skip Why

Even "obvious" changes benefit from context. Future readers (including yourself)
will appreciate understanding the motivation.

---

## Title Guidelines

- **Concise**: Max 72 characters
- **Action-oriented**: Start with verb (Add, Fix, Update, Remove, Refactor)
- **Specific**: What component or feature?

**Good titles**:

- Add retry logic for gRPC calls
- Fix block number comparison in migrations
- Update KMS Core to v0.14.0
- Remove deprecated encryption endpoint

**Bad titles**:

- Bug fix
- Update
- Issue with the thing
- WIP
