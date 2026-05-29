"""Shared test fixtures: temp dirs and local bare-repo helpers (no network)."""
import os
import shutil
import subprocess
import tempfile
from subprocess import CompletedProcess
from typing import Any

GIT_ENV = {
    **os.environ,
    "GIT_AUTHOR_NAME": "Test",
    "GIT_AUTHOR_EMAIL": "test@example.com",
    "GIT_COMMITTER_NAME": "Test",
    "GIT_COMMITTER_EMAIL": "test@example.com",
}


def git(repo_dir: str, *args: str) -> CompletedProcess[str]:
    """Run a git command in repo_dir with a deterministic identity."""
    return subprocess.run(
        ["git", "-C", repo_dir, *args],
        env=GIT_ENV, capture_output=True, text=True, check=True,
    )


def make_bare_remote(parent: str) -> str:
    """Create a bare repo to stand in for the private remote. Returns its path."""
    remote = os.path.join(parent, "remote.git")
    subprocess.run(["git", "init", "--bare", "-b", "main", remote],
                   env=GIT_ENV, capture_output=True, text=True, check=True)
    return remote


class TempEnv:
    """Context manager yielding (root, claude_dir, sync_dir, remote_url)."""
    def __enter__(self) -> "TempEnv":
        self.root = tempfile.mkdtemp(prefix="syncplugin-test-")
        self.claude_dir = os.path.join(self.root, "claude")
        self.sync_dir = os.path.join(self.root, "claude-sync")
        os.makedirs(self.claude_dir, exist_ok=True)
        remote = make_bare_remote(self.root)
        self.remote_url = "file://" + remote
        return self

    def write(self, relpath: str, content: str) -> str:
        """Write a file under claude_dir, creating parent dirs."""
        full = os.path.join(self.claude_dir, relpath)
        parent = os.path.dirname(full)
        if parent:
            os.makedirs(parent, exist_ok=True)
        with open(full, "w") as fh:
            fh.write(content)
        return full

    def read(self, relpath: str) -> str:
        with open(os.path.join(self.claude_dir, relpath)) as fh:
            return fh.read()

    def __exit__(self, *exc: Any) -> None:
        shutil.rmtree(self.root, ignore_errors=True)
