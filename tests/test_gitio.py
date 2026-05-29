import os
import subprocess
import unittest
from scripts.lib import gitio
from tests.helpers import TempEnv, GIT_ENV


class TestGitio(unittest.TestCase):
    def test_clone_empty_repo_reports_empty(self) -> None:
        with TempEnv() as env:
            gitio.clone(env.remote_url, env.sync_dir)
            self.assertTrue(gitio.is_empty_repo(env.sync_dir))

    def test_commit_push_then_clone_sees_content(self) -> None:
        with TempEnv() as env:
            gitio.clone(env.remote_url, env.sync_dir)
            with open(os.path.join(env.sync_dir, "a.txt"), "w") as fh:
                fh.write("hi")
            gitio.commit_all(env.sync_dir, "add a")
            gitio.push(env.sync_dir)
            self.assertFalse(gitio.is_empty_repo(env.sync_dir))
            dest = os.path.join(env.root, "clone2")
            subprocess.run(["git", "clone", env.remote_url, dest],
                           env=GIT_ENV, capture_output=True, text=True, check=True)
            self.assertTrue(os.path.isfile(os.path.join(dest, "a.txt")))

    def test_last_commit_time_increases_with_new_commit(self) -> None:
        with TempEnv() as env:
            gitio.clone(env.remote_url, env.sync_dir)
            p = os.path.join(env.sync_dir, "a.txt")
            with open(p, "w") as fh:
                fh.write("one")
            gitio.commit_all(env.sync_dir, "c1")
            t1 = gitio.last_commit_time(env.sync_dir, "a.txt")
            self.assertIsInstance(t1, int)
            self.assertIsNone(gitio.last_commit_time(env.sync_dir, "missing.txt"))
