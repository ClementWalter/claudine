#!/usr/bin/env -S uv run --python 3.12
# /// script
# requires-python = ">=3.12"
# ///
"""Hook: SessionEnd - Clean up any pending skill learning markers."""

import json
import sys
from pathlib import Path


MARKER_FILE = Path.home() / ".claude" / ".pending-skill-learning.json"


def main() -> None:
    # Read JSON input from stdin (required even if not used)
    try:
        json.load(sys.stdin)
    except json.JSONDecodeError:
        pass

    # Check if marker file exists
    if not MARKER_FILE.exists():
        print(json.dumps({}))
        return

    # Read pending skills for logging
    try:
        content = json.loads(MARKER_FILE.read_text())
        if isinstance(content, list):
            pending_skills = content
        elif isinstance(content, dict):
            pending_skills = [content]
        else:
            pending_skills = []
    except (json.JSONDecodeError, OSError):
        pending_skills = []

    # Delete the marker file
    MARKER_FILE.unlink(missing_ok=True)

    # Output message if there were pending skills
    if pending_skills:
        skill_names = [s.get("skill_name", "unknown") for s in pending_skills]
        output = {
            "systemMessage": (
                f"Session ended with {len(pending_skills)} pending skill learning(s) "
                f"({', '.join(skill_names)}). Marker file cleaned up."
            )
        }
    else:
        output = {}

    print(json.dumps(output))


if __name__ == "__main__":
    main()
