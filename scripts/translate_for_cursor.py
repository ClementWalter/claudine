#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml"]
# ///
"""
Translate skills (SKILL.md) to Cursor IDE rules (.mdc).

Usage:
    uv run scripts/translate_for_cursor.py --output ./.cursor/rules
    uv run scripts/translate_for_cursor.py --filter fhevm-developer,zama-developer
    uv run scripts/translate_for_cursor.py --dry-run
    uv run scripts/translate_for_cursor.py --check  # Verify files are up-to-date

Examples:
    # Translate all skills
    uv run scripts/translate_for_cursor.py

    # Only translate specific plugins
    uv run scripts/translate_for_cursor.py --filter fhevm-developer

    # Preview without writing files
    uv run scripts/translate_for_cursor.py --dry-run

    # Check if files need updating (for pre-commit)
    uv run scripts/translate_for_cursor.py --check
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import yaml


def find_skill_file(skill_dir: Path) -> Path | None:
    """Find the skill file in a directory (case-insensitive SKILL.md)."""
    # Check for SKILL.md or skill.md (case-insensitive)
    for name in ["SKILL.md", "skill.md", "Skill.md"]:
        path = skill_dir / name
        if path.exists():
            return path
    return None


def parse_skill_md(path: Path, skill_name_fallback: str | None = None) -> dict | None:
    """Extract YAML frontmatter and body from SKILL.md."""
    content = path.read_text(encoding="utf-8")

    # Determine fallback name from parent dir or filename
    if skill_name_fallback is None:
        # If it's a direct .md file in skills/, use the filename
        if path.parent.name == "skills":
            skill_name_fallback = path.stem
        else:
            skill_name_fallback = path.parent.name

    # Match YAML frontmatter between --- delimiters
    match = re.match(r"^---\n(.*?)\n---\n(.*)$", content, re.DOTALL)
    if not match:
        # No frontmatter - use directory name and full content as body
        print(
            f"  Warning: No frontmatter in {path} - using fallback name",
            file=sys.stderr,
        )
        # Try to extract first heading as name
        heading_match = re.match(r"^#\s+(.+)$", content, re.MULTILINE)
        name = (
            heading_match.group(1)
            if heading_match
            else skill_name_fallback.replace("-", " ").title()
        )
        return {
            "name": name,
            "description": f"This skill provides guidance for {name.lower()}",
            "version": None,
            "body": content.strip(),
            "path": path,
        }

    frontmatter_str, body = match.groups()

    try:
        frontmatter = yaml.safe_load(frontmatter_str)
        if frontmatter is None:
            frontmatter = {}
    except yaml.YAMLError:
        # YAML parse error - try manual extraction
        print(f"  Warning: YAML error in {path}, trying manual parse", file=sys.stderr)
        frontmatter = {}
        # Try to extract name manually
        name_match = re.search(r"^name:\s*(.+)$", frontmatter_str, re.MULTILINE)
        if name_match:
            frontmatter["name"] = name_match.group(1).strip()
        # Try to extract description (first line only to avoid colons)
        desc_match = re.search(r"^description:\s*(.+)$", frontmatter_str, re.MULTILINE)
        if desc_match:
            frontmatter["description"] = desc_match.group(1).strip()
        # Try to extract version
        ver_match = re.search(r"^version:\s*(.+)$", frontmatter_str, re.MULTILINE)
        if ver_match:
            frontmatter["version"] = ver_match.group(1).strip()

    # Handle description that might be a multi-line string
    description = frontmatter.get("description", f"Skill for {skill_name_fallback}")
    if isinstance(description, str):
        # Collapse multi-line descriptions to single line
        description = " ".join(description.split())

    return {
        "name": frontmatter.get("name", skill_name_fallback.replace("-", " ").title()),
        "description": description,
        "version": frontmatter.get("version"),
        "body": body.strip(),
        "path": path,
    }


def parse_reference_md(path: Path, skill_name: str, plugin_name: str) -> dict:
    """Parse a reference or agent markdown file."""
    content = path.read_text(encoding="utf-8")
    ref_name = path.stem  # e.g., "bug-hunter" from "bug-hunter.md"

    # Check for YAML frontmatter
    match = re.match(r"^---\n(.*?)\n---\n(.*)$", content, re.DOTALL)
    if match:
        frontmatter_str, body = match.groups()
        try:
            frontmatter = yaml.safe_load(frontmatter_str)
            description = frontmatter.get("description", "") if frontmatter else ""
        except yaml.YAMLError:
            description = ""
            body = content
    else:
        description = ""
        body = content

    # Generate description from filename if not present
    if not description:
        readable_name = ref_name.replace("-", " ").replace("_", " ")
        description = f"Detailed reference for {readable_name} ({skill_name} skill)"

    return {
        "name": ref_name,
        "skill_name": skill_name,
        "plugin_name": plugin_name,
        "description": description,
        "body": body.strip(),
        "path": path,
    }


def generate_mdc(
    skill_data: dict,
    plugin_name: str,
    examples: list[Path] | None = None,
    scripts: list[Path] | None = None,
    agents: list[Path] | None = None,
) -> str:
    """Generate .mdc file content from skill data."""
    lines = [
        "---",
        f"description: {skill_data['description']}",
        "alwaysApply: false",
        "---",
        "",
        f"# {skill_data['name']}",
        "",
    ]

    # Add version comment if present
    if skill_data.get("version"):
        lines.append(f"<!-- Version: {skill_data['version']} -->")
        lines.append("")

    # Add main body
    lines.append(skill_data["body"])

    # Inline examples if present
    if examples:
        lines.append("")
        lines.append("---")
        lines.append("")
        lines.append("## Examples")
        lines.append("")
        for example_path in examples:
            example_content = example_path.read_text(encoding="utf-8").strip()
            example_name = example_path.stem.replace("-", " ").replace("_", " ").title()
            lines.append(f"### {example_name}")
            lines.append("")
            lines.append(example_content)
            lines.append("")

    # Document agents if present
    if agents:
        lines.append("")
        lines.append("---")
        lines.append("")
        lines.append("## Specialized Agents")
        lines.append("")
        lines.append("The following agent prompts are available for specialized tasks:")
        lines.append("")
        for agent_path in agents:
            agent_name = agent_path.stem.replace("-", " ").replace("_", " ").title()
            # Try to get first line description from the file
            agent_content = agent_path.read_text(encoding="utf-8")
            # Look for first heading or first paragraph
            heading_match = re.search(r"^#\s+(.+)$", agent_content, re.MULTILINE)
            if heading_match:
                agent_desc = heading_match.group(1)
            else:
                # Use first non-empty line
                first_lines = [
                    line.strip() for line in agent_content.split("\n") if line.strip()
                ]
                agent_desc = first_lines[0][:80] if first_lines else "Agent prompt"
            lines.append(f"- **{agent_name}**: {agent_desc}")
        lines.append("")

    # Document scripts if present
    if scripts:
        lines.append("")
        lines.append("---")
        lines.append("")
        lines.append("## Available Scripts")
        lines.append("")
        lines.append(
            "The following scripts are available in the marketplace but cannot be executed from Cursor rules:"
        )
        lines.append("")
        for script_path in scripts:
            script_name = script_path.name
            # Read first docstring if present
            script_content = script_path.read_text(encoding="utf-8")
            docstring_match = re.search(r'"""(.*?)"""', script_content, re.DOTALL)
            if docstring_match:
                docstring = (
                    docstring_match.group(1).strip().split("\n")[0]
                )  # First line only
            else:
                docstring = "No description available"
            lines.append(f"- `{script_name}`: {docstring}")
        lines.append("")
        lines.append(
            "To use these scripts, run them via `uv run` from the marketplace directory."
        )

    return "\n".join(lines)


def generate_reference_mdc(ref_data: dict, ref_type: str = "reference") -> str:
    """Generate .mdc file content for a reference or agent document."""
    lines = [
        "---",
        f"description: {ref_data['description']}",
        "alwaysApply: false",
        "---",
        "",
        f"# {ref_data['name'].replace('-', ' ').replace('_', ' ').title()}",
        "",
        f"_{ref_type.title()} for {ref_data['skill_name']} skill ({ref_data['plugin_name']} plugin)_",
        "",
        ref_data["body"],
    ]
    return "\n".join(lines)


def to_kebab_case(name: str) -> str:
    """Convert a name to kebab-case."""
    # Replace & with "and"
    name = name.replace("&", "and")
    # Replace underscores and spaces with hyphens
    name = re.sub(r"[_\s]+", "-", name)
    # Remove any non-alphanumeric characters except hyphens
    name = re.sub(r"[^a-zA-Z0-9-]", "", name)
    # Insert hyphen before uppercase letters and lowercase them
    name = re.sub(r"([a-z])([A-Z])", r"\1-\2", name)
    # Collapse multiple hyphens
    name = re.sub(r"-+", "-", name)
    return name.lower().strip("-")


def file_needs_update(path: Path, new_content: str) -> bool:
    """Check if file doesn't exist or has different content."""
    if not path.exists():
        return True
    try:
        existing = path.read_text(encoding="utf-8")
        return existing != new_content
    except (OSError, UnicodeDecodeError):
        return True


