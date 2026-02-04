#!/usr/bin/env -S uv run --python 3.12
# /// script
# requires-python = ">=3.12"
# ///
"""Hook: UserPromptSubmit - Check for magic phrases to trigger learning summaries."""

import json
import re
import sys
from pathlib import Path


MARKER_FILE = Path.home() / ".claude" / ".pending-skill-learning.json"

# Magic phrases that indicate the user is satisfied (case-insensitive)
MAGIC_PHRASES = [
    r"\blooks?\s+good\b",
    r"\bdone\b",
    r"\bship\s+it\b",
    r"\blgtm\b",
    r"\bperfect\b",
    r"\bgreat\b",
    r"\bawesome\b",
    r"\ball\s+good\b",
    r"\bwe'?re\s+done\b",
    r"\bthat'?s\s+it\b",
    r"\bfinished\b",
    r"\bcomplete\b",
    r"\bapproved\b",
]


def contains_magic_phrase(text: str) -> bool:
    """Check if text contains any magic phrase."""
    text_lower = text.lower()
    return any(re.search(pattern, text_lower) for pattern in MAGIC_PHRASES)


def main() -> None:
    # Read JSON input from stdin
    try:
        data = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    # Check if marker file exists
    if not MARKER_FILE.exists():
        # No pending skill learning, nothing to do
        print(json.dumps({}))
        return

    # Get user's message (field is "prompt" per Claude Code docs)
    user_message = data.get("prompt", "")

    if not user_message:
        print(json.dumps({}))
        return

    # Check for magic phrases
    if not contains_magic_phrase(user_message):
        # No magic phrase, nothing to do
        print(json.dumps({}))
        return

    # Magic phrase detected! Read marker and trigger learning summaries
    try:
        content = json.loads(MARKER_FILE.read_text())
        # Handle both old format (single dict) and new format (list)
        if isinstance(content, dict):
            pending_skills = [content]
        elif isinstance(content, list):
            pending_skills = content
        else:
            pending_skills = []
    except (json.JSONDecodeError, OSError):
        print(json.dumps({}))
        return

    if not pending_skills:
        print(json.dumps({}))
        return

    # Delete the marker file (one-time trigger)
    MARKER_FILE.unlink(missing_ok=True)

    # Build instruction for all pending skills
    skill_names = [s.get("skill_name", "unknown") for s in pending_skills]
    skills_list = ", ".join(f"'{name}'" for name in skill_names)

    learnings_instructions = []
    for skill in pending_skills:
        path = skill.get("learnings_path", "")
        name = skill.get("skill_name", "unknown")
        learnings_instructions.append(f"- '{name}' -> {path}")

    learnings_paths = "\n".join(learnings_instructions)

    # Output instruction to create learning summaries
    output = {
        "systemMessage": (
            f"The user has indicated satisfaction. {len(pending_skills)} skill(s) pending: {skills_list}.\n\n"
            f"NOW CREATE LEARNING SUMMARIES for each skill:\n{learnings_paths}\n\n"
            "For EACH skill, create the learnings directory if needed, then write a file with this format:\n\n"
            "```markdown\n"
            "# Learning: [Brief title of what was learned]\n\n"
            "## DO\n"
            "- [Specific actionable advice to follow]\n"
            "- [Another do item]\n\n"
            "## DON'T\n"
            "- [Specific pitfalls to avoid]\n"
            "- [Another don't item]\n\n"
            "## Context\n"
            "[Brief explanation of the situation and what led to these learnings]\n"
            "```\n\n"
            "Base each learning on what was accomplished with that specific skill."
        )
    }

    print(json.dumps(output))


if __name__ == "__main__":
    main()
