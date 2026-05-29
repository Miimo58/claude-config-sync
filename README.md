# claude-config-sync

Sync a manifest-defined subset of your `~/.claude` configuration across machines via
a private git repository.

## What syncs

Defined by `manifest.default.json` (seeded into the repo as `manifest.json`):
`settings.json` (key-aware merge), `CLAUDE.md`, `AGENTS.md`, `agents/`, `commands/`,
`rules/`, `hooks/`, `scripts/`, `skills/`, `mcp-configs/`.

Never synced: `sessions/`, `projects/`, `cache/`, `security/`, `backups/`,
`file-history/`, `session-data/`, `session-env/`, `ide/`, `*.log`, `.DS_Store`.

## How it works

- **SessionStart** → `pull`: fetch the repo and apply changes (newest-wins per file;
  the overwritten version is saved under `~/.claude/backups/sync/<timestamp>/`).
- **Stop** (session end) → `push`: copy your config into the repo, scan for secrets,
  commit and push.

`settings.json` is merged, not overwritten: `enabledPlugins` and
`extraKnownMarketplaces` are unioned so every plugin/marketplace known on any machine
is **installed/available** everywhere, while each machine keeps its own
**enabled/disabled** choices (a plugin arriving from another machine lands installed
but disabled).

## Setup (once per machine)

```
/sync-setup git@github.com:you/your-private-claude-config.git
```

The first machine seeds the empty repo; later machines pull and merge.

## Commands

- `/sync-setup <git-remote-url>` — configure this machine.
- `/sync-status` — show remote, branch, pending changes.
- `/sync-push` — push now (also runs automatically at session end).

## Safety

- **Explicit allowlist:** only manifest paths ever sync.
- **Backups:** every overwrite is saved under `~/.claude/backups/sync/`.
- **Secret guard:** a push is aborted if a likely secret (API key, token, private
  key) is detected; nothing is pushed and the finding is logged to
  `~/.claude/backups/sync/sync.log`.
- **Non-fatal:** sync never blocks or breaks a session; failures are logged and
  skipped.

## Known limitation

Newest-wins relies on file mtime vs git commit time. Across machines with significant
**clock skew**, a rare simultaneous edit could be misjudged — but the overwritten
version is always backed up and recoverable.

## Plugin reconciliation

Requires the `claude` CLI on PATH. On pull, marketplaces in `extraKnownMarketplaces`
are added (`claude plugin marketplace add <repo>`) and plugins in `enabledPlugins` are
installed (`claude plugin install <plugin@marketplace> --scope user`) if missing.
Reconciliation failures are logged and never crash the session.
