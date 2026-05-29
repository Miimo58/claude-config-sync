import json
import os
import subprocess
import time
import unittest
from scripts import sync_engine
from scripts.lib import gitio
from tests.helpers import TempEnv, GIT_ENV


def _seed_remote_with(env, files):
    """Make the remote contain `files` (dict relpath->content) + a manifest."""
    seed = os.path.join(env.root, "seed")
    subprocess.run(["git", "clone", env.remote_url, seed],
                   env=GIT_ENV, capture_output=True, text=True, check=True)
    man = {"version": 1,
           "entries": [{"path": "settings.json", "policy": "merge"},
                       {"path": "CLAUDE.md", "policy": "copy"}],
           "global_excludes": [".DS_Store"]}
    with open(os.path.join(seed, "manifest.json"), "w", encoding="utf-8") as fh:
        json.dump(man, fh)
    for rel, content in files.items():
        p = os.path.join(seed, rel)
        os.makedirs(os.path.dirname(p) or seed, exist_ok=True)
        with open(p, "w", encoding="utf-8") as fh:
            fh.write(content)
    gitio.commit_all(seed, "seed")
    gitio.push(seed)


class TestEnginePull(unittest.TestCase):
    def _setup_clone(self, env):
        from scripts.lib import config
        config.write_local_config(env.claude_dir, env.remote_url, env.sync_dir)
        gitio.clone(env.remote_url, env.sync_dir)

    def test_pull_brings_new_repo_file_to_local(self):
        with TempEnv() as env:
            _seed_remote_with(env, {"CLAUDE.md": "from repo"})
            self._setup_clone(env)
            sync_engine.cmd_pull(env.claude_dir, env.sync_dir, reconcile=False)
            self.assertEqual(env.read("CLAUDE.md"), "from repo")

    def test_pull_repo_newer_overwrites_local_and_backs_up(self):
        with TempEnv() as env:
            _seed_remote_with(env, {"CLAUDE.md": "repo version"})
            self._setup_clone(env)
            env.write("CLAUDE.md", "local old")
            old = time.time() - 10000
            os.utime(os.path.join(env.claude_dir, "CLAUDE.md"), (old, old))
            sync_engine.cmd_pull(env.claude_dir, env.sync_dir, reconcile=False)
            self.assertEqual(env.read("CLAUDE.md"), "repo version")
            backups = os.path.join(env.claude_dir, "backups", "sync")
            found = []
            for r, _, fs in os.walk(backups):
                found += [os.path.join(r, f) for f in fs]
            self.assertTrue(any(
                open(f, encoding="utf-8").read() == "local old" for f in found
            ))

    def test_pull_local_newer_is_kept(self):
        with TempEnv() as env:
            _seed_remote_with(env, {"CLAUDE.md": "repo version"})
            self._setup_clone(env)
            env.write("CLAUDE.md", "local new")  # mtime = now > repo commit time
            sync_engine.cmd_pull(env.claude_dir, env.sync_dir, reconcile=False)
            self.assertEqual(env.read("CLAUDE.md"), "local new")

    def test_pull_merges_settings_enabled_plugins(self):
        with TempEnv() as env:
            _seed_remote_with(env, {
                "settings.json": json.dumps(
                    {"model": "sonnet", "enabledPlugins": {"x@m": True}})})
            self._setup_clone(env)
            env.write("settings.json", json.dumps(
                {"model": "opus", "enabledPlugins": {"y@m": True}}))
            old = time.time() - 10000
            os.utime(os.path.join(env.claude_dir, "settings.json"), (old, old))
            sync_engine.cmd_pull(env.claude_dir, env.sync_dir, reconcile=False)
            merged = json.loads(env.read("settings.json"))
            self.assertEqual(merged["model"], "sonnet")
            self.assertEqual(merged["enabledPlugins"]["y@m"], True)
            self.assertEqual(merged["enabledPlugins"]["x@m"], False)
