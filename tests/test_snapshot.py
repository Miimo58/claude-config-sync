"""Snapshot: the record of which manifest files were in sync last time."""
import json
import os
import unittest

from scripts.lib import snapshot
from tests.helpers import TempEnv

MAN = {
    "version": 1,
    "entries": [
        {"path": "settings.json", "policy": "merge"},
        {"path": "CLAUDE.md", "policy": "copy"},
        {"path": "skills", "policy": "copy"},
    ],
    "global_excludes": ["*.log", "sessions"],
}


class HashFile(unittest.TestCase):
    def test_same_content_same_hash(self):
        with TempEnv() as env:
            a = env.write("a.md", "hello")
            b = env.write("b.md", "hello")
            self.assertEqual(snapshot.hash_file(a), snapshot.hash_file(b))

    def test_different_content_different_hash(self):
        with TempEnv() as env:
            a = env.write("a.md", "hello")
            b = env.write("b.md", "goodbye")
            self.assertNotEqual(snapshot.hash_file(a), snapshot.hash_file(b))


class LoadSave(unittest.TestCase):
    def test_load_returns_empty_when_absent(self):
        with TempEnv() as env:
            self.assertEqual(snapshot.load(env.claude_dir), {})

    def test_round_trip(self):
        with TempEnv() as env:
            snapshot.save(env.claude_dir, {"CLAUDE.md": "abc"})
            self.assertEqual(snapshot.load(env.claude_dir), {"CLAUDE.md": "abc"})

    def test_load_survives_corrupt_file(self):
        """A damaged snapshot must degrade to 'know nothing', never crash a session."""
        with TempEnv() as env:
            with open(snapshot.path(env.claude_dir), "w", encoding="utf-8") as fh:
                fh.write("{not json")
            self.assertEqual(snapshot.load(env.claude_dir), {})

    def test_file_is_not_itself_synced(self):
        """The snapshot is machine-local: its name must not match a manifest entry."""
        names = {e["path"] for e in MAN["entries"]}
        self.assertNotIn(os.path.basename(snapshot.path("/x")), names)


class Build(unittest.TestCase):
    """The snapshot holds paths present in BOTH trees, hashed from the local one."""

    def _repo(self, env, rel, content):
        full = os.path.join(env.sync_dir, rel)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w", encoding="utf-8") as fh:
            fh.write(content)

    def test_intersection_only(self):
        with TempEnv() as env:
            env.write("CLAUDE.md", "both")
            self._repo(env, "CLAUDE.md", "both")
            env.write("skills/local-only/SKILL.md", "not pushed yet")
            self._repo(env, "skills/repo-only/SKILL.md", "not pulled yet")

            built = snapshot.build(env.claude_dir, env.sync_dir, MAN)

            self.assertIn("CLAUDE.md", built)
            self.assertNotIn("skills/local-only/SKILL.md", built,
                             "a never-pushed local file is not in sync")
            self.assertNotIn("skills/repo-only/SKILL.md", built,
                             "a never-applied repo file is not in sync")

    def test_hashes_come_from_local(self):
        with TempEnv() as env:
            local = env.write("CLAUDE.md", "local text")
            self._repo(env, "CLAUDE.md", "repo text")
            built = snapshot.build(env.claude_dir, env.sync_dir, MAN)
            self.assertEqual(built["CLAUDE.md"], snapshot.hash_file(local))

    def test_skips_settings_and_excludes(self):
        with TempEnv() as env:
            env.write("settings.json", json.dumps({"model": "opus"}))
            self._repo(env, "settings.json", json.dumps({"model": "opus"}))
            env.write("skills/x/notes.log", "noisy")
            self._repo(env, "skills/x/notes.log", "noisy")

            built = snapshot.build(env.claude_dir, env.sync_dir, MAN)

            self.assertNotIn("settings.json", built,
                             "settings.json merges; it must never be delete-tracked")
            self.assertNotIn("skills/x/notes.log", built)


if __name__ == "__main__":
    unittest.main()
