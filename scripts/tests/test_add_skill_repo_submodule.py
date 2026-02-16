"""Unit tests for add_skill_repo_submodule (repo name parsing and skill folder discovery)."""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.add_skill_repo_submodule import (
    ENV_REPO_ROOT,
    _default_repo_root,
    repo_name_from_url,
    skill_folders_under,
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


def test_skill_folders_under_non_dir_returns_empty(tmp_path: Path) -> None:
    """Non-directory path returns empty list."""
    file_path = tmp_path / "f"
    file_path.touch()
    assert skill_folders_under(file_path) == []


def test_skill_folders_under_empty_dir_returns_empty(tmp_path: Path) -> None:
    """Empty directory returns empty list."""
    assert skill_folders_under(tmp_path) == []


def test_skill_folders_under_ignores_dir_without_skill_md(tmp_path: Path) -> None:
    """Directories without SKILL.md are not returned."""
    (tmp_path / "no_skill").mkdir()
    assert skill_folders_under(tmp_path) == []


def test_skill_folders_under_returns_one_folder_when_one_has_skill_md(tmp_path: Path) -> None:
    """One directory with SKILL.md yields a single result."""
    d = tmp_path / "askill"
    d.mkdir()
    (d / SKILL_FILENAME).write_text("")
    result = skill_folders_under(tmp_path)
    assert len(result) == 1


def test_skill_folders_under_returned_folder_has_expected_name(tmp_path: Path) -> None:
    """Returned folder name matches the directory that contains SKILL.md."""
    d = tmp_path / "askill"
    d.mkdir()
    (d / SKILL_FILENAME).write_text("")
    result = skill_folders_under(tmp_path)
    assert result[0].name == "askill"


def test_skill_folders_under_returns_sorted_by_name(tmp_path: Path) -> None:
    """Returned list is sorted by folder name."""
    for name in ("b", "a", "c"):
        (tmp_path / name).mkdir()
        (tmp_path / name / SKILL_FILENAME).write_text("")
    result = skill_folders_under(tmp_path)
    assert [p.name for p in result] == ["a", "b", "c"]


def test_skill_folders_under_ignores_files(tmp_path: Path) -> None:
    """Files named SKILL.md in root are ignored (only subdirs checked)."""
    (tmp_path / SKILL_FILENAME).write_text("")
    assert skill_folders_under(tmp_path) == []
