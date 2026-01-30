#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.11"
# ///
"""Hook: After a skill is used, prompt Claude to create a learning summary."""

import json
import sys
from datetime import datetime


def main() -> None:
    # Read JSON input from stdin
    try:
        data = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    # Extract skill name from tool_input
    tool_input = data.get("tool_input", {})
    skill_name = tool_input.get("skill")

    if not skill_name:
        sys.exit(0)

    # Handle namespaced skills (e.g., "ms-office-suite:pdf" -> "pdf")
    skill_path_name = skill_name.split(":")[-1]

    # Determine the learnings folder path relative to project
    learnings_dir = f".claude/skills/{skill_path_name}/learnings"

    # Generate timestamp for unique filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Output JSON with additionalContext to prompt Claude
    output = {
        "hookSpecificOutput": {
            "additionalContext": (
                f"IMPORTANT: A skill was just used. Please create a learning summary file at "
                f"'{learnings_dir}/{timestamp}.md' with the following format:\n\n"
                "# Learning: [Brief title of what was learned]\n\n"
                "## DO\n"
                "- [Specific actionable advice to follow]\n"
                "- [Another do item]\n\n"
                "## DON'T\n"
                "- [Specific pitfalls to avoid]\n"
                "- [Another don't item]\n\n"
                "## Context\n"
                "[Brief explanation of the situation that led to this learning]\n\n"
                "First create the learnings directory if it doesn't exist, then write the learning file. "
                "Base the content on what was just discussed/accomplished with the skill."
            )
        }
    }

    print(json.dumps(output))


if __name__ == "__main__":
    main()
