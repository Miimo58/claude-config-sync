import json
import unittest
from scripts.lib import plugins


class FakeRunner:
    """Records commands; returns canned output for `list --json`."""
    def __init__(self, installed: list[str]) -> None:
        self._installed = installed
        self.calls: list[list[str]] = []

    def __call__(self, args: list[str]) -> tuple[int, str, str]:
        self.calls.append(args)
        if args[:3] == ["plugin", "list", "--json"]:
            payload = [{"name": k.split("@")[0], "marketplace": k.split("@")[1]}
                       for k in self._installed]
            return 0, json.dumps(payload), ""
        return 0, "", ""


class TestPlugins(unittest.TestCase):
    def test_never_installs_plugins(self):
        """Plugins are machine-local: reconcile must not install any plugin."""
        runner = FakeRunner(installed=["a@m1"])
        merged = {
            "enabledPlugins": {"a@m1": True, "b@m2": False},
            "extraKnownMarketplaces": {},
        }
        actions = plugins.reconcile(merged, known_marketplaces=set(), runner=runner)
        installs = [c for c in runner.calls if c[:2] == ["plugin", "install"]]
        self.assertEqual(installs, [])
        self.assertFalse(any("install" in a for a in actions))

    def test_adds_missing_marketplaces(self):
        runner = FakeRunner(installed=[])
        merged = {
            "enabledPlugins": {},
            "extraKnownMarketplaces": {
                "m2": {"source": {"source": "github", "repo": "owner/repo"}},
            },
        }
        actions = plugins.reconcile(merged, known_marketplaces={"m1"}, runner=runner)
        adds = [c for c in runner.calls if c[:3] == ["plugin", "marketplace", "add"]]
        self.assertEqual(adds, [["plugin", "marketplace", "add", "--", "owner/repo"]])

    def test_runner_error_is_caught_and_recorded(self):
        class Boom:
            def __call__(self, args: list[str]) -> tuple[int, str, str]:
                return 1, "", "boom"
        merged = {
            "enabledPlugins": {},
            "extraKnownMarketplaces": {
                "m2": {"source": {"source": "github", "repo": "owner/repo"}},
            },
        }
        actions = plugins.reconcile(merged, known_marketplaces=set(), runner=Boom())
        self.assertTrue(any("FAILED" in a for a in actions))
