# Pull Request Template

Standard format for PR descriptions in Zama repositories.

---

## Minimal Template

For straightforward changes:

```markdown
<summary in 1-3 sentences>

Closes #<issue-number>
```

**Example**:

```markdown
Add retry logic for gRPC calls to handle transient KMS failures.

Closes #42
```

---

## Standard Template

For changes that need more context:

```markdown
## Summary

<1-3 sentences explaining what this PR does and why>

## Changes

- <key change 1>
- <key change 2>
- <key change 3>

Closes #<issue-number>
```

**Example**:

```markdown
## Summary

Add error counter to track retry attempts across worker restarts. The counter is
persisted in PostgreSQL and accumulates across send and poll phases.

## Changes

- Add `error_counter` column to requests table
- Update migration with `IF NOT EXISTS` for idempotency
- Accumulate errors across gRPC send and poll phases
- Delete decryption requests after max attempts reached

Closes #42
```

---

## Multiple Issues

When a PR closes multiple issues, list each on its own line:

```markdown
## Summary

Refactor error handling across all KMS services to use ProcessingError enum.

Closes #42 Closes #43 Closes #44
```

---

## GitHub Close Keywords

These keywords auto-close the linked issue when the PR is merged:

| Keyword    | Example        |
| ---------- | -------------- |
| `Closes`   | `Closes #42`   |
| `Fixes`    | `Fixes #42`    |
| `Resolves` | `Resolves #42` |

**Always use `Closes`** for consistency across Zama repos.

---

## What NOT to Include

- **Long explanations**: Keep it concise
- **Implementation details**: The code shows how
- **Future work**: Create separate issues
- **Screenshots**: Unless UI changes (rare for backend)

---

## PR Title

PR titles **must follow conventional commit format** and are validated by
commitlint. See [`commitlint.config.ts`](./commitlint.config.ts) and
[commit-conventions.md](./commit-conventions.md) for the full specification.

### Format

```text
<type>(<scope>): <description>
```

### Requirements

- **Type**: Required - one of: `feat`, `fix`, `chore`, `docs`, `test`,
  `refactor`, `ci`, `style`, `perf`, `revert`, `ticket`
- **Scope**: Required - one of: `coprocessor`, `host-contracts`,
  `gateway-contracts`, `contracts`, `library-solidity`, `kms-connector`, `sdk`,
  `test-suite`, `charts`, `common`
- **Description**: Imperative mood ("add" not "added"), max 50 characters

**Good**:

- `feat(kms-connector): add retry logic for gRPC calls`
- `fix(coprocessor): handle block number comparison`
- `chore(common): update KMS Core to v0.14.0`

**Bad**:

- `Fixed stuff` - missing type/scope, past tense, vague
- `feat: add feature` - missing scope
- `feat(kms): add retry` - invalid scope (use `kms-connector`)
- `WIP: trying to add feature` - invalid type

---

## Checklist (Optional)

For complex PRs, include a checklist in the description:

```markdown
## Summary

Add AWS KMS signing support for transaction sender.

## Checklist

- [x] Add AWS KMS client
- [x] Update Helm chart with new config
- [x] Add integration tests
- [ ] Update documentation

Closes #42
```
