"""Unit tests for add_skill_repo_submodule (repo name parsing and skill folder discovery)."""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.add_skill_repo_submodule import (
    ENV_REPO_ROOT,
    _default_repo_root,
    minimal_skill_dirs,
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
