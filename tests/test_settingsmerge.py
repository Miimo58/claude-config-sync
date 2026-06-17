import unittest
from scripts.lib import settingsmerge


class TestSettingsMerge(unittest.TestCase):
    def test_enabled_plugins_are_local_only_repo_ignored(self):
        local = {"enabledPlugins": {"a@m": True, "b@m": False}}
        repo = {"enabledPlugins": {"a@m": False, "c@m": True}}
        # Even when the repo is the newest-wins winner, enabledPlugins stays local.
        merged = settingsmerge.merge_settings(local, repo, winner="repo")
        ep = merged["enabledPlugins"]
        self.assertEqual(ep, {"a@m": True, "b@m": False})  # local preserved verbatim
        self.assertNotIn("c@m", ep)                        # repo's plugin never added

    def test_enabled_plugins_dropped_when_local_has_none(self):
        local = {"model": "opus"}
        repo = {"enabledPlugins": {"c@m": True}}
        merged = settingsmerge.merge_settings(local, repo, winner="repo")
        self.assertNotIn("enabledPlugins", merged)  # repo's value must not leak in

    def test_marketplaces_union_local_wins(self):
        local = {"extraKnownMarketplaces": {"m1": {"source": {"repo": "x/local"}}}}
        repo = {"extraKnownMarketplaces": {"m1": {"source": {"repo": "x/repo"}},
                                            "m2": {"source": {"repo": "y/repo"}}}}
        merged = settingsmerge.merge_settings(local, repo, winner="repo")
        mk = merged["extraKnownMarketplaces"]
        self.assertEqual(mk["m1"]["source"]["repo"], "x/local")  # local wins
        self.assertIn("m2", mk)                                   # union

    def test_other_keys_follow_winner(self):
        local = {"model": "opus", "theme": "dark"}
        repo = {"model": "sonnet", "theme": "light"}
        self.assertEqual(settingsmerge.merge_settings(local, repo, "repo")["model"], "sonnet")
        self.assertEqual(settingsmerge.merge_settings(local, repo, "local")["model"], "opus")

    def test_missing_special_keys_default_to_empty(self):
        merged = settingsmerge.merge_settings({}, {}, "local")
        self.assertNotIn("enabledPlugins", merged)  # local-only, absent when unset
        self.assertEqual(merged["extraKnownMarketplaces"], {})

    def test_local_enabled_plugins_preserved_verbatim(self):
        local = {"enabledPlugins": {"a@m": True}}
        merged = settingsmerge.merge_settings(local, {}, "local")
        self.assertEqual(merged["enabledPlugins"], {"a@m": True})
