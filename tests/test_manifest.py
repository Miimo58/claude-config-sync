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
        d = tempfile.mkdtemp()
        data = {"version": 1, "entries": [{"path": "X.md", "policy": "copy"}],
                "global_excludes": [".DS_Store"]}
        with open(os.path.join(d, "manifest.json"), "w") as fh:
            json.dump(data, fh)
        loaded = manifest.load_manifest(d)
        self.assertEqual(loaded["entries"][0]["path"], "X.md")

    def test_load_manifest_falls_back_to_default(self):
        d = tempfile.mkdtemp()  # no manifest.json
        loaded = manifest.load_manifest(d)
        self.assertEqual(loaded, manifest.DEFAULT_MANIFEST)

    def test_is_excluded_matches_name_and_glob(self):
        excludes = [".DS_Store", "*.log", "cache"]
        self.assertTrue(manifest.is_excluded("scripts/.DS_Store", excludes))
        self.assertTrue(manifest.is_excluded("foo/bar.log", excludes))
        self.assertTrue(manifest.is_excluded("cache", excludes))
        self.assertTrue(manifest.is_excluded("cache/x", excludes))
        self.assertFalse(manifest.is_excluded("scripts/run.js", excludes))
