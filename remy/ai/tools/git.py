"""Read-only git tool executors for inspecting commits and diffs (US-git-commits-and-diffs)."""

from __future__ import annotations

import asyncio
import logging
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

from ...config import settings

if TYPE_CHECKING:
    from .registry import ToolRegistry

logger = logging.getLogger(__name__)

DIFF_MAX_BYTES = 32 * 1024
LOG_LIMIT_MAX = 50
GIT_TIMEOUT = 30


def _run_git(cwd: Path, *args: str) -> tuple[str, str, int]:
    """Run git with args in cwd. No shell. Returns (stdout, stderr, returncode)."""
    cmd = ["git", *args]
    try:
        r = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=GIT_TIMEOUT,
        )
        return (r.stdout or "", r.stderr or "", r.returncode)
    except subprocess.TimeoutExpired:
        return ("", "git command timed out", -1)
    except Exception as e:
        return ("", str(e), -1)


def _get_repo_root() -> Path | None:
    """Return git repo root: workspace_root if set, else from cwd via git rev-parse."""
    start: Path
    workspace = getattr(settings, "workspace_root", None)
    if workspace and str(workspace).strip():
        start = Path(workspace).expanduser().resolve()
    else:
        start = Path.cwd()
    if not start.is_dir():
        return None
    stdout, stderr, code = _run_git(start, "rev-parse", "--show-toplevel")
    if code != 0:
        logger.debug("Not a git repo from %s: %s", start, stderr.strip())
        return None
    root = stdout.strip()
    if not root:
        return None
    return Path(root).resolve()


def _git_log(ref: str, limit: int, path: str | None) -> tuple[str, str, int]:
    """Run git log. limit capped at LOG_LIMIT_MAX."""
    root = _get_repo_root()
    if root is None:
        return (
            "",
            "Not in a git repository (run from a repo or set workspace_root).",
            -1,
        )
    n = min(max(1, limit), LOG_LIMIT_MAX)
    fmt = "%h%x00%s%x00%an%x00%aI"
    args = ["log", f"-n{n}", f"--format={fmt}", ref]
    if path:
        args.extend(["--", path])
    return _run_git(root, *args)


def _git_show_commit(ref: str) -> tuple[str, str, int]:
    """Full message, author, date, and list of changed files for one commit."""
    root = _get_repo_root()
    if root is None:
        return ("", "Not in a git repository.", -1)
    # Message and metadata
    stdout1, stderr1, code1 = _run_git(
        root, "show", "-s", "--format=%B%x00%an%x00%ae%x00%aI", ref
    )
    if code1 != 0:
        return (stdout1, stderr1, code1)
    # Changed files (names only)
    stdout2, stderr2, code2 = _run_git(root, "diff", "--name-only", f"{ref}^..{ref}")
    if code2 != 0:
        # Maybe a root commit (no parent)
        stdout2, stderr2, code2 = _run_git(
            root, "show", "--name-only", "--format=", ref
        )
    parts = [stdout1.strip()]
    if stdout2.strip():
        parts.append("Files changed:\n" + stdout2.strip())
    return ("\n\n".join(parts), stderr2, code2 if code2 != 0 else code1)


def _git_diff(
    commit: str | None,
    base: str | None,
    head: str | None,
    path: str | None,
) -> tuple[str, str, int]:
    """Unified diff for one commit or between base and head. Output capped at DIFF_MAX_BYTES."""
    root = _get_repo_root()
    if root is None:
        return ("", "Not in a git repository.", -1)
    args: list[str]
    if commit:
        args = ["diff", f"{commit}^..{commit}"]
    elif base is not None and head is not None:
        args = ["diff", f"{base}..{head}"]
    else:
        return ("", "Provide either 'commit' or both 'base' and 'head'.", -1)
    if path:
        args.extend(["--", path])
    stdout, stderr, code = _run_git(root, *args)
    if code != 0:
        return (stdout, stderr, code)
    if len(stdout.encode("utf-8")) > DIFF_MAX_BYTES:
        truncated = stdout.encode("utf-8")[:DIFF_MAX_BYTES].decode(
            "utf-8", errors="replace"
        )
        stdout = truncated + f"\n\n[… truncated — diff exceeds {DIFF_MAX_BYTES} bytes]"
    return (stdout, stderr, code)


