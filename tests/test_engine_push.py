import json
import os
import subprocess
import unittest
from scripts import sync_engine
from scripts.lib import gitio, config
from tests.helpers import TempEnv, GIT_ENV


class TestEnginePush(unittest.TestCase):
    def _setup_seeded(self, env):
        env.write("CLAUDE.md", "v1")
        env.write("settings.json", json.dumps({"model": "opus",
                                               "enabledPlugins": {"a@m": True}}))
        sync_engine.cmd_setup(env.remote_url, env.claude_dir, env.sync_dir)

    def test_push_publishes_local_change(self):
        with TempEnv() as env:
            self._setup_seeded(env)
            env.write("CLAUDE.md", "v2")
            res = sync_engine.cmd_push(env.claude_dir, env.sync_dir)
            self.assertEqual(res["status"], "pushed")
            dest = os.path.join(env.root, "verify")
            subprocess.run(["git", "clone", env.remote_url, dest],
                           env=GIT_ENV, capture_output=True, text=True, check=True)
            with open(os.path.join(dest, "CLAUDE.md"), encoding="utf-8") as fh:
                self.assertEqual(fh.read(), "v2")

    def test_push_blocks_on_secret(self):
        with TempEnv() as env:
            self._setup_seeded(env)
            env.write("CLAUDE.md", "token ghp_ABCDEFGHIJ1234567890abcd")
            res = sync_engine.cmd_push(env.claude_dir, env.sync_dir)
            self.assertEqual(res["status"], "blocked")
            # remote must NOT contain the secret
            dest = os.path.join(env.root, "verify2")
            subprocess.run(["git", "clone", env.remote_url, dest],
                           env=GIT_ENV, capture_output=True, text=True, check=True)
            with open(os.path.join(dest, "CLAUDE.md"), encoding="utf-8") as fh:
                self.assertEqual(fh.read(), "v1")

    def test_push_noop_when_no_change(self):
        with TempEnv() as env:
            self._setup_seeded(env)
            res = sync_engine.cmd_push(env.claude_dir, env.sync_dir)
            self.assertEqual(res["status"], "nochange")

    def test_push_omits_enabled_plugins_from_repo(self):
        """Repo settings.json must not carry enabledPlugins at all (local-only)."""
        with TempEnv() as env:
            self._setup_seeded(env)  # local has enabledPlugins: {"a@m": True}
            dest = os.path.join(env.root, "verify_ep")
            subprocess.run(["git", "clone", env.remote_url, dest],
                           env=GIT_ENV, capture_output=True, text=True, check=True)
            with open(os.path.join(dest, "settings.json"), encoding="utf-8") as fh:
                repo_settings = json.load(fh)
            self.assertNotIn("enabledPlugins", repo_settings,
                             "enabledPlugins must never be published to the repo")
