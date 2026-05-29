import os
import subprocess
import unittest
from scripts import sync_engine
from scripts.lib import config, gitio
from tests.helpers import TempEnv, GIT_ENV


class TestEngineSetup(unittest.TestCase):
    def test_setup_seeds_empty_repo_from_local(self):
        with TempEnv() as env:
            env.write("CLAUDE.md", "my instructions")
            env.write("agents/a.md", "agent a")
            env.write("settings.json", '{"model": "opus"}')
            sync_engine.cmd_setup(env.remote_url, env.claude_dir, env.sync_dir)

            # local config recorded
            cfg = config.load_local_config(env.claude_dir)
            self.assertEqual(cfg["remote_url"], env.remote_url)

            # manifest seeded + content pushed: a fresh clone sees the files
            dest = os.path.join(env.root, "verify")
            subprocess.run(["git", "clone", env.remote_url, dest],
                           env=GIT_ENV, capture_output=True, text=True, check=True)
            self.assertTrue(os.path.isfile(os.path.join(dest, "manifest.json")))
            with open(os.path.join(dest, "CLAUDE.md"), encoding="utf-8") as fh:
                self.assertEqual(fh.read(), "my instructions")
            self.assertTrue(os.path.isfile(os.path.join(dest, "agents", "a.md")))

    def test_setup_skips_excluded_files(self):
        with TempEnv() as env:
            env.write("CLAUDE.md", "x")
            env.write("scripts/.DS_Store", "junk")
            sync_engine.cmd_setup(env.remote_url, env.claude_dir, env.sync_dir)
            self.assertFalse(os.path.isfile(os.path.join(env.sync_dir, "scripts", ".DS_Store")))
