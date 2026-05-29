"""Thin git wrappers with timeouts. All functions raise GitError on failure."""
import os
import subprocess
from typing import Optional

DEFAULT_TIMEOUT = 20  # seconds; keeps SessionStart from hanging

_ENV = {
    **os.environ,
    "GIT_TERMINAL_PROMPT": "0",  # never block on credential prompts
}


class GitError(RuntimeError):
    pass


def _run(args: list[str], cwd: Optional[str] = None,
         timeout: int = DEFAULT_TIMEOUT) -> str:
    try:
        proc = subprocess.run(
            ["git", *args], cwd=cwd, env=_ENV,
            capture_output=True, text=True, timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        raise GitError(f"git timed out: {' '.join(args)}") from exc
    if proc.returncode != 0:
        raise GitError(proc.stderr.strip() or f"git failed: {' '.join(args)}")
    return proc.stdout


def _validate_remote_url(remote_url: str) -> None:
    """Reject values that could be interpreted as git flags."""
    if remote_url.startswith("-"):
        raise GitError(f"invalid remote URL: {remote_url!r}")


def clone(remote_url: str, dest: str, timeout: int = DEFAULT_TIMEOUT) -> None:
    _validate_remote_url(remote_url)
    _run(["clone", "--", remote_url, dest], timeout=timeout)


def is_empty_repo(repo_dir: str) -> bool:
    """True if HEAD has no commits yet."""
    proc = subprocess.run(["git", "-C", repo_dir, "rev-parse", "HEAD"],
                          env=_ENV, capture_output=True, text=True)
    return proc.returncode != 0


def commit_all(repo_dir: str, message: str) -> bool:
    """Stage everything and commit. Returns True if a commit was made."""
    _run(["add", "-A"], cwd=repo_dir)
    status = _run(["status", "--porcelain"], cwd=repo_dir)
    if not status.strip():
        return False
    _run(["-c", "user.email=sync@local", "-c", "user.name=claude-config-sync",
          "commit", "-m", message], cwd=repo_dir)
    return True


def pull(repo_dir: str, timeout: int = DEFAULT_TIMEOUT) -> None:
    _run(["pull", "--ff-only"], cwd=repo_dir, timeout=timeout)


def push(repo_dir: str, timeout: int = DEFAULT_TIMEOUT) -> None:
    branch = _run(["rev-parse", "--abbrev-ref", "HEAD"], cwd=repo_dir).strip()
    _run(["push", "-u", "origin", branch], cwd=repo_dir, timeout=timeout)


def last_commit_time(repo_dir: str, relpath: str) -> Optional[int]:
    """Unix timestamp (int) of the last commit touching relpath, or None."""
    proc = subprocess.run(
        ["git", "-C", repo_dir, "log", "-1", "--format=%ct", "--", relpath],
        env=_ENV, capture_output=True, text=True,
    )
    out = proc.stdout.strip()
    if proc.returncode != 0 or not out:
        return None
    return int(out)