def _git_status() -> tuple[str, str, int]:
    """Short status: branch, ahead/behind, modified/untracked files."""
    root = _get_repo_root()
    if root is None:
        return ("", "Not in a git repository.", -1)
    stdout, stderr, code = _run_git(root, "status", "-sb")
    if code != 0:
        return (stdout, stderr, code)
    out = stdout.strip()
    stdout2, stderr2, code2 = _run_git(root, "status", "--short")
    if code2 == 0 and stdout2.strip():
        out += "\n\n" + stdout2.strip()
    return (out, stderr2, code2)


async def exec_git_log(registry: ToolRegistry, inp: dict) -> str:
    """List recent commits with hash, subject, author, date."""
    ref = (inp.get("ref") or "HEAD").strip() or "HEAD"
    limit = inp.get("limit", 10)
    try:
        limit = int(limit) if limit is not None else 10
    except (TypeError, ValueError):
        limit = 10
    path = (inp.get("path") or "").strip() or None

    def _do() -> str:
        stdout, stderr, code = _git_log(ref, limit, path)
        if code != 0:
            return f"git log failed: {stderr.strip() or 'unknown error'}"
        lines = []
        for line in stdout.strip().split("\n"):
            if not line:
                continue
            parts = line.split("\x00", 3)
            if len(parts) >= 4:
                h, subj, author, date = parts[0], parts[1], parts[2], parts[3]
                lines.append(f"{h}  {subj}  ({author}, {date})")
            else:
                lines.append(line)
        return "\n".join(lines) if lines else "No commits found."

    try:
        return await asyncio.to_thread(_do)
    except Exception as e:
        return f"git log error: {e}"


async def exec_git_show_commit(registry: ToolRegistry, inp: dict) -> str:
    """Show one commit: full message, author, date, and changed files."""
    ref = (inp.get("ref") or "").strip()
    if not ref:
        return "No ref provided (e.g. commit hash or branch name)."

    def _do() -> str:
        stdout, stderr, code = _git_show_commit(ref)
        if code != 0:
            return f"git show failed: {stderr.strip() or 'unknown error'}"
        return stdout

    try:
        return await asyncio.to_thread(_do)
    except Exception as e:
        return f"git show error: {e}"


async def exec_git_diff(registry: ToolRegistry, inp: dict) -> str:
    """Show unified diff for a commit or between two refs."""
    commit = (inp.get("commit") or "").strip() or None
    base = (inp.get("base") or "").strip() or None
    head = (inp.get("head") or "").strip() or None
    path = (inp.get("path") or "").strip() or None
    if commit and (base or head):
        return "Provide either 'commit' or 'base' and 'head', not both."
    if not commit and not (base and head):
        return "Provide either 'commit' or both 'base' and 'head'."

    def _do() -> str:
        stdout, stderr, code = _git_diff(commit, base, head, path)
        if code != 0:
            return f"git diff failed: {stderr.strip() or 'unknown error'}"
        return stdout if stdout else "(no diff)"

    try:
        return await asyncio.to_thread(_do)
    except Exception as e:
        return f"git diff error: {e}"


async def exec_git_status(registry: ToolRegistry, inp: dict) -> str:
    """Show current branch and short status (modified/untracked files)."""

    def _do() -> str:
        stdout, stderr, code = _git_status()
        if code != 0:
            return f"git status failed: {stderr.strip() or 'unknown error'}"
        return stdout

    try:
        return await asyncio.to_thread(_do)
    except Exception as e:
        return f"git status error: {e}"
