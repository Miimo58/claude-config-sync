#!/usr/bin/env python3
"""Claude config sync engine: setup | pull | push | status."""
import argparse
import json
import os
import shutil
import sys
import time

# Allow running as `python3 scripts/sync_engine.py` and as an imported module.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lib import (config, gitio, manifest, resolve, settingsmerge,  # noqa: E402
                 backup, secretscan, plugins)

ENGINE_DIR = os.path.dirname(os.path.abspath(__file__))
PLUGIN_ROOT = os.path.dirname(ENGINE_DIR)
DEFAULT_MANIFEST_FILE = os.path.join(PLUGIN_ROOT, "manifest.default.json")
DEFAULT_SYNC_DIR = os.path.expanduser("~/.claude-sync")


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

    Plugin names are synced so every machine can install the same set, but
    enabled/disabled state is local-only: all enabledPlugins values are stored
    as False in the repo regardless of this machine's choices, so one machine's
    `True` never auto-enables a plugin elsewhere. Returns True if the repo file
    was changed.
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
    repo_payload = {**merged}
    # Publish plugin names but never their enabled state: store every value as
    # False so a plugin lands installed-but-disabled on machines that pull it.
    if "enabledPlugins" in repo_payload:
        repo_payload["enabledPlugins"] = {k: False
                                          for k in repo_payload["enabledPlugins"]}
    if os.path.isfile(repo_path) and repo_payload == repo:
        return False
    with open(repo_path, "w", encoding="utf-8") as fh:
        json.dump(repo_payload, fh, indent=2)
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


def _apply_copy(claude_dir: str, sync_dir: str, rel: str, stamp: str) -> str:
    """Newest-wins copy for a single file. Returns 'repo'|'local'|'equal'|'new'."""
    # Guard against path traversal: destination must stay inside claude_dir.
    claude_root = os.path.realpath(claude_dir)
    local_path = os.path.realpath(os.path.join(claude_dir, rel))
    if not local_path.startswith(claude_root + os.sep):
        return "local"  # silently skip traversal attempts
    repo_path = os.path.join(sync_dir, rel)
    local_exists = os.path.isfile(local_path)
    repo_exists = os.path.isfile(repo_path)
    if not repo_exists:
        return "local"
    equal = resolve.files_equal(local_path, repo_path)
    local_mtime = int(os.path.getmtime(local_path)) if local_exists else 0
    repo_ctime = gitio.last_commit_time(sync_dir, rel) or 0
    decision = resolve.newest_wins(local_exists, repo_exists, equal,
                                   local_mtime, repo_ctime)
    if decision == "repo":
        if local_exists:
            backup.backup_file(claude_dir, rel, stamp)
        os.makedirs(os.path.dirname(local_path) or claude_dir, exist_ok=True)
        shutil.copy2(repo_path, local_path)
        return "new" if not local_exists else "repo"
    return decision


def _apply_settings_merge(claude_dir: str, sync_dir: str, rel: str,
                           stamp: str) -> dict:
    """Merge settings.json into local. Returns the merged dict."""
    local_path = os.path.join(claude_dir, rel)
    repo_path = os.path.join(sync_dir, rel)
    local_exists = os.path.isfile(local_path)
    repo_exists = os.path.isfile(repo_path)
    if not local_exists and not repo_exists:
        return {}
    local: dict = {}
    repo: dict = {}
    if local_exists:
        with open(local_path, encoding="utf-8") as fh:
            local = json.load(fh)
    if repo_exists:
        with open(repo_path, encoding="utf-8") as fh:
            repo = json.load(fh)
    local_mtime = int(os.path.getmtime(local_path)) if local_exists else 0
    repo_ctime = gitio.last_commit_time(sync_dir, rel) or 0
    equal = resolve.files_equal(local_path, repo_path)
    winner_raw = resolve.newest_wins(local_exists, repo_exists, equal,
                                     local_mtime, repo_ctime)
    winner = "local" if winner_raw in ("local", "equal") else "repo"
    merged = settingsmerge.merge_settings(local, repo, winner)
    if local_exists and merged == local:
        return merged
    if local_exists:
        backup.backup_file(claude_dir, rel, stamp)
    os.makedirs(os.path.dirname(local_path) or claude_dir, exist_ok=True)
    with open(local_path, "w", encoding="utf-8") as fh:
        json.dump(merged, fh, indent=2)
    return merged


def cmd_pull(claude_dir: str, sync_dir: str, reconcile: bool = True) -> dict:
    gitio.pull(sync_dir)
    man = manifest.load_manifest(sync_dir)
    excludes = man.get("global_excludes", [])
    stamp = time.strftime("%Y%m%d-%H%M%S")
    summary: dict = {"updated": 0, "kept": 0, "merged_settings": False}
    merged_settings: dict = {}

    # Snapshot what this machine already knows BEFORE the merge unions in the
    # repo's marketplaces/plugins, so reconcile can tell genuinely new arrivals
    # (install + disable) from plugins this machine already manages (leave alone).
    known_marketplaces: set = set()
    local_known_plugins: set = set()
    local_settings_path = os.path.join(claude_dir, "settings.json")
    if os.path.isfile(local_settings_path):
        try:
            with open(local_settings_path, encoding="utf-8") as fh:
                _local = json.load(fh)
            known_marketplaces = set(_local.get("extraKnownMarketplaces", {}) or {})
            local_known_plugins = set(_local.get("enabledPlugins", {}) or {})
        except (OSError, json.JSONDecodeError):
            pass

    for entry in man["entries"]:
        if entry.get("policy") == "merge" and entry["path"] == "settings.json":
            merged_settings = _apply_settings_merge(
                claude_dir, sync_dir, entry["path"], stamp)
            summary["merged_settings"] = True
            continue
        for rel in resolve.iter_manifest_files(sync_dir, entry["path"], excludes):
            decision = _apply_copy(claude_dir, sync_dir, rel, stamp)
            if decision in ("repo", "new"):
                summary["updated"] += 1
            else:
                summary["kept"] += 1

    if reconcile and merged_settings:
        try:
            actions = plugins.reconcile(merged_settings, known_marketplaces,
                                        local_known_plugins)
            for action in actions:
                _log(claude_dir, f"reconcile: {action}")
        except Exception as exc:  # noqa: BLE001
            _log(claude_dir, f"reconcile: WARNING {exc!r}")
    return summary


