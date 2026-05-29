"""Reconcile installed plugins/marketplaces against the merged desired state."""
import json
import subprocess
from typing import Any, Callable, Optional, Set

RunnerType = Callable[[list[str]], tuple[int, str, str]]


def default_runner(args: list[str]) -> tuple[int, str, str]:
    """Run `claude <args>`; return (returncode, stdout, stderr)."""
    proc = subprocess.run(["claude", *args], capture_output=True, text=True)
    return proc.returncode, proc.stdout, proc.stderr


def installed_plugins(runner: RunnerType) -> set[str]:
    """Return a set of 'name@marketplace' from `claude plugin list --json`."""
    rc, out, _ = runner(["plugin", "list", "--json"])
    if rc != 0 or not out.strip():
        return set()
    try:
        data = json.loads(out)
    except json.JSONDecodeError:
        return set()
    result: set[str] = set()
    for item in data:
        name = item.get("name")
        market = item.get("marketplace")
        if name and market:
            result.add(f"{name}@{market}")
    return result


def reconcile(merged_settings: dict[str, Any], known_marketplaces: set[str],
              runner: RunnerType = default_runner) -> list[str]:
    """Add missing marketplaces and install missing plugins. Returns action log."""
    actions: list[str] = []
    marketplaces = merged_settings.get("extraKnownMarketplaces", {}) or {}
    for name, spec in marketplaces.items():
        if name in known_marketplaces:
            continue
        repo = (spec.get("source") or {}).get("repo")
        if not repo:
            actions.append(f"SKIP marketplace {name}: no repo in source")
            continue
        rc, _, err = runner(["plugin", "marketplace", "add", repo])
        actions.append(f"marketplace add {repo}"
                       + ("" if rc == 0 else f" FAILED: {err.strip()}"))

    installed = installed_plugins(runner)
    enabled = merged_settings.get("enabledPlugins", {}) or {}
    for key in enabled:
        if key in installed:
            continue
        rc, _, err = runner(["plugin", "install", key, "--scope", "user"])
        actions.append(f"install {key}"
                       + ("" if rc == 0 else f" FAILED: {err.strip()}"))
    return actions
