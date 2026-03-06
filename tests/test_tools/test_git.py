"""Tests for remy.ai.tools.git module (US-git-commits-and-diffs)."""

from __future__ import annotations

import tempfile
from unittest.mock import MagicMock

import pytest

from remy.ai.tools import git


def make_registry() -> MagicMock:
    """Create a mock registry for git executors."""
    return MagicMock()


@pytest.fixture(autouse=True)
def use_cwd_as_repo(monkeypatch):
    """Reset workspace_root so git tools fall back to cwd (the project root, a git repo)."""
    stub = type("Stub", (), {"workspace_root": ""})()
    monkeypatch.setattr(git, "settings", stub)


class TestExecGitLog:
    """Tests for exec_git_log."""

    @pytest.mark.asyncio
    async def test_returns_string_in_repo(self):
        """In a git repo, returns formatted log lines."""
        registry = make_registry()
        result = await git.exec_git_log(registry, {"ref": "HEAD", "limit": 2})
        assert isinstance(result, str)
        assert "git log failed" not in result
        # Should have at least one line with hash-like prefix (7 chars)
        lines = [line for line in result.split("\n") if line.strip()]
        if lines:
            assert len(lines[0]) >= 7

    @pytest.mark.asyncio
    async def test_defaults_ref_and_limit(self):
        """Empty input uses HEAD and default limit."""
        registry = make_registry()
        result = await git.exec_git_log(registry, {})
        assert isinstance(result, str)
        assert "git log failed" not in result or "provide" in result.lower()

    @pytest.mark.asyncio
    async def test_invalid_limit_coerced(self):
        """Non-integer limit is coerced to default."""
        registry = make_registry()
        result = await git.exec_git_log(registry, {"ref": "HEAD", "limit": "nope"})
        assert isinstance(result, str)


class TestExecGitShowCommit:
    """Tests for exec_git_show_commit."""

    @pytest.mark.asyncio
    async def test_requires_ref(self):
        """Missing ref returns error message."""
        registry = make_registry()
        result = await git.exec_git_show_commit(registry, {})
        assert "ref" in result.lower() or "provide" in result.lower()

    @pytest.mark.asyncio
    async def test_returns_string_with_ref(self):
        """With valid ref returns commit details."""
        registry = make_registry()
        result = await git.exec_git_show_commit(registry, {"ref": "HEAD"})
        assert isinstance(result, str)
        assert "git show failed" not in result


class TestExecGitDiff:
    """Tests for exec_git_diff."""

    @pytest.mark.asyncio
    async def test_requires_commit_or_base_head(self):
        """Neither commit nor base/head returns error."""
        registry = make_registry()
        result = await git.exec_git_diff(registry, {})
        assert (
            "base" in result.lower()
            or "head" in result.lower()
            or "commit" in result.lower()
        )

    @pytest.mark.asyncio
    async def test_rejects_both_commit_and_base_head(self):
        """Providing both commit and base/head returns error."""
        registry = make_registry()
        result = await git.exec_git_diff(
            registry, {"commit": "HEAD", "base": "main", "head": "HEAD"}
        )
        assert "not both" in result.lower()

    @pytest.mark.asyncio
    async def test_returns_string_with_base_head(self):
        """With base and head returns diff or no diff."""
        registry = make_registry()
        result = await git.exec_git_diff(registry, {"base": "HEAD~1", "head": "HEAD"})
        assert isinstance(result, str)
        assert "git diff failed" not in result

    @pytest.mark.asyncio
    async def test_returns_string_with_commit(self):
        """With commit returns diff."""
        registry = make_registry()
        result = await git.exec_git_diff(registry, {"commit": "HEAD"})
        assert isinstance(result, str)
        assert "git diff failed" not in result


class TestExecGitStatus:
    """Tests for exec_git_status."""

    @pytest.mark.asyncio
    async def test_returns_string_in_repo(self):
        """In a git repo, returns status string."""
        registry = make_registry()
        result = await git.exec_git_status(registry, {})
        assert isinstance(result, str)
        assert "git status failed" not in result
        assert "##" in result or "branch" in result.lower() or "On branch" in result


class TestGetRepoRoot:
    """Tests for _get_repo_root (when not in repo)."""

    def test_returns_none_when_workspace_not_a_repo(self, monkeypatch):
        """When workspace_root is set to a non-git dir, returns None."""
        with tempfile.TemporaryDirectory() as tmp:
            stub = type("Stub", (), {"workspace_root": tmp})()
            monkeypatch.setattr(git, "settings", stub)
            root = git._get_repo_root()
            assert root is None