def translate_skill_dir(
    skill_dir: Path,
    plugin_name: str,
    output_dir: Path,
    dry_run: bool = False,
    check: bool = False,
) -> tuple[list[Path], list[Path]]:
    """Translate a single skill directory to .mdc files.

    Returns:
        Tuple of (generated_files, outdated_files).
        In check mode, outdated_files contains files that need updating.
    """
    skill_md = find_skill_file(skill_dir)
    if not skill_md:
        return [], []

    skill_data = parse_skill_md(skill_md)
    if not skill_data:
        return [], []

    skill_name = to_kebab_case(skill_data["name"])
    plugin_kebab = to_kebab_case(plugin_name)
    output_files = []
    outdated_files = []

    # Find examples, scripts, references, and agents
    examples_dir = skill_dir / "examples"
    scripts_dir = skill_dir / "scripts"
    refs_dir = skill_dir / "references"
    agents_dir = skill_dir / "agents"

    examples = list(examples_dir.glob("*.md")) if examples_dir.exists() else []
    scripts = list(scripts_dir.glob("*.py")) if scripts_dir.exists() else []
    agents = list(agents_dir.glob("*.md")) if agents_dir.exists() else []

    # Generate main skill .mdc
    mdc_content = generate_mdc(skill_data, plugin_name, examples, scripts, agents)
    mdc_filename = f"{plugin_kebab}-{skill_name}.mdc"
    mdc_path = output_dir / mdc_filename

    if check:
        if file_needs_update(mdc_path, mdc_content):
            print(f"  ✗ {mdc_filename} (needs update)")
            outdated_files.append(mdc_path)
        else:
            print(f"  ✓ {mdc_filename}")
    else:
        print(f"  → {mdc_filename}")
        if not dry_run:
            mdc_path.write_text(mdc_content, encoding="utf-8")
    output_files.append(mdc_path)

    # Generate separate .mdc for each reference
    if refs_dir.exists():
        for ref_path in refs_dir.glob("*.md"):
            ref_data = parse_reference_md(ref_path, skill_data["name"], plugin_name)
            ref_mdc_content = generate_reference_mdc(ref_data, "reference")
            ref_name = to_kebab_case(ref_data["name"])
            ref_mdc_filename = f"{plugin_kebab}-{skill_name}--{ref_name}.mdc"
            ref_mdc_path = output_dir / ref_mdc_filename

            if check:
                if file_needs_update(ref_mdc_path, ref_mdc_content):
                    print(f"  ✗ {ref_mdc_filename} (needs update)")
                    outdated_files.append(ref_mdc_path)
                else:
                    print(f"  ✓ {ref_mdc_filename}")
            else:
                print(f"  → {ref_mdc_filename}")
                if not dry_run:
                    ref_mdc_path.write_text(ref_mdc_content, encoding="utf-8")
            output_files.append(ref_mdc_path)

    # Generate separate .mdc for each agent
    if agents_dir.exists():
        for agent_path in agents_dir.glob("*.md"):
            agent_data = parse_reference_md(agent_path, skill_data["name"], plugin_name)
            agent_mdc_content = generate_reference_mdc(agent_data, "agent")
            agent_name = to_kebab_case(agent_data["name"])
            agent_mdc_filename = f"{plugin_kebab}-{skill_name}--agent-{agent_name}.mdc"
            agent_mdc_path = output_dir / agent_mdc_filename

            if check:
                if file_needs_update(agent_mdc_path, agent_mdc_content):
                    print(f"  ✗ {agent_mdc_filename} (needs update)")
                    outdated_files.append(agent_mdc_path)
                else:
                    print(f"  ✓ {agent_mdc_filename}")
            else:
                print(f"  → {agent_mdc_filename}")
                if not dry_run:
                    agent_mdc_path.write_text(agent_mdc_content, encoding="utf-8")
            output_files.append(agent_mdc_path)

    return output_files, outdated_files


