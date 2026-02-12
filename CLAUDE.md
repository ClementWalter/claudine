# Project Guidelines

## Scripts

- **Never use shell scripts (.sh)**. Always use Python scripts with `uv run`
- Use PEP 723 inline script metadata for dependencies:

```python
#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.11"
# dependencies = ["requests", "click"]
# ///
```

## Pre commit hooks

Project like have pre commit hooks. These are **CRITICAL**. Don't stop without
committing the changes because they don't pass. Don't evaluate the relevance of
these hooks, just fix them. using `prek run` run them without committing. Don't
disable linting rules that don't pass, fix errors.

## Code

When you write code, you should follow these rules:

- always explain the why in comment
- always add a module-level docstring
- never use print statements, always use proper logging frameworks.

## Testing

All code NEED to be unit and e2e tested. Always start by unit testing only the
code you write. **CRITICAL** don't run the full test suite immediately, but
first tests for the code you write.

**CRITICAL**: always respect 1 test = 1 assertion, no looping over fixtures
data. Test frameworks have built in tools for this:

- for python, use [pytest](https://docs.pytest.org/en/stable/index.html) with
  [pytest fixtures](https://docs.pytest.org/en/stable/explanation/fixtures.html)
  for hard coded data,
  [parametrize](https://docs.pytest.org/en/stable/how-to/parametrize.html) for
  fuzzing, etc.
- for rust, use [rstest](https://docs.rs/rstest/latest/rstest/) and macro to
  generate single tests for single data points.
- always run

**CRITICAL: Leverage test harnesses tools**:

- when running the full test suite, always start with previous failures only.
  Then when it passes, run the full test suite.
- Measure time to run the full test suite. If it's slow (several minutes), use
  parallelization
