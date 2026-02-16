#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.11"
# dependencies = ["click"]
# ///
"""
Add a Git repo as a submodule under external/ and symlink skill folders into .claude/skills.

Accepts one Git URL, adds it as external/<repo-name>, then creates symlinks in
.claude/skills/ for each immediate subdirectory that contains a SKILL.md file.
Fails on any path collision (existing submodule path or existing skill target).

Can be run from any working directory. Default repo root is the repo that contains
this script; set CLAUDINE_REPO or use --repo-root to target a different repo.
"""

from __future__ import annotations

import logging
import os
import subprocess
import sys
from pathlib import Path

import click

SKILL_FILENAME = "SKILL.md"
EXTERNAL_DIR = "external"
SKILLS_DIR = ".claude/skills"
ENV_REPO_ROOT = "CLAUDINE_REPO"

logger = logging.getLogger(__name__)


def _default_repo_root() -> Path:
    """Repo root: CLAUDINE_REPO if set, else the repo that contains this script."""
    env = os.environ.get(ENV_REPO_ROOT, "").strip()
    if env:
        return Path(env).expanduser()
    # Script lives at <repo>/scripts/add_skill_repo_submodule.py -> repo is parent of scripts/
    return Path(__file__).resolve().parent.parent


def repo_name_from_url(url: str) -> str | None:
    """Derive repo name from a Git URL by taking the last path segment and stripping .git."""
    if not url or not url.strip():
        return None
    url = url.strip()
    # Normalize: remove .git suffix and trailing slash, then take last segment
    base = url.rstrip("/").removesuffix(".git")
    if not base:
        return None
    # Last path segment (handles both git@host:org/repo and https://host/org/repo)
    last = base.split("/")[-1] if "/" in base else base
    # git@host:repo (no slash) -> use as-is
    if ":" in last:
        last = last.split(":")[-1]
    # Must be a valid directory name (non-empty, no path separators)
    if not last or "/" in last or "\\" in last:
        return None
    return last


def skill_folders_under(root: Path) -> list[Path]:
    """Return immediate child directories of root that contain SKILL.md."""
    if not root.is_dir():
        return []
    out = []
    for p in root.iterdir():
        if p.is_dir() and (p / SKILL_FILENAME).is_file():
            out.append(p)
    return sorted(out, key=lambda x: x.name)


def add_submodule(repo_root: Path, url: str, submodule_path: Path) -> None:
    """Run git submodule add; raises CalledProcessError on failure."""
    subprocess.run(
        ["git", "submodule", "add", url, str(submodule_path)],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
    )


def ensure_dir(path: Path) -> None:
    """Create directory and parents if they do not exist."""
    path.mkdir(parents=True, exist_ok=True)


def run(
    repo_root: Path,
    url: str,
    external_dir: Path,
    skills_dir: Path,
) -> None:
    """
    Add submodule at external/<repo_name> and symlink skill folders into .claude/skills.
    Fails on first collision or invalid state.
    """
    name = repo_name_from_url(url)
    if not name:
        logger.error("Invalid or empty Git URL: could not derive repo name")
        sys.exit(1)

    submodule_path = external_dir / name
    if submodule_path.exists() or submodule_path.is_symlink():
        logger.error("Submodule path already exists: %s", submodule_path)
        sys.exit(1)

    ensure_dir(external_dir)
    logger.info("Adding submodule %s at %s", url, submodule_path)
    try:
        add_submodule(repo_root, url, submodule_path)
    except subprocess.CalledProcessError as e:
        logger.error("git submodule add failed: %s", e.stderr or e)
        sys.exit(1)

    skills_root = skills_dir
    ensure_dir(skills_root)

    folders = skill_folders_under(submodule_path)
    if not folders:
        logger.info("No subdirectories with %s found; no symlinks created", SKILL_FILENAME)
        return

    # Resolve once for relative symlink target from .claude/skills/<name>
    try:
        submodule_resolved = submodule_path.resolve()
    except OSError as e:
        logger.error("Cannot resolve submodule path: %s", e)
        sys.exit(1)

    for folder in folders:
        link_path = skills_root / folder.name
        if link_path.exists() or link_path.is_symlink():
            logger.error("Skill target already exists: %s", link_path)
            sys.exit(1)
        target = submodule_resolved / folder.name
        # Use relative path so symlinks work when repo is moved
        try:
            rel = Path(os.path.relpath(target, link_path.parent))
        except ValueError:
            rel = target
        link_path.symlink_to(rel, target_is_directory=True)
        logger.info("Linked %s -> %s", link_path, rel)


@click.command()
@click.argument("url", type=str)
@click.option(
    "--repo-root",
    type=click.Path(file_okay=False, path_type=Path),
    default=None,
    help=f"Repository root (default: {ENV_REPO_ROOT} if set, else this script's repo)",
)
@click.option(
    "--external",
    "external_dir",
    type=click.Path(file_okay=False, path_type=Path),
    default=None,
    help=f"External directory for submodules (default: <repo-root>/{EXTERNAL_DIR})",
)
@click.option(
    "--skills",
    "skills_dir",
    type=click.Path(file_okay=False, path_type=Path),
    default=None,
    help=f"Skills directory for symlinks (default: <repo-root>/{SKILLS_DIR})",
)
def main(
    url: str,
    repo_root: Path | None,
    external_dir: Path | None,
    skills_dir: Path | None,
) -> None:
    """Add a Git repo as submodule under external/ and symlink skill folders to .claude/skills."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    if repo_root is None:
        repo_root = _default_repo_root()
    repo_root = repo_root.resolve()
    if external_dir is None:
        external_dir = repo_root / EXTERNAL_DIR
    else:
        external_dir = external_dir.resolve()
    if skills_dir is None:
        skills_dir = repo_root / SKILLS_DIR
    else:
        skills_dir = skills_dir.resolve()

    run(repo_root, url, external_dir, skills_dir)


if __name__ == "__main__":
    main()
