#!/usr/bin/env -S uv run --python 3.12
# /// script
# requires-python = ">=3.12"
# ///
"""Hook: PostToolUse:Skill - Append to marker file when a skill is invoked."""

import json
import sys
from datetime import datetime
from pathlib import Path


MARKER_FILE = Path.home() / ".claude" / ".pending-skill-learning.json"


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

    # Generate timestamp for unique filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # New skill entry
    new_entry = {
        "skill_name": skill_name,
        "skill_path_name": skill_path_name,
        "timestamp": timestamp,
        "learnings_path": f".claude/skills/{skill_path_name}/learnings/{timestamp}.md",
        "created_at": datetime.now().isoformat(),
    }

    # Load existing pending skills or start fresh
    MARKER_FILE.parent.mkdir(parents=True, exist_ok=True)
    pending_skills = []
    if MARKER_FILE.exists():
        try:
            content = json.loads(MARKER_FILE.read_text())
            # Handle both old format (single dict) and new format (list)
            if isinstance(content, list):
                pending_skills = content
            elif isinstance(content, dict):
                pending_skills = [content]
        except (json.JSONDecodeError, OSError):
            pending_skills = []

    # Append new skill (avoid duplicates by skill_name)
    existing_names = {s.get("skill_name") for s in pending_skills}
    if skill_name not in existing_names:
        pending_skills.append(new_entry)
        MARKER_FILE.write_text(json.dumps(pending_skills, indent=2))

    # Output minimal acknowledgment
    count = len(pending_skills)
    output = {
        "systemMessage": (
            f"Skill '{skill_name}' loaded ({count} skill(s) pending). "
            "Learning summary will be requested when you indicate the work is complete "
            "(e.g., 'looks good', 'done', 'ship it')."
        )
    }

    print(json.dumps(output))


if __name__ == "__main__":
    main()
