import unittest
from scripts.lib import settingsmerge


class TestSettingsMerge(unittest.TestCase):
    def test_enabled_plugins_union_local_value_wins_new_keys_disabled(self):
        local = {"enabledPlugins": {"a@m": True, "b@m": False}}
        repo = {"enabledPlugins": {"a@m": False, "c@m": True}}
        merged = settingsmerge.merge_settings(local, repo, winner="repo")
        ep = merged["enabledPlugins"]
        self.assertEqual(ep["a@m"], True)    # local value wins over repo's False
        self.assertEqual(ep["b@m"], False)   # local-only choice preserved
        self.assertEqual(ep["c@m"], False)   # new from repo -> available but disabled
        self.assertEqual(set(ep), {"a@m", "b@m", "c@m"})  # union of names

    def test_repo_only_plugin_lands_disabled_even_when_repo_had_true(self):
        local = {"model": "opus"}
        repo = {"enabledPlugins": {"c@m": True}}
        merged = settingsmerge.merge_settings(local, repo, winner="repo")
        # The name propagates so it is available, but explicitly disabled here.
        self.assertEqual(merged["enabledPlugins"], {"c@m": False})

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
        self.assertEqual(merged["enabledPlugins"], {})
        self.assertEqual(merged["extraKnownMarketplaces"], {})

    def test_local_enabled_plugins_preserved_verbatim(self):
        local = {"enabledPlugins": {"a@m": True}}
        merged = settingsmerge.merge_settings(local, {}, "local")
        self.assertEqual(merged["enabledPlugins"], {"a@m": True})
