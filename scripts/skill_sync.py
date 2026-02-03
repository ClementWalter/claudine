#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.11"
# dependencies = ["click"]
# ///
"""
Sync Claude/Codex skills by creating symlinks from a source .claude folder.

Usage:
    uv run scripts/skill_sync.py
    uv run scripts/skill_sync.py --source ~/.claude
    uv run scripts/skill_sync.py --force
    uv run scripts/skill_sync.py --dry-run

Examples:
    # Sync skills to current directory
    cd ~/my-project && skill-sync

    # Force overwrite existing symlinks
    skill-sync --force

    # Preview what would be done
    skill-sync --dry-run
"""

from __future__ import annotations

import sys
from pathlib import Path

import click

DEFAULT_SOURCE = Path.home() / "Documents" / "claudine" / ".claude"
TARGET_FOLDERS = [".claude", ".codex"]


def create_symlink(
    source_item: Path,
    target_item: Path,
    force: bool,
    dry_run: bool,
) -> str | None:
    """Create a symlink from target_item to source_item.

    Returns a status message or None if skipped.
    """
    if target_item.exists() or target_item.is_symlink():
        if target_item.is_symlink():
            current_target = target_item.resolve()
            if current_target == source_item.resolve():
                return f"  [skip] {target_item.name} (already linked)"
            if force:
                if not dry_run:
                    target_item.unlink()
                return f"  [update] {target_item.name} -> {source_item}"
            return f"  [skip] {target_item.name} (exists, use --force to overwrite)"
        else:
            if force:
                if not dry_run:
                    if target_item.is_dir():
                        import shutil

                        shutil.rmtree(target_item)
                    else:
                        target_item.unlink()
                return f"  [replace] {target_item.name} -> {source_item}"
            return f"  [skip] {target_item.name} (exists as real file/dir, use --force)"

    if not dry_run:
        target_item.symlink_to(source_item)
    return f"  [link] {target_item.name} -> {source_item}"


@click.command()
@click.option(
    "--source",
    type=click.Path(exists=True, path_type=Path),
    default=DEFAULT_SOURCE,
    help=f"Source .claude folder (default: {DEFAULT_SOURCE})",
)
@click.option(
    "--target",
    type=click.Path(path_type=Path),
    default=Path.cwd(),
    help="Target directory (default: current working directory)",
)
@click.option(
    "--force",
    is_flag=True,
    help="Overwrite existing symlinks",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Show what would be done without making changes",
)
def main(source: Path, target: Path, force: bool, dry_run: bool) -> None:
    """Sync Claude/Codex skills by creating symlinks."""
    source = source.expanduser().resolve()
    target = target.expanduser().resolve()

    if not source.exists():
        click.echo(f"Error: Source folder does not exist: {source}", err=True)
        sys.exit(1)

    if dry_run:
        click.echo("[DRY RUN] No changes will be made\n")

    click.echo(f"Source: {source}")
    click.echo(f"Target: {target}\n")

    # Get items to symlink from source
    source_items = sorted(source.iterdir())
    if not source_items:
        click.echo("No items found in source folder")
        return

    for folder_name in TARGET_FOLDERS:
        target_folder = target / folder_name
        click.echo(f"Syncing to {target_folder}/")

        # Create target folder if needed
        if not target_folder.exists():
            if not dry_run:
                target_folder.mkdir(parents=True)
            click.echo(f"  [create] {folder_name}/")

        # Create symlinks for each item
        for source_item in source_items:
            target_item = target_folder / source_item.name
            message = create_symlink(source_item, target_item, force, dry_run)
            if message:
                click.echo(message)

        click.echo()

    click.echo("Done!")


if __name__ == "__main__":
    main()