def _staged_manifest_files(sync_dir: str, man: dict) -> list[str]:
    """Absolute paths of all manifest files currently in the repo clone."""
    excludes = man.get("global_excludes", [])
    paths = []
    for entry in man["entries"]:
        for rel in resolve.iter_manifest_files(sync_dir, entry["path"], excludes):
            paths.append(os.path.join(sync_dir, rel))
    return paths


def cmd_push(claude_dir: str, sync_dir: str) -> dict:
    try:
        gitio.pull(sync_dir)
    except gitio.GitError:
        pass  # offline / first push; proceed and let push report
    man = manifest.load_manifest(sync_dir)

    _copy_into_repo(claude_dir, sync_dir, man)
    _write_repo_settings(claude_dir, sync_dir)

    findings = secretscan.scan_paths(_staged_manifest_files(sync_dir, man))
    if findings:
        # Discard staged changes so nothing leaks; best-effort — ignore errors.
        try:
            gitio._run(["checkout", "--", "."], cwd=sync_dir)
            gitio._run(["clean", "-fd"], cwd=sync_dir)
        except gitio.GitError:
            pass
        return {"status": "blocked", "findings": findings}

    if not gitio.commit_all(sync_dir, "sync: push config update"):
        return {"status": "nochange"}
    gitio.push(sync_dir)
    return {"status": "pushed"}


def _log(claude_dir: str, message: str) -> None:
    log_dir = os.path.join(claude_dir, "backups", "sync")
    os.makedirs(log_dir, exist_ok=True)
    stamp = time.strftime("%Y-%m-%dT%H:%M:%S")
    with open(os.path.join(log_dir, "sync.log"), "a", encoding="utf-8") as fh:
        fh.write(f"{stamp} {message}\n")


def cmd_status(claude_dir: str, sync_dir: str) -> dict:
    cfg = config.load_local_config(claude_dir)
    status: dict = {
        "configured": cfg is not None,
        "remote_url": cfg["remote_url"] if cfg else None,
        "sync_dir": sync_dir,
        "pending": 0,
        "branch": None,
    }
    if os.path.isdir(os.path.join(sync_dir, ".git")):
        out = gitio._run(["status", "-sb"], cwd=sync_dir)
        lines = out.splitlines()
        if lines:
            status["branch"] = lines[0]
        status["pending"] = max(0, len(lines) - 1)
    return status


def _resolve_claude_dir(args: argparse.Namespace) -> str:
    if args.claude_dir:
        return args.claude_dir
    return os.environ.get("CLAUDE_CONFIG_DIR") or os.path.expanduser("~/.claude")


def _resolve_sync_dir(args: argparse.Namespace, claude_dir: str) -> str:
    cfg = config.load_local_config(claude_dir)
    if cfg and cfg.get("sync_dir"):
        return cfg["sync_dir"]
    return args.sync_dir or DEFAULT_SYNC_DIR


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="sync_engine")
    parser.add_argument("command", choices=["setup", "pull", "push", "status"])
    parser.add_argument("remote_url", nargs="?")
    parser.add_argument("--claude-dir", default=None)
    parser.add_argument("--sync-dir", default=None)
    args = parser.parse_args(argv)

    claude_dir = _resolve_claude_dir(args)
    sync_dir = _resolve_sync_dir(args, claude_dir)

    if args.command == "setup":
        if not args.remote_url:
            print("usage: sync_engine setup <git-remote-url>", file=sys.stderr)
            return 2
        cmd_setup(args.remote_url, claude_dir, sync_dir)
        print(f"[sync] configured with remote {args.remote_url}")
        return 0

    if args.command == "status":
        st = cmd_status(claude_dir, sync_dir)
        print(json.dumps(st, indent=2))
        return 0

    # pull / push: never break a session.
    cfg = config.load_local_config(claude_dir)
    if cfg is None:
        _log(claude_dir, f"{args.command}: skipped (sync not configured)")
        return 0
    try:
        if args.command == "pull":
            summary = cmd_pull(claude_dir, sync_dir)
        else:
            summary = cmd_push(claude_dir, sync_dir)
        _log(claude_dir, f"{args.command}: {summary}")
        if isinstance(summary, dict) and summary.get("status") == "blocked":
            print("[sync] push BLOCKED: possible secret detected; not pushed. "
                  "See backups/sync/sync.log")
    except Exception as exc:  # noqa: BLE001
        _log(claude_dir, f"{args.command}: ERROR {exc!r}")
        print(f"[sync] {args.command} skipped ({exc})")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
