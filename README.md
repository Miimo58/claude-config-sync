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
becomes **available everywhere**. A plugin installed on one machine is installed on the
others too, but **disabled by default** — and each machine's own enabled/disabled
choice always wins and **persists across syncs** (disabling a plugin locally stays
disabled; it is never silently re-enabled). One machine's `enabled = true` never
propagates to force a plugin on elsewhere.

---

## Publishing to the Claude marketplace

The plugin is shared as a **public** GitHub repository. Users add it via the standard
`claude plugin` workflow — no separate package registry is needed.

### 1. Create a public GitHub repo and push

```bash
# Inside this directory
git remote add origin git@github.com:YOUR_USERNAME/claude-config-sync.git
git push -u origin main
```

### 2. Users install it

```bash
# Add the marketplace (only needed once per machine)
claude plugin marketplace add https://github.com/YOUR_USERNAME/claude-config-sync

# Install the plugin
claude plugin install claude-config-sync
```

That's it. The plugin appears in `claude plugin list` and hooks activate automatically
on the next session.

---

## Full setup guide (new machine)

Two separate repos are involved:

| Repo | Visibility | Purpose |
|------|-----------|---------|
| `claude-config-sync` (this repo) | **Public** | The plugin code — shared with everyone |
| `your-private-claude-config` | **Private** | Your personal config — synced between your machines |

### Step 1 — Install the plugin (every machine)

```bash
claude plugin marketplace add https://github.com/YOUR_USERNAME/claude-config-sync
claude plugin install claude-config-sync
```

### Step 2 — Create a private config repo (first machine only)

Create an empty **private** repo on GitHub (e.g. `my-claude-config`), then:

```bash
/sync-setup git@github.com:YOUR_USERNAME/my-claude-config.git
```

This seeds the empty repo from your current `~/.claude` config.

### Step 3 — Connect additional machines

On each new machine, install the plugin (Step 1), then run:

```bash
/sync-setup git@github.com:YOUR_USERNAME/my-claude-config.git
```

The engine pulls from the repo and applies your config (newest-wins, with backups).
From this point forward, every session start pulls and every session end pushes
automatically.

---

## Commands

- `/sync-setup <git-remote-url>` — configure this machine.
- `/sync-status` — show remote, branch, pending changes.
- `/sync-push` — push now (also runs automatically at session end).

---

## Safety

### Is it safe to publish this plugin?

Yes — the plugin source code contains no personal information, credentials, or
machine-specific configuration. What to be aware of:

- **`.claude/settings.local.json`** (your local Claude Code permission settings) is
  excluded by `.gitignore` and is never committed. It may contain your name/email in
  permission entries.
- **`docs/`** (internal planning specs) is also excluded by `.gitignore`.
- The git history contains no personal information.

### Runtime safety (your private config repo)

- **Explicit allowlist:** only paths listed in `manifest.json` ever sync.
- **Backups:** every overwrite is saved under `~/.claude/backups/sync/`.
- **Secret guard:** a push is aborted if a likely secret (API key, token, private
  key) is detected; nothing is pushed and the finding is logged to
  `~/.claude/backups/sync/sync.log`.
- **Non-fatal:** sync never blocks or breaks a session; failures are logged and
  skipped.

---

## Known limitation

Newest-wins relies on file mtime vs git commit time. Across machines with significant
**clock skew**, a rare simultaneous edit could be misjudged — but the overwritten
version is always backed up and recoverable.

## Plugin & marketplace reconciliation

Requires the `claude` CLI on PATH. On pull:

- Marketplaces in `extraKnownMarketplaces` not yet known locally are added
  (`claude plugin marketplace add <repo>`).
- A plugin name that is **new to this machine** (it arrived via the repo) is installed
  and then disabled (`claude plugin install --scope user <key>` followed by
  `claude plugin disable --scope user <key>`), so it lands **available but disabled by
  default**.
- Plugins this machine already manages are **left untouched**, so a local
  enabled/disabled choice is never overridden.

The install/skip decision uses this machine's pre-pull `enabledPlugins` keys, so it
does not depend on `claude plugin list` reporting disabled plugins. Reconciliation
failures are logged and never crash the session.
