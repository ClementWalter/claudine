# Commit Message Conventions

Conventional Commits format for Zama repositories.

> **Note:** These conventions are enforced by commitlint. See
> [`commitlint.config.ts`](./commitlint.config.ts) for the machine-readable
> configuration.

---

## Format

```text
<type>(<scope>): <description>

[optional body]

[optional footer]
```

### Type (Required)

Types are enforced by commitlint. Use one of:

| Type       | When to Use                      | Example                                |
| ---------- | -------------------------------- | -------------------------------------- |
| `feat`     | New feature or capability        | `feat(sdk): add retry logic`           |
| `fix`      | Bug fix                          | `fix(coprocessor): handle null`        |
| `chore`    | Maintenance, deps, tooling       | `chore(common): bump dependencies`     |
| `docs`     | Documentation only               | `docs(sdk): update API reference`      |
| `test`     | Adding or fixing tests           | `test(kms-connector): add retry tests` |
| `refactor` | Code change (no feature or fix)  | `refactor(sdk): extract helper`        |
| `ci`       | CI/CD configuration              | `ci: add lint step to workflow`        |
| `style`    | Formatting, whitespace (no code) | `style(contracts): fix indentation`    |
| `perf`     | Performance improvement          | `perf(coprocessor): optimize batching` |
| `revert`   | Revert a previous commit         | `revert(sdk): undo breaking change`    |
| `ticket`   | Ticket/issue reference           | `ticket(common): FHEVM-123`            |

### Scope (Required)

Scope is enforced by commitlint. Use one of these values:

| Scope               | Component                  |
| ------------------- | -------------------------- |
| `coprocessor`       | Coprocessor service        |
| `host-contracts`    | Host chain smart contracts |
| `gateway-contracts` | Gateway smart contracts    |
| `contracts`         | General contract changes   |
| `library-solidity`  | Solidity library code      |
| `kms-connector`     | KMS Connector service      |
| `sdk`               | SDK and client libraries   |
| `test-suite`        | Test infrastructure        |
| `charts`            | Helm charts and deployment |
| `common`            | Shared/common code         |

### Description (Required)

- **Max 50 characters** (aim for shorter)
- **Imperative mood**: "add" not "added" or "adds"
- **No period** at the end
- **Lowercase** start

---

## Examples

### Good

```text
feat(kms-connector): add error counter for retry tracking
fix(coprocessor): use BIGINT for block numbers
chore(common): bump dependencies
docs(sdk): update deployment guide
test(test-suite): add retry limit tests
refactor(contracts): extract signing logic
ci(charts): add sqlx prepare check
```

### Bad

```text
Added new feature              # Past tense, vague, missing type/scope
fix: Fixed the bug.            # Missing scope, past tense, period
FEAT: Add feature              # Uppercase type, missing scope
feat(kms): add retry           # Invalid scope (use kms-connector)
feat(worker): added logic      # Invalid scope, past tense
```

---

## Breaking Changes

For breaking changes, add `!` after type/scope:

```text
feat(sdk)!: change response format
```

Or add `BREAKING CHANGE:` in the footer:

```text
feat(sdk): change response format

BREAKING CHANGE: response now uses JSON instead of protobuf
```

---

## Multi-line Messages

For complex changes, add a body after a blank line:

```text
fix(kms-connector): handle subscription failures gracefully

Previously, if any subscription failed, the listener would hang.
Now it exits immediately on first failure to allow orchestrator restart.

Refs: #123
```

---

## Commit Atomicity

Each commit should be:

1. **Self-contained**: Builds and tests pass
2. **Focused**: One logical change
3. **Reviewable**: Can be understood in isolation

**Split commits when**:

- Changes affect unrelated components
- You're mixing refactoring with features
- Tests and implementation are separable

**Combine when**:

- Changes are tightly coupled
- Splitting would break the build
