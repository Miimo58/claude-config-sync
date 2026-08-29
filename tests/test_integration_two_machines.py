import glob
import json
import os
import shutil
import tempfile
import time
import unittest
from scripts import sync_engine
from scripts.lib import snapshot
from tests.helpers import make_bare_remote


class TwoMachines(unittest.TestCase):
    """Machine A seeds; machine B clones; a change on A reaches B; newest-wins holds."""

    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="syncplugin-int-")
        self.remote = "file://" + make_bare_remote(self.root)
        self.a_claude = os.path.join(self.root, "A", "claude")
        self.a_sync = os.path.join(self.root, "A", "sync")
        self.b_claude = os.path.join(self.root, "B", "claude")
        self.b_sync = os.path.join(self.root, "B", "sync")
        for d in (self.a_claude, self.b_claude):
            os.makedirs(d, exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def _write(self, claude_dir: str, rel: str, content: str) -> None:
        p = os.path.join(claude_dir, rel)
        os.makedirs(os.path.dirname(p) or claude_dir, exist_ok=True)
        with open(p, "w", encoding="utf-8") as fh:
            fh.write(content)

    def test_change_on_A_propagates_to_B(self):
        # A seeds the repo
        self._write(self.a_claude, "CLAUDE.md", "A v1")
        self._write(self.a_claude, "settings.json",
                    json.dumps({"model": "opus", "enabledPlugins": {"a@m": True}}))
        sync_engine.cmd_setup(self.remote, self.a_claude, self.a_sync)

        # B sets up from a non-empty repo -> pulls
        self._write(self.b_claude, "settings.json",
                    json.dumps({"model": "sonnet", "enabledPlugins": {"b@m": True}}))
        sync_engine.cmd_setup(self.remote, self.b_claude, self.b_sync, reconcile=False)
        with open(os.path.join(self.b_claude, "CLAUDE.md"), encoding="utf-8") as fh:
            self.assertEqual(fh.read(), "A v1")
        with open(os.path.join(self.b_claude, "settings.json"), encoding="utf-8") as fh:
            b_settings = json.load(fh)
        # B keeps its own enabled plugin; A's name propagates but lands disabled.
        self.assertEqual(b_settings["enabledPlugins"]["b@m"], True)
        self.assertEqual(b_settings["enabledPlugins"]["a@m"], False)

        # Back-date B's local CLAUDE.md so A's incoming commit will be strictly newer.
        b_claude_md = os.path.join(self.b_claude, "CLAUDE.md")
        past = time.time() - 10000
        os.utime(b_claude_md, (past, past))

        # A changes CLAUDE.md and pushes
        self._write(self.a_claude, "CLAUDE.md", "A v2")
        self.assertEqual(sync_engine.cmd_push(self.a_claude, self.a_sync)["status"],
                         "pushed")

        # B pulls and sees the change
        sync_engine.cmd_pull(self.b_claude, self.b_sync, reconcile=False)
        with open(os.path.join(self.b_claude, "CLAUDE.md"), encoding="utf-8") as fh:
            self.assertEqual(fh.read(), "A v2")

    def test_plugin_name_propagates_to_B_disabled_by_default(self):
        """A's plugin becomes available on B but explicitly disabled."""
        self._write(self.a_claude, "CLAUDE.md", "A")
        self._write(self.a_claude, "settings.json",
                    json.dumps({"enabledPlugins": {"px@m": True}}))
        sync_engine.cmd_setup(self.remote, self.a_claude, self.a_sync)

        self._write(self.b_claude, "settings.json", json.dumps({}))
        sync_engine.cmd_setup(self.remote, self.b_claude, self.b_sync, reconcile=False)

        with open(os.path.join(self.b_claude, "settings.json"), encoding="utf-8") as fh:
            b_settings = json.load(fh)
        ep = b_settings.get("enabledPlugins", {})
        self.assertIn("px@m", ep, "plugin name should reach B for availability")
        self.assertFalse(ep["px@m"], "A's enabled=True must land disabled on B")

    def test_local_disable_sticks_across_pull(self):
        """A plugin disabled locally stays disabled after a pull (state sticks)."""
        # A seeds with px@m enabled; the repo carries the name with value False.
        self._write(self.a_claude, "CLAUDE.md", "A")
        self._write(self.a_claude, "settings.json",
                    json.dumps({"enabledPlugins": {"px@m": True}}))
        sync_engine.cmd_setup(self.remote, self.a_claude, self.a_sync)

        # B receives px@m (disabled), then the user enables it locally.
        self._write(self.b_claude, "settings.json", json.dumps({}))
        sync_engine.cmd_setup(self.remote, self.b_claude, self.b_sync, reconcile=False)
        self._write(self.b_claude, "settings.json",
                    json.dumps({"enabledPlugins": {"px@m": True}}))

        # A subsequent pull must NOT reset B's choice back to disabled.
        sync_engine.cmd_pull(self.b_claude, self.b_sync, reconcile=False)
        with open(os.path.join(self.b_claude, "settings.json"), encoding="utf-8") as fh:
            b_settings = json.load(fh)
        self.assertTrue(b_settings["enabledPlugins"]["px@m"],
                        "B's local enable choice must survive the pull")

    def test_local_enabled_state_sticks_for_seeding_machine(self):
        """A keeps its own enabled plugin across pulls despite repo storing False."""
        self._write(self.a_claude, "CLAUDE.md", "A")
        self._write(self.a_claude, "settings.json",
                    json.dumps({"enabledPlugins": {"px@m": True}}))
        sync_engine.cmd_setup(self.remote, self.a_claude, self.a_sync)
        sync_engine.cmd_pull(self.a_claude, self.a_sync, reconcile=False)
        with open(os.path.join(self.a_claude, "settings.json"), encoding="utf-8") as fh:
            a_settings = json.load(fh)
        self.assertTrue(a_settings["enabledPlugins"]["px@m"],
                        "repo's normalized False must not disable A's own plugin")

    def test_excluded_paths_never_sync(self):
        self._write(self.a_claude, "CLAUDE.md", "x")
        self._write(self.a_claude, "sessions/secret-session.json", "should not sync")
        sync_engine.cmd_setup(self.remote, self.a_claude, self.a_sync)
        self.assertFalse(os.path.isfile(os.path.join(self.a_sync, "sessions",
                                                     "secret-session.json")))


class Deletions(unittest.TestCase):
    """A delete on one machine reaches the other, and never fires by accident."""

    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="syncplugin-del-")
        self.remote = "file://" + make_bare_remote(self.root)
        self.a_claude = os.path.join(self.root, "A", "claude")
        self.a_sync = os.path.join(self.root, "A", "sync")
        self.b_claude = os.path.join(self.root, "B", "claude")
        self.b_sync = os.path.join(self.root, "B", "sync")
        for d in (self.a_claude, self.b_claude):
            os.makedirs(d, exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def _write(self, claude_dir: str, rel: str, content: str) -> None:
        p = os.path.join(claude_dir, rel)
        os.makedirs(os.path.dirname(p) or claude_dir, exist_ok=True)
        with open(p, "w", encoding="utf-8") as fh:
            fh.write(content)

    def _seed_both(self):
        """A seeds a skill; B clones it. Both machines end in sync."""
        self._write(self.a_claude, "CLAUDE.md", "shared")
        self._write(self.a_claude, "settings.json", json.dumps({}))
        self._write(self.a_claude, "skills/doomed/SKILL.md", "delete me")
        self._write(self.a_claude, "skills/doomed/scripts/helper.js", "nested")
        sync_engine.cmd_setup(self.remote, self.a_claude, self.a_sync)
        self._write(self.b_claude, "settings.json", json.dumps({}))
        sync_engine.cmd_setup(self.remote, self.b_claude, self.b_sync, reconcile=False)
        self.assertTrue(os.path.isfile(
            os.path.join(self.b_claude, "skills/doomed/SKILL.md")))

    def test_delete_on_A_reaches_the_repo(self):
        self._seed_both()
        shutil.rmtree(os.path.join(self.a_claude, "skills/doomed"))
        sync_engine.cmd_push(self.a_claude, self.a_sync)
        self.assertFalse(os.path.exists(
            os.path.join(self.a_sync, "skills/doomed/SKILL.md")),
            "push must remove the file this machine deleted")

    def test_delete_on_A_reaches_B(self):
        self._seed_both()
        shutil.rmtree(os.path.join(self.a_claude, "skills/doomed"))
        sync_engine.cmd_push(self.a_claude, self.a_sync)

        sync_engine.cmd_pull(self.b_claude, self.b_sync, reconcile=False)

        self.assertFalse(os.path.exists(
            os.path.join(self.b_claude, "skills/doomed/SKILL.md")),
            "pull must remove a file deleted upstream")
        self.assertFalse(os.path.exists(os.path.join(self.b_claude, "skills/doomed")),
                         "the emptied directory must go too, nested subdirs included")
        self.assertFalse(os.path.exists(os.path.join(self.b_claude, "skills")),
                         "the last skill leaving takes the entry root with it")

    def test_deleted_file_is_backed_up_on_B(self):
        self._seed_both()
        shutil.rmtree(os.path.join(self.a_claude, "skills/doomed"))
        sync_engine.cmd_push(self.a_claude, self.a_sync)
        sync_engine.cmd_pull(self.b_claude, self.b_sync, reconcile=False)

        hits = glob.glob(os.path.join(self.b_claude, "backups", "sync", "*",
                                      "skills", "doomed", "SKILL.md"))
        self.assertTrue(hits, "a deleted file must be recoverable from backups")
        with open(hits[0], encoding="utf-8") as fh:
            self.assertEqual(fh.read(), "delete me")

    def test_delete_does_not_come_back_on_the_next_round_trip(self):
        """The original bug: B must not push the file back up to the repo."""
        self._seed_both()
        shutil.rmtree(os.path.join(self.a_claude, "skills/doomed"))
        sync_engine.cmd_push(self.a_claude, self.a_sync)
        sync_engine.cmd_pull(self.b_claude, self.b_sync, reconcile=False)

        sync_engine.cmd_push(self.b_claude, self.b_sync)
        sync_engine.cmd_pull(self.a_claude, self.a_sync, reconcile=False)

        self.assertFalse(os.path.exists(
            os.path.join(self.a_claude, "skills/doomed/SKILL.md")),
            "the deleted skill must stay dead")

    def test_locally_modified_file_survives_an_upstream_delete(self):
        """B edited the file after the last sync, so B's edit wins over A's delete."""
        self._seed_both()
        shutil.rmtree(os.path.join(self.a_claude, "skills/doomed"))
        sync_engine.cmd_push(self.a_claude, self.a_sync)

        self._write(self.b_claude, "skills/doomed/SKILL.md", "B still wants this")
        sync_engine.cmd_pull(self.b_claude, self.b_sync, reconcile=False)

        path = os.path.join(self.b_claude, "skills/doomed/SKILL.md")
        self.assertTrue(os.path.isfile(path), "a local edit must beat a remote delete")
        with open(path, encoding="utf-8") as fh:
            self.assertEqual(fh.read(), "B still wants this")

    def test_push_keeps_repo_files_this_machine_never_had(self):
        """B must never delete A's brand-new file just because B lacks it."""
        self._seed_both()
        self._write(self.a_claude, "skills/newcomer/SKILL.md", "fresh from A")
        sync_engine.cmd_push(self.a_claude, self.a_sync)

        # B pushes without ever having pulled the newcomer.
        sync_engine.cmd_push(self.b_claude, self.b_sync)

        self.assertTrue(os.path.isfile(
            os.path.join(self.b_sync, "skills/newcomer/SKILL.md")),
            "a file absent from B's snapshot is unknown, not deleted")

    def test_first_run_without_a_snapshot_deletes_nothing(self):
        """Upgrading an existing machine must not wipe files on the first sync."""
        self._seed_both()
        os.remove(snapshot.path(self.b_claude))  # pre-upgrade machine
        shutil.rmtree(os.path.join(self.b_claude, "skills/doomed"))

        sync_engine.cmd_push(self.b_claude, self.b_sync)

        self.assertTrue(os.path.isfile(
            os.path.join(self.b_sync, "skills/doomed/SKILL.md")),
            "with no memory of the last sync, delete nothing")

    def test_unpushed_local_file_is_never_deleted_by_a_pull(self):
        """A file created locally and not yet pushed is not an upstream delete."""
        self._seed_both()
        self._write(self.b_claude, "skills/brand-new/SKILL.md", "written offline")
        sync_engine.cmd_pull(self.b_claude, self.b_sync, reconcile=False)
        sync_engine.cmd_pull(self.b_claude, self.b_sync, reconcile=False)

        self.assertTrue(os.path.isfile(
            os.path.join(self.b_claude, "skills/brand-new/SKILL.md")),
            "an unpushed local file must survive repeated pulls")
