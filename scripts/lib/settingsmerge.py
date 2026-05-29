"""Key-aware merge for settings.json.

Non-special keys follow the newest-wins `winner` ('local' or 'repo').
`enabledPlugins` and `extraKnownMarketplaces` are unioned so that every plugin
or marketplace known on any machine is available everywhere, while each machine
keeps its own enabled/disabled choices.
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
        # Local value wins; a key new to this machine defaults to disabled.
        merged_ep[key] = local_ep[key] if key in local_ep else False
    base["enabledPlugins"] = merged_ep

    local_mk = local.get("extraKnownMarketplaces", {}) or {}
    repo_mk = repo.get("extraKnownMarketplaces", {}) or {}
    merged_mk: dict[str, Any] = {}
    for key in set(local_mk) | set(repo_mk):
        merged_mk[key] = local_mk[key] if key in local_mk else repo_mk[key]
    base["extraKnownMarketplaces"] = merged_mk

    return base
