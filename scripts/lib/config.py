"""Machine-local (never-synced) config: remote URL + clone path."""
import json
import os
from typing import Any, Optional

FILENAME = "sync-plugin.local.json"


def config_path(claude_dir: str) -> str:
    """Return the path to the local config file."""
    return os.path.join(claude_dir, FILENAME)


def load_local_config(claude_dir: str) -> Optional[dict[str, Any]]:
    """Return the local config dict, or None if setup has not run."""
    path = config_path(claude_dir)
    if not os.path.isfile(path):
        return None
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def write_local_config(claude_dir: str, remote_url: str, sync_dir: str) -> None:
    """Write the local config to disk."""
    os.makedirs(claude_dir, exist_ok=True)
    data = {"remote_url": remote_url, "sync_dir": sync_dir}
    with open(config_path(claude_dir), "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2)
