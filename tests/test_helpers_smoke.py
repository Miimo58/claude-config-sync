import os
import subprocess
import unittest
from tests.helpers import TempEnv, git


class TestHarness(unittest.TestCase):
    def test_tempenv_creates_dirs_and_remote(self):
        with TempEnv() as env:
            self.assertTrue(os.path.isdir(env.claude_dir))
            self.assertTrue(env.remote_url.startswith("file://"))
            env.write("CLAUDE.md", "hello")
            self.assertEqual(env.read("CLAUDE.md"), "hello")

    def test_can_clone_bare_remote(self):
        with TempEnv() as env:
            dest = os.path.join(env.root, "clone")
            subprocess.run(["git", "clone", env.remote_url, dest],
                           capture_output=True, text=True, check=True)
            self.assertTrue(os.path.isdir(os.path.join(dest, ".git")))
