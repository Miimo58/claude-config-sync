"""Equality check, newest-wins decision, and manifest file iteration."""
import filecmp
import os
from typing import Iterator

from .manifest import is_excluded


def files_equal(path_a: str, path_b: str) -> bool:
    if not (os.path.isfile(path_a) and os.path.isfile(path_b)):
        return False
    return filecmp.cmp(path_a, path_b, shallow=False)


def newest_wins(local_exists: bool, repo_exists: bool, equal: bool,
                local_mtime: int, repo_ctime: int) -> str:
    """Return 'local', 'repo', or 'equal'.

    local_mtime: filesystem mtime (int) of the local file.
    repo_ctime: commit time (int) of the repo file's last change.
    """
    if not local_exists:
        return "repo"
    if not repo_exists:
        return "local"
    if equal:
        return "equal"
    return "repo" if repo_ctime > local_mtime else "local"


def iter_manifest_files(base_dir: str, entry_path: str,
                        excludes: list[str]) -> Iterator[str]:
    """Yield relpaths (posix-style, relative to base_dir) for a manifest entry.

    entry_path may be a file or a directory. Excluded segments are skipped.
    Missing paths yield nothing.
    """
    full = os.path.join(base_dir, entry_path)
    if is_excluded(entry_path, excludes):
        return
    if os.path.isfile(full):
        yield entry_path.replace("\\", "/")
        return
    if not os.path.isdir(full):
        return
    for root, dirs, files in os.walk(full):
        rel_root = os.path.relpath(root, base_dir)
        dirs[:] = [d for d in dirs
                   if not is_excluded(os.path.join(rel_root, d).replace("\\", "/"), excludes)]
        for name in files:
            rel = os.path.join(rel_root, name).replace("\\", "/")
            if not is_excluded(rel, excludes):
                yield rel
