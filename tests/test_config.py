import os
import tempfile
import unittest
from scripts.lib import config


class TestConfig(unittest.TestCase):
    def test_load_returns_none_when_missing(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertIsNone(config.load_local_config(d))

    def test_write_then_load_roundtrip(self):
        with tempfile.TemporaryDirectory() as d:
            config.write_local_config(d, "file:///tmp/r.git", "/tmp/sync")
            loaded = config.load_local_config(d)
            self.assertEqual(loaded["remote_url"], "file:///tmp/r.git")
            self.assertEqual(loaded["sync_dir"], "/tmp/sync")

    def test_config_path_is_under_claude_dir(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(
                config.config_path(d),
                os.path.join(d, "sync-plugin.local.json"),
            )
