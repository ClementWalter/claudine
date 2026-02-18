#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Auto-commit and push any pending changes in the claudine repo.

Designed to run as a launchd periodic job. Symlinked directories may be modified
by external tools, and this script ensures those changes are always committed
and pushed without manual intervention.

Workflow:
  1. Stash local changes (if any)
  2. Pull --rebase to sync with remote
  3. Pop stash
  4. If conflicts arise, invoke a Claude agent to resolve them
  5. Commit and push
"""

import logging
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

# Repo root is the parent of the scripts/ directory
REPO_DIR = Path(__file__).resolve().parent.parent

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("auto_commit")


def run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
    """Run a command in the repo directory, logging it for traceability."""
    logger.debug("Running: %s", " ".join(cmd))
    result = subprocess.run(
        cmd,
        cwd=REPO_DIR,
        capture_output=True,
        text=True,
        **kwargs,
    )
    if result.stdout.strip():
        logger.debug("stdout: %s", result.stdout.strip())
    if result.stderr.strip():
        logger.debug("stderr: %s", result.stderr.strip())
    return result


def has_changes() -> bool:
    """Check if the working tree has any uncommitted changes."""
    # Refresh the index first (handles stat-only changes from symlinks)
    run(["git", "update-index", "--refresh"])
    result = run(["git", "status", "--porcelain"])
    return bool(result.stdout.strip())


def has_conflicts() -> bool:
    """Check if the working tree has unresolved merge conflicts."""
    result = run(["git", "diff", "--name-only", "--diff-filter=U"])
    return bool(result.stdout.strip())


def get_conflict_files() -> list[str]:
    """Return the list of files with unresolved merge conflicts."""
    result = run(["git", "diff", "--name-only", "--diff-filter=U"])
    return [f for f in result.stdout.strip().splitlines() if f]


def resolve_conflicts_with_claude() -> bool:
    """Invoke Claude Code in non-interactive mode to resolve merge conflicts."""
    conflict_files = get_conflict_files()
    if not conflict_files:
        return True

    files_list = "\n".join(f"  - {f}" for f in conflict_files)
    prompt = (
        "You are resolving merge conflicts in the claudine repo, an auto-synced "
        "dotfiles/config repository. The following files have conflicts:\n"
        f"{files_list}\n\n"
        "For each conflicted file:\n"
        "1. Read the file to understand both sides of the conflict\n"
        "2. Resolve the conflict by keeping the most complete/recent version, "
        "or merging both sides when they touch different parts\n"
        "3. Remove all conflict markers (<<<<<<, ======, >>>>>>)\n"
        "4. Stage the resolved file with git add\n\n"
        "This is an automated sync — prefer keeping all content from both sides "
        "when possible. If in doubt, prefer the incoming (remote) changes."
    )

    logger.info(
        "Invoking Claude agent to resolve conflicts in: %s",
        ", ".join(conflict_files),
    )

    result = subprocess.run(
        [
            "claude",
            "-p",
            "--dangerously-skip-permissions",
            "--model", "haiku",
            prompt,
        ],
        cwd=REPO_DIR,
        capture_output=True,
        text=True,
        # Unset CLAUDECODE to allow running from within a claude session
        env={**_get_clean_env(), "CLAUDECODE": ""},
        timeout=120,
    )

    if result.returncode != 0:
        logger.error("Claude agent failed: %s", result.stderr)
        return False

    logger.info("Claude agent output: %s", result.stdout.strip()[:500])

    # Verify no conflicts remain
    if has_conflicts():
        logger.error("Conflicts remain after Claude agent resolution.")
        return False

    return True


def _get_clean_env() -> dict[str, str]:
    """Get a copy of the current environment."""
    import os

    return dict(os.environ)


def stash_local_changes() -> bool:
    """Stash local changes, return True if something was stashed."""
    result = run(["git", "stash", "push", "-m", "auto-sync-stash", "--include-untracked"])
    if result.returncode != 0:
        logger.error("git stash failed: %s", result.stderr)
        return False
    # git stash outputs "No local changes to save" when nothing to stash
    stashed = "No local changes to save" not in result.stdout
    if stashed:
        logger.info("Stashed local changes.")
    return stashed


def pull_rebase() -> bool:
    """Pull with rebase from origin. Returns True on success."""
    result = run(["git", "pull", "--rebase", "--autostash"])
    if result.returncode != 0:
        logger.warning("git pull --rebase failed: %s", result.stderr)
        # Abort the rebase to get back to a clean state
        if "rebase" in result.stderr.lower() or "conflict" in result.stderr.lower():
            logger.info("Aborting failed rebase...")
            run(["git", "rebase", "--abort"])
        return False
    logger.info("Pulled and rebased successfully.")
    return True


def pop_stash() -> bool:
    """Pop the stash. Returns True on success, False on conflict."""
    result = run(["git", "stash", "pop"])
    if result.returncode != 0:
        if "conflict" in result.stdout.lower() or "conflict" in result.stderr.lower():
            logger.warning("Stash pop produced conflicts.")
            return False
        logger.error("git stash pop failed: %s", result.stderr)
        return False
    logger.info("Popped stash successfully.")
    return True


def commit_and_push() -> int:
    """Stage everything, commit and push. Returns 0 on success."""
    # Stage all changes
    result = run(["git", "add", "-A"])
    if result.returncode != 0:
        logger.error("git add failed: %s", result.stderr)
        return 1

    # Check if there's actually something to commit
    result = run(["git", "diff", "--cached", "--quiet"])
    if result.returncode == 0:
        logger.info("Nothing staged after git add, nothing to commit.")
        return 0

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    message = f"auto-sync: {now}"

    # Skip hooks — this is automated sync of symlinked content
    result = run(["git", "commit", "-m", message, "--no-verify"])
    if result.returncode != 0:
        logger.error("git commit failed: %s", result.stderr)
        return 1
    logger.info("Committed: %s", message)

    result = run(["git", "push"])
    if result.returncode != 0:
        logger.error("git push failed: %s", result.stderr)
        return 1
    logger.info("Pushed to origin.")
    return 0


def main() -> int:
    """Sync local changes with remote: stash, rebase, resolve, commit, push."""
    local_changes = has_changes()
    did_stash = False

    if local_changes:
        did_stash = stash_local_changes()

    # Always try to pull rebase to stay in sync with remote
    pull_ok = pull_rebase()
    if not pull_ok:
        # If rebase failed and we stashed, try to recover the stash
        if did_stash:
            logger.warning("Rebase failed, recovering stash...")
            run(["git", "stash", "pop"])
        # Don't abort — we can still commit and push local changes

    # Pop stash if we stashed
    if did_stash:
        stash_ok = pop_stash()
        if not stash_ok and has_conflicts():
            # Conflicts from stash pop — ask Claude to resolve
            resolved = resolve_conflicts_with_claude()
            if not resolved:
                logger.error(
                    "Could not resolve conflicts. Dropping stash and keeping remote state."
                )
                # Reset to clean state, drop the conflicted stash application
                run(["git", "checkout", "--", "."])
                run(["git", "clean", "-fd"])
                # The stash is already applied (partially), drop it
                run(["git", "stash", "drop"])
                return 1

    if not has_changes():
        logger.info("No changes to commit after sync.")
        return 0

    return commit_and_push()


if __name__ == "__main__":
    sys.exit(main())
