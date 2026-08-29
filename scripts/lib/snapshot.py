"""What was in sync last time: the memory that makes deletions propagate.

Without it the engine cannot tell "I deleted this" from "I never had this",
so a delete on one machine is silently undone by the next pull. The snapshot
records every manifest file present in BOTH the local config and the repo at
the end of the last successful sync, with a hash of its content.

Machine-local, like sync-plugin.local.json: it is never listed in the manifest
and so never travels to the repo.
"""
import hashlib
import json
import os
from typing import Any

from .manifest import is_excluded
from .resolve import iter_manifest_files

FILENAME = "sync-snapshot.local.json"
VERSION = 1
_CHUNK = 65536


def path(claude_dir: str) -> str:
    """Return the path to the snapshot file."""
    return os.path.join(claude_dir, FILENAME)


def hash_file(file_path: str) -> str:
    """Return the SHA-256 of a file's content."""
    digest = hashlib.sha256()
    with open(file_path, "rb") as fh:
        for chunk in iter(lambda: fh.read(_CHUNK), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load(claude_dir: str) -> dict[str, str]:
    """Return {relpath: sha256} from the last sync.

    Returns {} when the file is absent or unreadable. An empty snapshot means
    "this machine remembers nothing", which makes every delete rule a no-op —
    the safe answer for a first run or a damaged file.
    """
    try:
        with open(path(claude_dir), encoding="utf-8") as fh:
            data: Any = json.load(fh)
    except (OSError, json.JSONDecodeError):
        return {}
    files = data.get("files") if isinstance(data, dict) else None
    if not isinstance(files, dict):
        return {}
    return {k: v for k, v in files.items() if isinstance(k, str) and isinstance(v, str)}


def save(claude_dir: str, files: dict[str, str]) -> None:
    """Write the snapshot for this machine."""
    os.makedirs(claude_dir, exist_ok=True)
    payload = {"version": VERSION, "files": files}
    with open(path(claude_dir), "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, sort_keys=True)


def _copy_entries(man: dict) -> list[str]:
    """Manifest paths that sync by copy. settings.json merges, so it is excluded:
    it is never absent-because-deleted, and must never be delete-tracked."""
    return [entry["path"] for entry in man["entries"]
            if not (entry.get("policy") == "merge" and entry["path"] == "settings.json")]


def build(claude_dir: str, sync_dir: str, man: dict) -> dict[str, str]:
    """Return the in-sync set: manifest files in both trees, hashed from local.

    A file only one side has is not in sync — it is either not pushed yet or
    not applied yet — so it stays out of the snapshot and no delete rule can
    fire on it later.
    """
    excludes = man.get("global_excludes", [])
    files: dict[str, str] = {}
    for entry_path in _copy_entries(man):
        for rel in iter_manifest_files(claude_dir, entry_path, excludes):
            if not os.path.isfile(os.path.join(sync_dir, rel)):
                continue
            try:
                files[rel] = hash_file(os.path.join(claude_dir, rel))
            except OSError:
                continue
    return files


def deleted_since(known: dict[str, str], base_dir: str) -> list[str]:
    """Snapshot paths that no longer exist under base_dir."""
    return sorted(rel for rel in known
                  if not os.path.isfile(os.path.join(base_dir, rel)))


def prune_empty_dirs(base_dir: str, man: dict) -> None:
    """Remove directories left empty under each manifest entry root.

    An emptied skills/<name>/ directory is not harmless: tools that scan the
    config directory would still see the folder. The entry root itself may go;
    base_dir never does.
    """
    excludes = man.get("global_excludes", [])
    for entry_path in _copy_entries(man):
        if is_excluded(entry_path, excludes):
            continue
        root = os.path.join(base_dir, entry_path)
        if not os.path.isdir(root):
            continue
        for current, dirs, files in os.walk(root, topdown=False):
            if not dirs and not files:
                try:
                    os.rmdir(current)
                except OSError:
                    pass
