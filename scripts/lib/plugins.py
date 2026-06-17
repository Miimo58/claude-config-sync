"""Reconcile known marketplaces against the merged desired state.

Plugins themselves are machine-local and are never auto-installed: only
marketplace *sources* are reconciled so a manually installed plugin can be
found. Each machine independently decides which plugins to install/enable.
"""
import re
import subprocess
from typing import Any, Callable

RunnerType = Callable[[list[str]], tuple[int, str, str]]

# Allowlist: name@marketplace keys and repo slugs must not start with '-' or
# contain shell-special characters that could smuggle flags into the CLI.
_SAFE_VALUE_RE = re.compile(r"^[A-Za-z0-9_./@:+-]+$")


def default_runner(args: list[str]) -> tuple[int, str, str]:
    """Run `claude <args>`; return (returncode, stdout, stderr)."""
    proc = subprocess.run(["claude", *args], capture_output=True, text=True)
    return proc.returncode, proc.stdout, proc.stderr


def reconcile(merged_settings: dict[str, Any], known_marketplaces: set[str],
              runner: RunnerType = default_runner) -> list[str]:
    """Add missing marketplaces. Returns action log.

    Plugins are intentionally NOT installed here: plugin state is machine-local,
    so each machine decides for itself which plugins to install and enable.
    """
    actions: list[str] = []
    marketplaces = merged_settings.get("extraKnownMarketplaces", {}) or {}
    for name, spec in marketplaces.items():
        if name in known_marketplaces:
            continue
        repo = (spec.get("source") or {}).get("repo")
        if not repo:
            actions.append(f"SKIP marketplace {name}: no repo in source")
            continue
        if not _SAFE_VALUE_RE.match(repo):
            actions.append(f"SKIP marketplace {name}: unsafe repo value {repo!r}")
            continue
        rc, _, err = runner(["plugin", "marketplace", "add", "--", repo])
        actions.append(f"marketplace add {repo}"
                       + ("" if rc == 0 else f" FAILED: {err.strip()}"))
    return actions
