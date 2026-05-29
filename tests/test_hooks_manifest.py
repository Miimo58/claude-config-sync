import json
import os
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class TestHooksAndCommands(unittest.TestCase):
    def test_hooks_json_has_sessionstart_pull_and_stop_push(self):
        with open(os.path.join(ROOT, "hooks", "hooks.json"), encoding="utf-8") as fh:
            hooks = json.load(fh)["hooks"]
        ss = json.dumps(hooks["SessionStart"])
        stop = json.dumps(hooks["Stop"])
        self.assertIn("sync_engine.py", ss)
        self.assertIn("pull", ss)
        self.assertIn("sync_engine.py", stop)
        self.assertIn("push", stop)
        self.assertIn("CLAUDE_PLUGIN_ROOT", ss)

    def test_plugin_manifest_has_no_hooks_or_agents_field(self):
        with open(os.path.join(ROOT, ".claude-plugin", "plugin.json"),
                  encoding="utf-8") as fh:
            man = json.load(fh)
        self.assertNotIn("hooks", man)
        self.assertNotIn("agents", man)
        self.assertIn("version", man)

    def test_command_files_exist(self):
        for name in ("sync-setup", "sync-status", "sync-push"):
            self.assertTrue(
                os.path.isfile(os.path.join(ROOT, "commands", f"{name}.md")))
