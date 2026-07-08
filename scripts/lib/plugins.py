"""Reconcile marketplaces and plugins against the merged desired state.

Plugin *names* propagate across machines (via the unioned ``enabledPlugins`` in
settings.json) so a plugin installed on one machine becomes available on all of
them. Each machine's enabled/disabled choice, however, stays local. Reconcile
therefore:

* installs a plugin only when it is genuinely NEW to this machine, and disables
  it immediately so propagated plugins land "available, disabled by default";
* never touches a plugin this machine already manages, so a locally
  enabled/disabled choice sticks across sessions.

The install/skip decision is driven by the machine's pre-pull ``enabledPlugins``
keys, not by parsing ``claude plugin list`` output, so it does not depend on
that command's reporting of disabled plugins.
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
              local_known_plugins: set[str],
              runner: RunnerType = default_runner) -> list[str]:
    """Add missing marketplaces and install plugins new to this machine.

    ``known_marketplaces`` / ``local_known_plugins`` describe what this machine
    already had *before* the pull merged in the repo's state. Returns an action
    log. Plugins this machine already manages are left untouched so local
    enabled/disabled state is preserved.
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

    enabled = merged_settings.get("enabledPlugins", {}) or {}
    for key in enabled:
        if key in local_known_plugins:
            # Already managed here: leave the local enabled/disabled choice as-is.
            continue
        if not _SAFE_VALUE_RE.match(key):
            actions.append(f"SKIP install {key!r}: unsafe plugin key")
            continue
        rc, _, err = runner(["plugin", "install", "--scope", "user", "--", key])
        if rc != 0:
            actions.append(f"install {key} FAILED: {err.strip()}")
            continue
        actions.append(f"install {key}")
        # Plugins install enabled by default and there is no install-disabled
        # flag, so explicitly disable propagated plugins: available, off by default.
        rc, _, err = runner(["plugin", "disable", "--scope", "user", "--", key])
        actions.append(f"disable {key}"
                       + ("" if rc == 0 else f" FAILED: {err.strip()}"))
    return actions
