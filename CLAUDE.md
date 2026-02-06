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
