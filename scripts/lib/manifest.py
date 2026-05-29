"""Manifest: the explicit allowlist of paths to sync, plus global excludes."""
import copy
import fnmatch
import json
import os
from typing import Any

DEFAULT_MANIFEST: dict[str, Any] = {
    "version": 1,
    "entries": [
        {"path": "settings.json", "policy": "merge"},
        {"path": "CLAUDE.md", "policy": "copy"},
        {"path": "AGENTS.md", "policy": "copy"},
        {"path": "agents", "policy": "copy"},
        {"path": "commands", "policy": "copy"},
        {"path": "rules", "policy": "copy"},
        {"path": "hooks", "policy": "copy"},
        {"path": "scripts", "policy": "copy"},
        {"path": "skills", "policy": "copy"},
        {"path": "mcp-configs", "policy": "copy"},
    ],
    "global_excludes": [
        ".DS_Store",
        "*.log",
        "sessions",
        "projects",
        "cache",
        "security",
        "backups",
        "file-history",
        "session-data",
        "session-env",
        "ide",
    ],
}


def load_manifest(sync_dir: str) -> dict[str, Any]:
    """Load <sync_dir>/manifest.json, or return DEFAULT_MANIFEST if absent."""
    path = os.path.join(sync_dir, "manifest.json")
    if not os.path.isfile(path):
        return copy.deepcopy(DEFAULT_MANIFEST)
    with open(path, encoding="utf-8") as fh:
        try:
            return json.load(fh)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Manifest at {path!r} is not valid JSON: {exc}") from exc


def is_excluded(relpath: str, excludes: list[str]) -> bool:
    """True if any path segment matches an exclude name or glob pattern."""
    segments = relpath.replace("\\", "/").split("/")
    for pattern in excludes:
        for seg in segments:
            if fnmatch.fnmatch(seg, pattern):
                return True
    return False
