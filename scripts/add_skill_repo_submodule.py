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

GitHub tree URLs (e.g. https://github.com/org/repo/tree/main/some/path) are handled
specially: the base repo is added as a submodule and a scaffold skill is created under
.claude/skills/<repo-name>/ with a ``references`` symlink pointing to the given subpath.
A Claude agent is then launched to generate a SKILL.md from the references content
(disable with --no-skillgen).

Can be run from any working directory. Default repo root is the repo that contains
this script; set CLAUDINE_REPO or use --repo-root to target a different repo.
"""

from __future__ import annotations

import logging
import os
import re
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


def parse_github_tree_url(url: str) -> tuple[str, str, str] | None:
    """
    Parse a GitHub tree URL and return (base_repo_url, branch, subpath).

    Returns None if the URL is not a GitHub /tree/<branch>/<path> URL.
    Example: https://github.com/org/repo/tree/main/some/path
    -> ("https://github.com/org/repo", "main", "some/path")
    """
    m = re.match(r"^(https://github\.com/[^/]+/[^/]+)/tree/([^/]+)/(.+)$", url.strip())
    if m:
        return m.group(1), m.group(2), m.group(3)
    return None


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


def _scaffold_skill_from_subpath(
    skills_dir: Path,
    skill_name: str,
    submodule_path: Path,
    subpath: str,
    force: bool,
    run_skillgen: bool,
) -> None:
    """
    Create a real skill directory with a references symlink pointing to subpath in the submodule.

    Unlike the plain-repo path (which makes the skill dir itself a symlink), this creates a
    real directory so Claude can write SKILL.md into it. The ``references`` entry inside is a
    symlink to the chosen subpath of the cloned submodule.

    Optionally launches a Claude agent to auto-generate SKILL.md from the references.
    """
    skill_dir = skills_dir / skill_name
    if skill_dir.exists() and not force:
        logger.error("Skill directory already exists: %s", skill_dir)
        sys.exit(1)
    skill_dir.mkdir(parents=True, exist_ok=True)

    # Resolve the target path inside the cloned submodule
    target = submodule_path.resolve() / subpath
    if not target.exists():
        logger.error("Subpath does not exist in submodule: %s", target)
        sys.exit(1)

    references_link = skill_dir / "references"
    if references_link.exists() or references_link.is_symlink():
        if not force:
            logger.error("references link already exists: %s", references_link)
            sys.exit(1)
        if references_link.is_symlink():
            references_link.unlink()
        else:
            shutil.rmtree(references_link)

    # Use a relative symlink so the skill directory remains portable
    try:
        rel = Path(os.path.relpath(target, references_link.parent))
    except ValueError:
        rel = target
    references_link.symlink_to(rel, target_is_directory=True)
    logger.info("Linked %s -> %s", references_link, rel)

    if run_skillgen:
        _run_claude_skillgen(skill_dir)


def _run_claude_skillgen(skill_dir: Path) -> None:
    """
    Launch the Claude CLI to auto-generate a SKILL.md in skill_dir.

    Runs ``claude -p`` with a prompt that instructs Claude to explore the references
    folder and apply skill-creator best practices to produce a well-structured SKILL.md.
    Streams output directly so the user can follow progress.
    """
    prompt = (
        "Do a deep exploration of the references folder to understand what this is about. "
        "Use the skill-creator skill best practices to generate a SKILL.md file summarizing "
        "the content of this skill's references and pointing to them in relevant parts."
    )
    logger.info("Launching Claude to generate SKILL.md in %s", skill_dir)
    try:
        # No capture_output so the generation streams to the user's terminal
        # --dangerously-skip-permissions allows Claude to write files without prompting
        subprocess.run(
            ["claude", "-p", prompt, "--dangerously-skip-permissions"],
            cwd=skill_dir,
            check=True,
        )
        logger.info("SKILL.md generation complete in %s", skill_dir)
    except subprocess.CalledProcessError as e:
        logger.warning("Claude skillgen failed (exit %d); SKILL.md was not generated", e.returncode)
    except FileNotFoundError:
        logger.warning("claude CLI not found in PATH; skipping SKILL.md generation")


def run(
    repo_root: Path,
    url: str,
    external_dir: Path,
    skills_dir: Path,
    force: bool = False,
    run_skillgen: bool = True,
) -> None:
    """
    Add submodule at external/<repo_name> and create skill entries under .claude/skills.

    For plain repo URLs: discovers SKILL.md folders and creates flat symlinks.
    For GitHub tree URLs (containing /tree/<branch>/<path>): creates a scaffold skill
    directory named after the repo with a references symlink to the subpath, then
    optionally runs Claude to generate a SKILL.md.

    With --force: skip adding if submodule path exists (only create/update symlinks),
    and overwrite existing symlinks or empty dirs at skill targets.
    """
    # Detect GitHub tree URLs to separate the base repo URL from the subpath
    tree_info = parse_github_tree_url(url)
    if tree_info:
        base_url, _branch, subpath = tree_info
        actual_url = base_url
        logger.info("Detected GitHub tree URL; base repo: %s, subpath: %s", base_url, subpath)
    else:
        actual_url = url
        subpath = None

    name = repo_name_from_url(actual_url)
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
        logger.info("Adding submodule %s at %s", actual_url, submodule_path)
        try:
            add_submodule(repo_root, actual_url, submodule_path)
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
                    ["git", "config", "-f", ".gitmodules", f"submodule.{submodule_rel_str}.url", actual_url],
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

    ensure_dir(skills_dir)

    if subpath:
        # GitHub tree URL path: scaffold a real skill directory with a references symlink
        _scaffold_skill_from_subpath(
            skills_dir=skills_dir,
            skill_name=name,
            submodule_path=submodule_path,
            subpath=subpath,
            force=force,
            run_skillgen=run_skillgen,
        )
    else:
        # Plain repo URL path: discover SKILL.md folders and create flat symlinks
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
            link_path = skills_dir / skill_name
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
@click.option(
    "--skillgen/--no-skillgen",
    default=True,
    help="Run Claude to auto-generate SKILL.md for scaffold skills from tree URLs (default: enabled)",
)
def main(
    url: str,
    repo_root: Path | None,
    external_dir: Path | None,
    skills_dir: Path | None,
    force: bool,
    skillgen: bool,
) -> None:
    """Add a Git repo as submodule under external/ and symlink skill folders to .claude/skills.

    For GitHub tree URLs (https://github.com/org/repo/tree/branch/path), creates a scaffold
    skill directory with a references symlink and optionally auto-generates SKILL.md via Claude.
    """
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

    run(repo_root, url, external_dir, skills_dir, force=force, run_skillgen=skillgen)


if __name__ == "__main__":
    main()
