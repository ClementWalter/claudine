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
