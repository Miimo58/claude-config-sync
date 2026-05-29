import json
import os
import unittest
from scripts import sync_engine
from tests.helpers import TempEnv


class TestEngineCli(unittest.TestCase):
    def test_pull_without_setup_exits_zero_and_logs(self):
        with TempEnv() as env:
            code = sync_engine.main(["pull", "--claude-dir", env.claude_dir])
            self.assertEqual(code, 0)
            log = os.path.join(env.claude_dir, "backups", "sync", "sync.log")
            self.assertTrue(os.path.isfile(log))

    def test_status_reports_not_configured(self):
        with TempEnv() as env:
            st = sync_engine.cmd_status(env.claude_dir, env.sync_dir)
            self.assertFalse(st["configured"])

    def test_setup_then_status_configured(self):
        with TempEnv() as env:
            env.write("CLAUDE.md", "x")
            sync_engine.cmd_setup(env.remote_url, env.claude_dir, env.sync_dir)
            st = sync_engine.cmd_status(env.claude_dir, env.sync_dir)
            self.assertTrue(st["configured"])
            self.assertEqual(st["remote_url"], env.remote_url)
