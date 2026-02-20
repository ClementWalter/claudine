"""Unit tests for add_skill_repo_submodule (repo name parsing and skill folder discovery)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from scripts.add_skill_repo_submodule import (
    ENV_REPO_ROOT,
    _default_repo_root,
    _run_claude_skillgen,
    _scaffold_skill_from_subpath,
    minimal_skill_dirs,
    parse_github_tree_url,
    repo_name_from_url,
    skill_folders_recursive,
)

SKILL_FILENAME = "SKILL.md"


def test_default_repo_root_uses_script_repo_when_env_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    """When CLAUDINE_REPO is not set, repo root is the directory containing the script (parent of scripts/)."""
    import scripts.add_skill_repo_submodule as _mod

    monkeypatch.delenv(ENV_REPO_ROOT, raising=False)
    expected = Path(_mod.__file__).resolve().parent.parent
    assert _default_repo_root() == expected


def test_default_repo_root_uses_env_when_set(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """When CLAUDINE_REPO is set, repo root is that path (expanduser applied)."""
    monkeypatch.setenv(ENV_REPO_ROOT, str(tmp_path))
    assert _default_repo_root() == tmp_path


@pytest.mark.parametrize(
    "url,expected",
    [
        ("git@github.com:austintgriffith/ethskills.git", "ethskills"),
        ("https://github.com/org/repo.git", "repo"),
        ("https://github.com/org/repo", "repo"),
        ("git@host:onlyrepo", "onlyrepo"),
        ("https://example.com/a/b/c", "c"),
    ],
)
def test_repo_name_from_url_returns_last_segment(url: str, expected: str) -> None:
    """Repo name is the last path segment with .git stripped."""
    assert repo_name_from_url(url) == expected


def test_repo_name_from_url_empty_returns_none() -> None:
    """Empty URL yields None."""
    assert repo_name_from_url("") is None


def test_repo_name_from_url_whitespace_only_returns_none() -> None:
    """Whitespace-only URL yields None."""
    assert repo_name_from_url("   ") is None


def test_repo_name_from_url_dot_git_only_returns_none() -> None:
    """URL that becomes empty after stripping .git yields None."""
    assert repo_name_from_url(".git") is None


def test_skill_folders_recursive_non_dir_returns_empty(tmp_path: Path) -> None:
    """Non-directory path returns empty list."""
    file_path = tmp_path / "f"
    file_path.touch()
    assert skill_folders_recursive(file_path) == []


def test_skill_folders_recursive_empty_dir_returns_empty(tmp_path: Path) -> None:
    """Empty directory returns empty list."""
    assert skill_folders_recursive(tmp_path) == []


def test_skill_folders_recursive_ignores_dir_without_skill_md(tmp_path: Path) -> None:
    """Directories without SKILL.md are not returned."""
    (tmp_path / "no_skill").mkdir()
    assert skill_folders_recursive(tmp_path) == []


def test_skill_folders_recursive_returns_one_folder_when_one_has_skill_md(tmp_path: Path) -> None:
    """One directory with SKILL.md yields a single result."""
    d = tmp_path / "askill"
    d.mkdir()
    (d / SKILL_FILENAME).write_text("")
    result = skill_folders_recursive(tmp_path)
    assert len(result) == 1


def test_skill_folders_recursive_returned_folder_has_expected_name(tmp_path: Path) -> None:
    """Returned folder name matches the directory that contains SKILL.md."""
    d = tmp_path / "askill"
    d.mkdir()
    (d / SKILL_FILENAME).write_text("")
    result = skill_folders_recursive(tmp_path)
    assert result[0].name == "askill"


def test_skill_folders_recursive_includes_root_when_root_has_skill_md(tmp_path: Path) -> None:
    """When root contains SKILL.md, root is included in results."""
    (tmp_path / SKILL_FILENAME).write_text("")
    result = skill_folders_recursive(tmp_path)
    assert len(result) == 1
    assert result[0] == tmp_path


def test_skill_folders_recursive_finds_nested_dir_with_skill_md(tmp_path: Path) -> None:
    """Directories with SKILL.md at any depth are found."""
    (tmp_path / "foo" / "bar").mkdir(parents=True)
    (tmp_path / "foo" / "bar" / SKILL_FILENAME).write_text("")
    result = skill_folders_recursive(tmp_path)
    assert len(result) == 1
    assert result[0].name == "bar"
    assert result[0].parent.name == "foo"


def test_skill_folders_recursive_returns_sorted_by_depth_then_path(tmp_path: Path) -> None:
    """Returned list is sorted by path length then path."""
    for name in ("b", "a", "c"):
        (tmp_path / name).mkdir()
        (tmp_path / name / SKILL_FILENAME).write_text("")
    result = skill_folders_recursive(tmp_path)
    assert [p.name for p in result] == ["a", "b", "c"]


def test_minimal_skill_dirs_keeps_only_topmost_when_nested(tmp_path: Path) -> None:
    """When both parent and child have SKILL.md, only the parent is kept."""
    (tmp_path / "foo").mkdir()
    (tmp_path / "foo" / SKILL_FILENAME).write_text("")
    (tmp_path / "foo" / "bar").mkdir()
    (tmp_path / "foo" / "bar" / SKILL_FILENAME).write_text("")
    all_dirs = skill_folders_recursive(tmp_path)
    minimal = minimal_skill_dirs(all_dirs, tmp_path)
    assert len(minimal) == 1
    assert minimal[0].name == "foo"


def test_minimal_skill_dirs_keeps_both_when_siblings(tmp_path: Path) -> None:
    """When two sibling dirs have SKILL.md, both are kept."""
    (tmp_path / "foo").mkdir()
    (tmp_path / "foo" / SKILL_FILENAME).write_text("")
    (tmp_path / "bar").mkdir()
    (tmp_path / "bar" / SKILL_FILENAME).write_text("")
    all_dirs = skill_folders_recursive(tmp_path)
    minimal = minimal_skill_dirs(all_dirs, tmp_path)
    assert len(minimal) == 2
    names = {p.name for p in minimal}
    assert names == {"foo", "bar"}


# ---------------------------------------------------------------------------
# parse_github_tree_url
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "url,expected_base",
    [
        (
            "https://github.com/kitlangton/effect-solutions/tree/main/packages/website/docs",
            "https://github.com/kitlangton/effect-solutions",
        ),
        (
            "https://github.com/org/repo/tree/develop/src/components",
            "https://github.com/org/repo",
        ),
    ],
)
def test_parse_github_tree_url_returns_base_url(url: str, expected_base: str) -> None:
    """Base repo URL is the part before /tree/."""
    result = parse_github_tree_url(url)
    assert result is not None
    assert result[0] == expected_base


@pytest.mark.parametrize(
    "url,expected_branch",
    [
        (
            "https://github.com/kitlangton/effect-solutions/tree/main/packages/website/docs",
            "main",
        ),
        (
            "https://github.com/org/repo/tree/develop/src",
            "develop",
        ),
    ],
)
def test_parse_github_tree_url_returns_branch(url: str, expected_branch: str) -> None:
    """Branch name is the segment immediately after /tree/."""
    result = parse_github_tree_url(url)
    assert result is not None
    assert result[1] == expected_branch


@pytest.mark.parametrize(
    "url,expected_subpath",
    [
        (
            "https://github.com/kitlangton/effect-solutions/tree/main/packages/website/docs",
            "packages/website/docs",
        ),
        (
            "https://github.com/org/repo/tree/main/src",
            "src",
        ),
    ],
)
def test_parse_github_tree_url_returns_subpath(url: str, expected_subpath: str) -> None:
    """Subpath is everything after /tree/<branch>/."""
    result = parse_github_tree_url(url)
    assert result is not None
    assert result[2] == expected_subpath


def test_parse_github_tree_url_returns_none_for_plain_https_url() -> None:
    """Plain HTTPS repo URL without /tree/ returns None."""
    assert parse_github_tree_url("https://github.com/org/repo") is None


def test_parse_github_tree_url_returns_none_for_plain_https_url_with_git_suffix() -> None:
    """Plain HTTPS .git URL without /tree/ returns None."""
    assert parse_github_tree_url("https://github.com/org/repo.git") is None


def test_parse_github_tree_url_returns_none_for_ssh_url() -> None:
    """SSH git@ URLs return None."""
    assert parse_github_tree_url("git@github.com:org/repo.git") is None


def test_parse_github_tree_url_returns_none_for_tree_without_subpath() -> None:
    """A /tree/<branch> URL with no path after the branch returns None."""
    assert parse_github_tree_url("https://github.com/org/repo/tree/main") is None


def test_parse_github_tree_url_returns_none_for_empty_string() -> None:
    """Empty string returns None."""
    assert parse_github_tree_url("") is None


# ---------------------------------------------------------------------------
# _scaffold_skill_from_subpath
# ---------------------------------------------------------------------------


def test_scaffold_skill_creates_skill_directory(tmp_path: Path) -> None:
    """Scaffold creates the skill directory."""
    submodule = tmp_path / "external" / "myrepo"
    (submodule / "docs").mkdir(parents=True)
    skills_dir = tmp_path / "skills"
    _scaffold_skill_from_subpath(skills_dir, "myrepo", submodule, "docs", force=False, run_skillgen=False)
    assert (skills_dir / "myrepo").is_dir()


def test_scaffold_skill_creates_references_symlink(tmp_path: Path) -> None:
    """Scaffold creates a references symlink inside the skill directory."""
    submodule = tmp_path / "external" / "myrepo"
    (submodule / "docs").mkdir(parents=True)
    skills_dir = tmp_path / "skills"
    _scaffold_skill_from_subpath(skills_dir, "myrepo", submodule, "docs", force=False, run_skillgen=False)
    assert (skills_dir / "myrepo" / "references").is_symlink()


def test_scaffold_skill_references_resolves_to_subpath(tmp_path: Path) -> None:
    """The references symlink resolves to the correct subpath in the submodule."""
    submodule = tmp_path / "external" / "myrepo"
    docs = submodule / "docs"
    docs.mkdir(parents=True)
    skills_dir = tmp_path / "skills"
    _scaffold_skill_from_subpath(skills_dir, "myrepo", submodule, "docs", force=False, run_skillgen=False)
    assert (skills_dir / "myrepo" / "references").resolve() == docs.resolve()


def test_scaffold_skill_exits_when_skill_dir_exists_without_force(tmp_path: Path) -> None:
    """Exits with SystemExit when skill dir already exists and force=False."""
    submodule = tmp_path / "external" / "myrepo"
    (submodule / "docs").mkdir(parents=True)
    skills_dir = tmp_path / "skills"
    (skills_dir / "myrepo").mkdir(parents=True)
    with pytest.raises(SystemExit):
        _scaffold_skill_from_subpath(skills_dir, "myrepo", submodule, "docs", force=False, run_skillgen=False)


def test_scaffold_skill_force_overwrites_existing_references_symlink(tmp_path: Path) -> None:
    """With force=True, an existing references symlink is replaced."""
    submodule = tmp_path / "external" / "myrepo"
    docs = submodule / "docs"
    docs.mkdir(parents=True)
    skills_dir = tmp_path / "skills"
    # First creation
    _scaffold_skill_from_subpath(skills_dir, "myrepo", submodule, "docs", force=False, run_skillgen=False)
    # Second creation with force
    _scaffold_skill_from_subpath(skills_dir, "myrepo", submodule, "docs", force=True, run_skillgen=False)
    assert (skills_dir / "myrepo" / "references").resolve() == docs.resolve()


def test_scaffold_skill_exits_when_subpath_does_not_exist(tmp_path: Path) -> None:
    """Exits with SystemExit when the subpath does not exist inside the submodule."""
    submodule = tmp_path / "external" / "myrepo"
    submodule.mkdir(parents=True)
    skills_dir = tmp_path / "skills"
    with pytest.raises(SystemExit):
        _scaffold_skill_from_subpath(skills_dir, "myrepo", submodule, "missing/path", force=False, run_skillgen=False)


def test_scaffold_skill_does_not_call_claude_when_run_skillgen_false(tmp_path: Path) -> None:
    """When run_skillgen=False, the Claude CLI is never invoked."""
    submodule = tmp_path / "external" / "myrepo"
    (submodule / "docs").mkdir(parents=True)
    skills_dir = tmp_path / "skills"
    with patch("scripts.add_skill_repo_submodule.subprocess.run") as mock_run:
        _scaffold_skill_from_subpath(skills_dir, "myrepo", submodule, "docs", force=False, run_skillgen=False)
    mock_run.assert_not_called()


def test_scaffold_skill_calls_claude_when_run_skillgen_true(tmp_path: Path) -> None:
    """When run_skillgen=True, subprocess.run is called with the claude CLI."""
    submodule = tmp_path / "external" / "myrepo"
    (submodule / "docs").mkdir(parents=True)
    skills_dir = tmp_path / "skills"
    with patch("scripts.add_skill_repo_submodule.subprocess.run") as mock_run:
        _scaffold_skill_from_subpath(skills_dir, "myrepo", submodule, "docs", force=False, run_skillgen=True)
    assert mock_run.call_count == 1
    called_cmd = mock_run.call_args[0][0]
    assert called_cmd[0] == "claude"


# ---------------------------------------------------------------------------
# _run_claude_skillgen
# ---------------------------------------------------------------------------


def test_run_claude_skillgen_invokes_claude_p(tmp_path: Path) -> None:
    """The claude CLI is called with the -p flag."""
    with patch("scripts.add_skill_repo_submodule.subprocess.run") as mock_run:
        _run_claude_skillgen(tmp_path)
    called_cmd = mock_run.call_args[0][0]
    assert called_cmd[0] == "claude"
    assert called_cmd[1] == "-p"


def test_run_claude_skillgen_uses_skill_dir_as_cwd(tmp_path: Path) -> None:
    """The claude process runs with cwd set to the skill directory."""
    with patch("scripts.add_skill_repo_submodule.subprocess.run") as mock_run:
        _run_claude_skillgen(tmp_path)
    assert mock_run.call_args[1]["cwd"] == tmp_path


def test_run_claude_skillgen_handles_file_not_found_gracefully(tmp_path: Path) -> None:
    """FileNotFoundError (claude not in PATH) is caught and does not propagate."""
    with patch("scripts.add_skill_repo_submodule.subprocess.run", side_effect=FileNotFoundError):
        _run_claude_skillgen(tmp_path)  # must not raise


def test_run_claude_skillgen_handles_called_process_error_gracefully(tmp_path: Path) -> None:
    """CalledProcessError from claude is caught and does not propagate."""
    import subprocess

    with patch(
        "scripts.add_skill_repo_submodule.subprocess.run",
        side_effect=subprocess.CalledProcessError(1, "claude"),
    ):
        _run_claude_skillgen(tmp_path)  # must not raise
