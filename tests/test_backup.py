import os
import unittest
from scripts.lib import backup
from tests.helpers import TempEnv


class TestBackup(unittest.TestCase):
    def test_backup_copies_file_into_timestamped_dir(self):
        with TempEnv() as env:
            env.write("CLAUDE.md", "original")
            dest = backup.backup_file(env.claude_dir, "CLAUDE.md", "20260529-100000")
            self.assertTrue(os.path.isfile(dest))
            with open(dest, encoding="utf-8") as fh:
                self.assertEqual(fh.read(), "original")
            self.assertIn(os.path.join("backups", "sync", "20260529-100000"), dest)

    def test_backup_missing_file_returns_none(self):
        with TempEnv() as env:
            self.assertIsNone(
                backup.backup_file(env.claude_dir, "nope.md", "20260529-100000"))
