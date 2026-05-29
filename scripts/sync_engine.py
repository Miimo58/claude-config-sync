#!/usr/bin/env python3
"""Claude config sync engine: setup | pull | push | status."""
import argparse
import json
import os
import shutil
import sys

# Allow running as `python3 scripts/sync_engine.py` and as an imported module.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lib import config, gitio, manifest, resolve, settingsmerge  # noqa: E402

ENGINE_DIR = os.path.dirname(os.path.abspath(__file__))
PLUGIN_ROOT = os.path.dirname(ENGINE_DIR)
DEFAULT_MANIFEST_FILE = os.path.join(PLUGIN_ROOT, "manifest.default.json")


def _is_settings_entry(entry: dict) -> bool:
    return entry.get("policy") == "merge" and entry["path"] == "settings.json"


def _copy_into_repo(claude_dir: str, sync_dir: str, man: dict) -> None:
    """Copy manifest files claude_dir -> sync_dir (honoring excludes).

    Skips the settings.json merge entry; settings are written separately.
    """
    excludes = man.get("global_excludes", [])
    for entry in man["entries"]:
        if _is_settings_entry(entry):
            continue
        for rel in resolve.iter_manifest_files(claude_dir, entry["path"], excludes):
            src = os.path.join(claude_dir, rel)
            dest = os.path.join(sync_dir, rel)
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            shutil.copy2(src, dest)


def _write_repo_settings(claude_dir: str, sync_dir: str) -> bool:
    """Write the canonical merged settings.json into the repo.

    Returns True if the repo file was changed.
    """
    local_path = os.path.join(claude_dir, "settings.json")
    repo_path = os.path.join(sync_dir, "settings.json")
    if not os.path.isfile(local_path):
        return False
    with open(local_path, encoding="utf-8") as fh:
        local = json.load(fh)
    repo = {}
    if os.path.isfile(repo_path):
        with open(repo_path, encoding="utf-8") as fh:
            repo = json.load(fh)
    merged = settingsmerge.merge_settings(local, repo, winner="local")
    if os.path.isfile(repo_path) and merged == repo:
        return False
    with open(repo_path, "w", encoding="utf-8") as fh:
        json.dump(merged, fh, indent=2)
    return True


def cmd_setup(remote_url: str, claude_dir: str, sync_dir: str,
              reconcile: bool = True) -> str:
    config.write_local_config(claude_dir, remote_url, sync_dir)
    if not os.path.isdir(os.path.join(sync_dir, ".git")):
        gitio.clone(remote_url, sync_dir)

    if gitio.is_empty_repo(sync_dir):
        # Seed the repo from this machine.
        shutil.copy2(DEFAULT_MANIFEST_FILE, os.path.join(sync_dir, "manifest.json"))
        man = manifest.load_manifest(sync_dir)
        _copy_into_repo(claude_dir, sync_dir, man)
        _write_repo_settings(claude_dir, sync_dir)
        if gitio.commit_all(sync_dir, "sync: seed config from first machine"):
            gitio.push(sync_dir)
        return "seeded"
    # Repo already has content: behave like a new machine.
    return cmd_pull(claude_dir, sync_dir, reconcile=reconcile)


def cmd_pull(claude_dir: str, sync_dir: str, reconcile: bool = True) -> dict:
    raise NotImplementedError


def cmd_push(claude_dir: str, sync_dir: str) -> dict:
    raise NotImplementedError


def cmd_status(claude_dir: str, sync_dir: str) -> dict:
    raise NotImplementedError


def main(argv: list[str] | None = None) -> int:
    raise NotImplementedError


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
