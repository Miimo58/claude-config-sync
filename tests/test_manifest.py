import json
import os
import tempfile
import unittest
from scripts.lib import manifest


class TestManifest(unittest.TestCase):
    def test_default_manifest_has_settings_merge_policy(self):
        entries = {e["path"]: e["policy"] for e in manifest.DEFAULT_MANIFEST["entries"]}
        self.assertEqual(entries["settings.json"], "merge")
        self.assertEqual(entries["CLAUDE.md"], "copy")

    def test_load_manifest_reads_file_when_present(self):
        with tempfile.TemporaryDirectory() as d:
            data = {"version": 1, "entries": [{"path": "X.md", "policy": "copy"}],
                    "global_excludes": [".DS_Store"]}
            with open(os.path.join(d, "manifest.json"), "w", encoding="utf-8") as fh:
                json.dump(data, fh)
            loaded = manifest.load_manifest(d)
            self.assertEqual(loaded["entries"][0]["path"], "X.md")

    def test_load_manifest_falls_back_to_default(self):
        with tempfile.TemporaryDirectory() as d:
            loaded = manifest.load_manifest(d)
            self.assertEqual(loaded, manifest.DEFAULT_MANIFEST)

    def test_load_manifest_default_is_a_copy(self):
        with tempfile.TemporaryDirectory() as d:
            loaded = manifest.load_manifest(d)
            loaded["entries"].append({"path": "EXTRA.md", "policy": "copy"})
            # Mutating the returned copy must not affect the module constant
            self.assertNotEqual(loaded, manifest.DEFAULT_MANIFEST)

    def test_load_manifest_raises_on_malformed_json(self):
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "manifest.json"), "w", encoding="utf-8") as fh:
                fh.write("{not valid json")
            with self.assertRaises(ValueError):
                manifest.load_manifest(d)

    def test_is_excluded_matches_name_and_glob(self):
        excludes = [".DS_Store", "*.log", "cache"]
        self.assertTrue(manifest.is_excluded("scripts/.DS_Store", excludes))
        self.assertTrue(manifest.is_excluded("foo/bar.log", excludes))
        self.assertTrue(manifest.is_excluded("cache", excludes))
        self.assertTrue(manifest.is_excluded("cache/x", excludes))
        self.assertFalse(manifest.is_excluded("scripts/run.js", excludes))
