"""Key-aware merge for settings.json.

Non-special keys follow the newest-wins `winner` ('local' or 'repo').
`enabledPlugins` and `extraKnownMarketplaces` are unioned so every plugin or
marketplace known on any machine becomes *available* everywhere. For
`enabledPlugins` the **local machine's value always wins**, and a plugin new to
this machine defaults to `False` (installed-but-disabled). This is what makes a
plugin propagate as "available, disabled by default" while each machine's own
enabled/disabled choice is preserved across syncs.
"""
import copy
from typing import Any

UNION_KEYS = ("enabledPlugins", "extraKnownMarketplaces")


def merge_settings(local: dict[str, Any], repo: dict[str, Any],
                   winner: str) -> dict[str, Any]:
    """Return the merged settings dict. `winner` is 'local' or 'repo'."""
    base = copy.deepcopy(local if winner == "local" else repo)

    local_ep = local.get("enabledPlugins", {}) or {}
    repo_ep = repo.get("enabledPlugins", {}) or {}
    merged_ep: dict[str, bool] = {}
    for key in set(local_ep) | set(repo_ep):
        # Local value wins; a key new to this machine is written explicitly as
        # False (disabled). Writing it explicitly matters: an *absent* key would
        # fall back to the plugin's defaultEnabled (usually True = enabled).
        merged_ep[key] = local_ep[key] if key in local_ep else False
    base["enabledPlugins"] = merged_ep

    local_mk = local.get("extraKnownMarketplaces", {}) or {}
    repo_mk = repo.get("extraKnownMarketplaces", {}) or {}
    merged_mk: dict[str, Any] = {}
    for key in set(local_mk) | set(repo_mk):
        merged_mk[key] = local_mk[key] if key in local_mk else repo_mk[key]
    base["extraKnownMarketplaces"] = merged_mk

    return base