def translate_skill_file(
    skill_file: Path,
    plugin_name: str,
    output_dir: Path,
    dry_run: bool = False,
    check: bool = False,
) -> tuple[list[Path], list[Path]]:
    """Translate a direct skill .md file (not in a subdirectory) to .mdc.

    Returns:
        Tuple of (generated_files, outdated_files).
    """
    skill_data = parse_skill_md(skill_file)
    if not skill_data:
        return [], []

    skill_name = to_kebab_case(skill_data["name"])
    plugin_kebab = to_kebab_case(plugin_name)
    outdated_files = []

    # Generate main skill .mdc
    mdc_content = generate_mdc(skill_data, plugin_name)
    mdc_filename = f"{plugin_kebab}-{skill_name}.mdc"
    mdc_path = output_dir / mdc_filename

    if check:
        if file_needs_update(mdc_path, mdc_content):
            print(f"  ✗ {mdc_filename} (needs update)")
            outdated_files.append(mdc_path)
        else:
            print(f"  ✓ {mdc_filename}")
    else:
        print(f"  → {mdc_filename}")
        if not dry_run:
            mdc_path.write_text(mdc_content, encoding="utf-8")

    return [mdc_path], outdated_files


def translate_all(
    marketplace_path: Path,
    output_dir: Path,
    plugin_filter: list[str] | None = None,
    dry_run: bool = False,
    check: bool = False,
) -> tuple[list[Path], list[Path]]:
    """Walk marketplace and translate all skills.

    Returns:
        Tuple of (generated_files, outdated_files).
    """
    output_files = []
    all_outdated = []

    # Look in the plugins/ subdirectory
    plugins_dir = marketplace_path / "plugins"
    if not plugins_dir.exists():
        print(f"Error: plugins/ directory not found at {plugins_dir}", file=sys.stderr)
        return output_files, all_outdated

    # Find all plugin directories (those with .claude-plugin/plugin.json)
    for plugin_dir in plugins_dir.iterdir():
        if not plugin_dir.is_dir():
            continue
        if plugin_dir.name.startswith("."):
            continue

        plugin_json = plugin_dir / ".claude-plugin" / "plugin.json"
        if not plugin_json.exists():
            continue

        plugin_name = plugin_dir.name

        # Apply filter if specified
        if plugin_filter and plugin_name not in plugin_filter:
            continue

        print(f"Plugin: {plugin_name}")

        # Find skills directory
        skills_dir = plugin_dir / "skills"
        if not skills_dir.exists():
            print("  (no skills directory)")
            continue

        for entry in skills_dir.iterdir():
            if entry.is_dir():
                # Skill in subdirectory (e.g., skills/pr-review/SKILL.md)
                files, outdated = translate_skill_dir(
                    entry, plugin_name, output_dir, dry_run, check
                )
                output_files.extend(files)
                all_outdated.extend(outdated)
            elif entry.is_file() and entry.suffix == ".md":
                # Direct skill file (e.g., skills/fhevm-developer.md)
                files, outdated = translate_skill_file(
                    entry, plugin_name, output_dir, dry_run, check
                )
                output_files.extend(files)
                all_outdated.extend(outdated)

    return output_files, all_outdated


