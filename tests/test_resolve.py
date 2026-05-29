import os
import tempfile
import unittest
from scripts.lib import resolve


def _write(path: str, content: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(content)


class TestResolve(unittest.TestCase):
    def test_files_equal(self):
        with tempfile.TemporaryDirectory() as d:
            a, b = os.path.join(d, "a"), os.path.join(d, "b")
            _write(a, "x")
            _write(b, "x")
            self.assertTrue(resolve.files_equal(a, b))
            _write(b, "y")
            self.assertFalse(resolve.files_equal(a, b))

    def test_newest_wins_missing_sides(self):
        self.assertEqual(resolve.newest_wins(local_exists=False, repo_exists=True,
                                              equal=False, local_mtime=0, repo_ctime=0), "repo")
        self.assertEqual(resolve.newest_wins(local_exists=True, repo_exists=False,
                                              equal=False, local_mtime=0, repo_ctime=0), "local")

    def test_newest_wins_equal(self):
        self.assertEqual(resolve.newest_wins(True, True, equal=True,
                                             local_mtime=5, repo_ctime=9), "equal")

    def test_newest_wins_by_time(self):
        self.assertEqual(resolve.newest_wins(True, True, False,
                                             local_mtime=10, repo_ctime=20), "repo")
        self.assertEqual(resolve.newest_wins(True, True, False,
                                             local_mtime=30, repo_ctime=20), "local")

    def test_iter_manifest_files_walks_dir_and_applies_excludes(self):
        with tempfile.TemporaryDirectory() as base:
            _write(os.path.join(base, "agents", "a.md"), "1")
            _write(os.path.join(base, "agents", ".DS_Store"), "junk")
            _write(os.path.join(base, "CLAUDE.md"), "2")
            excludes = [".DS_Store"]
            agent_files = sorted(resolve.iter_manifest_files(base, "agents", excludes))
            self.assertEqual(agent_files, ["agents/a.md"])
            file_entry = list(resolve.iter_manifest_files(base, "CLAUDE.md", excludes))
            self.assertEqual(file_entry, ["CLAUDE.md"])

    def test_iter_manifest_files_missing_path_yields_nothing(self):
        with tempfile.TemporaryDirectory() as base:
            self.assertEqual(list(resolve.iter_manifest_files(base, "nope", [])), [])
