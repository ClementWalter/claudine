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
import shutil
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


def skill_folders_recursive(root: Path) -> list[Path]:
    """Return all directories under root (any depth) that contain SKILL.md."""
    if not root.is_dir():
        return []
    out: list[Path] = []
    if (root / SKILL_FILENAME).is_file():
        out.append(root)
    for p in root.rglob("*"):
        if p.is_dir() and (p / SKILL_FILENAME).is_file():
            out.append(p)
    return sorted(out, key=lambda x: (len(x.parts), x))


def minimal_skill_dirs(dirs: list[Path], submodule_root: Path) -> list[Path]:
    """Keep only dirs that have no ancestor in dirs, so one symlink covers nested skills."""
    return [
        d
        for d in dirs
        if not any(a != d and d.is_relative_to(a) for a in dirs)
    ]


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
    force: bool = False,
) -> None:
    """
    Add submodule at external/<repo_name> and symlink skill folders into .claude/skills.
    With --force: skip adding if submodule path exists (only create/update symlinks),
    and overwrite existing symlinks or empty dirs at skill targets.
    """
    name = repo_name_from_url(url)
    if not name:
        logger.error("Invalid or empty Git URL: could not derive repo name")
        sys.exit(1)

    submodule_path = external_dir / name
    submodule_already_exists = submodule_path.exists() or submodule_path.is_symlink()

    if submodule_already_exists and not force:
        logger.error("Submodule path already exists: %s", submodule_path)
        sys.exit(1)

    ensure_dir(external_dir)
    if not submodule_already_exists:
        logger.info("Adding submodule %s at %s", url, submodule_path)
        try:
            add_submodule(repo_root, url, submodule_path)
        except subprocess.CalledProcessError as e:
            logger.error("git submodule add failed: %s", e.stderr or e)
            sys.exit(1)
    else:
        logger.info("Submodule path already exists; updating and syncing symlinks (--force)")
        submodule_rel = submodule_path.resolve().relative_to(repo_root.resolve())
        submodule_rel_str = str(submodule_rel).replace("\\", "/")
        # Ensure .gitmodules has an entry with relative path so "git submodule update" can find the url
        try:
            r = subprocess.run(
                ["git", "config", "-f", ".gitmodules", "--get", f"submodule.{submodule_rel_str}.url"],
                cwd=repo_root,
                capture_output=True,
                text=True,
            )
            if r.returncode != 0 or not r.stdout.strip():
                subprocess.run(
                    ["git", "config", "-f", ".gitmodules", f"submodule.{submodule_rel_str}.path", submodule_rel_str],
                    cwd=repo_root,
                    check=True,
                    capture_output=True,
                    text=True,
                )
                subprocess.run(
                    ["git", "config", "-f", ".gitmodules", f"submodule.{submodule_rel_str}.url", url],
                    cwd=repo_root,
                    check=True,
                    capture_output=True,
                    text=True,
                )
                subprocess.run(["git", "submodule", "sync", "--"], cwd=repo_root, check=True, capture_output=True, text=True)
        except subprocess.CalledProcessError as e:
            logger.debug("Could not ensure .gitmodules entry: %s", e.stderr or e)
        try:
            subprocess.run(
                ["git", "submodule", "update", "--init", "--", str(submodule_path)],
                cwd=repo_root,
                check=True,
                capture_output=True,
                text=True,
            )
        except subprocess.CalledProcessError as e:
            logger.warning("git submodule update failed: %s; continuing with existing tree", e.stderr or e)

    skills_root = skills_dir
    ensure_dir(skills_root)

    all_with_skill = skill_folders_recursive(submodule_path)
    folders = minimal_skill_dirs(all_with_skill, submodule_path)
    if not folders:
        logger.info("No directories with %s found; no symlinks created", SKILL_FILENAME)
        return

    try:
        submodule_resolved = submodule_path.resolve()
    except OSError as e:
        logger.error("Cannot resolve submodule path: %s", e)
        sys.exit(1)

    # Flat layout: .claude/skills/<skill_name>/ for each skill (leaf name only)
    for folder in sorted(folders, key=lambda p: len(p.parts)):
        if folder == submodule_path:
            skill_name = name
            target = submodule_resolved
        else:
            skill_name = folder.name
            target = submodule_resolved / folder.relative_to(submodule_path)
        link_path = skills_root / skill_name
        if link_path.exists() or link_path.is_symlink():
            if not force:
                logger.error("Skill target already exists: %s", link_path)
                sys.exit(1)
            if link_path.is_symlink():
                link_path.unlink()
            elif link_path.is_dir():
                shutil.rmtree(link_path)
            else:
                logger.error("Skill target exists and is a file (not a dir/symlink): %s", link_path)
                sys.exit(1)
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
@click.option(
    "--force",
    "-f",
    is_flag=True,
    help="If submodule path exists, skip add and only update symlinks; overwrite existing skill symlinks/dirs",
)
def main(
    url: str,
    repo_root: Path | None,
    external_dir: Path | None,
    skills_dir: Path | None,
    force: bool,
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

    run(repo_root, url, external_dir, skills_dir, force=force)


if __name__ == "__main__":
    main()
