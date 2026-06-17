"""Key-aware merge for settings.json.

Non-special keys follow the newest-wins `winner` ('local' or 'repo').
`enabledPlugins` is **machine-local only**: it is never synced, so the merged
result always preserves this machine's own value verbatim (neither the set of
installed plugins nor their enabled/disabled state propagates between machines).
`extraKnownMarketplaces` is unioned so marketplace sources known on any machine
are available everywhere.
"""
import copy
from typing import Any

UNION_KEYS = ("extraKnownMarketplaces",)


def merge_settings(local: dict[str, Any], repo: dict[str, Any],
                   winner: str) -> dict[str, Any]:
    """Return the merged settings dict. `winner` is 'local' or 'repo'."""
    base = copy.deepcopy(local if winner == "local" else repo)

    # enabledPlugins is local-only: the repo's value is ignored entirely and
    # this machine's value is preserved exactly, so local plugin state sticks.
    if "enabledPlugins" in local:
        base["enabledPlugins"] = copy.deepcopy(local["enabledPlugins"])
    else:
        base.pop("enabledPlugins", None)

    local_mk = local.get("extraKnownMarketplaces", {}) or {}
    repo_mk = repo.get("extraKnownMarketplaces", {}) or {}
    merged_mk: dict[str, Any] = {}
    for key in set(local_mk) | set(repo_mk):
        merged_mk[key] = local_mk[key] if key in local_mk else repo_mk[key]
    base["extraKnownMarketplaces"] = merged_mk

    return base