def main():
    parser = argparse.ArgumentParser(
        description="Translate skills to Cursor .mdc rules",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--marketplace",
        type=Path,
        default=Path(__file__).parent.parent,
        help="Path to marketplace root (default: parent of scripts/)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).parent.parent / ".cursor" / "rules",
        help="Output directory for .mdc files (default: ./.cursor/rules)",
    )
    parser.add_argument(
        "--filter",
        type=str,
        help="Comma-separated list of plugins to translate (default: all)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview without writing files",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Check if files are up-to-date (exit 1 if not)",
    )

    args = parser.parse_args()

    marketplace_path = args.marketplace.resolve()
    output_dir = args.output.resolve()
    plugin_filter = args.filter.split(",") if args.filter else None

    print(f"Marketplace: {marketplace_path}")
    print(f"Output: {output_dir}")
    if plugin_filter:
        print(f"Filter: {plugin_filter}")
    if args.dry_run:
        print("DRY RUN - no files will be written")
    if args.check:
        print("CHECK MODE - verifying files are up-to-date")
    print()

    # Create output directory (not in check mode)
    if not args.dry_run and not args.check:
        output_dir.mkdir(parents=True, exist_ok=True)

    # Translate all skills
    output_files, outdated_files = translate_all(
        marketplace_path,
        output_dir,
        plugin_filter,
        args.dry_run,
        args.check,
    )

    print()

    if args.check:
        if outdated_files:
            print(f"✗ {len(outdated_files)} files need updating:")
            for f in outdated_files:
                print(f"  - {f.name}")
            print()
            print("Run without --check to regenerate files:")
            print("  uv run scripts/translate_for_cursor.py")
            sys.exit(1)
        else:
            print(f"✓ All {len(output_files)} .mdc files are up-to-date")
            sys.exit(0)
    else:
        print(f"Generated {len(output_files)} .mdc files")
        if args.dry_run:
            print()
            print("Run without --dry-run to write files")


if __name__ == "__main__":
    main()
