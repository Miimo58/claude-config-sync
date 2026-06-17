import unittest
from scripts.lib import plugins


class FakeRunner:
    """Records every command; returns success for all of them."""
    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    def __call__(self, args: list[str]) -> tuple[int, str, str]:
        self.calls.append(args)
        return 0, "", ""


class TestPlugins(unittest.TestCase):
    def test_installs_then_disables_plugins_new_to_this_machine(self):
        runner = FakeRunner()
        merged = {
            "enabledPlugins": {"a@m1": True, "b@m2": False},
            "extraKnownMarketplaces": {},
        }
        # a@m1 is already known here; b@m2 is new (arrived from the repo).
        actions = plugins.reconcile(merged, known_marketplaces=set(),
                                    local_known_plugins={"a@m1"}, runner=runner)
        self.assertEqual(
            runner.calls,
            [["plugin", "install", "--scope", "user", "--", "b@m2"],
             ["plugin", "disable", "--scope", "user", "--", "b@m2"]],
        )
        self.assertTrue(any("install b@m2" in a for a in actions))
        self.assertTrue(any("disable b@m2" in a for a in actions))

    def test_known_plugins_are_never_touched(self):
        """A plugin this machine already manages must not be reinstalled/toggled."""
        runner = FakeRunner()
        merged = {"enabledPlugins": {"a@m1": False, "b@m2": True},
                  "extraKnownMarketplaces": {}}
        plugins.reconcile(merged, known_marketplaces=set(),
                          local_known_plugins={"a@m1", "b@m2"}, runner=runner)
        self.assertEqual(runner.calls, [], "no plugin commands for known plugins")

    def test_adds_missing_marketplaces(self):
        runner = FakeRunner()
        merged = {
            "enabledPlugins": {},
            "extraKnownMarketplaces": {
                "m2": {"source": {"source": "github", "repo": "owner/repo"}},
            },
        }
        plugins.reconcile(merged, known_marketplaces={"m1"},
                          local_known_plugins=set(), runner=runner)
        adds = [c for c in runner.calls if c[:3] == ["plugin", "marketplace", "add"]]
        self.assertEqual(adds, [["plugin", "marketplace", "add", "--", "owner/repo"]])

    def test_install_failure_is_caught_and_recorded(self):
        class Boom:
            def __call__(self, args: list[str]) -> tuple[int, str, str]:
                return 1, "", "boom"
        merged = {"enabledPlugins": {"b@m2": False}, "extraKnownMarketplaces": {}}
        actions = plugins.reconcile(merged, known_marketplaces=set(),
                                    local_known_plugins=set(), runner=Boom())
        self.assertTrue(any("FAILED" in a for a in actions))
