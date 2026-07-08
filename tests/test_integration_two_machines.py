import json
import os
import shutil
import tempfile
import time
import unittest
from scripts import sync_engine
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
