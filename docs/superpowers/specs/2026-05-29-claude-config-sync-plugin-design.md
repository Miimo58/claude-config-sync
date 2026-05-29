# Claude Config Sync Plugin — Design

**Date:** 2026-05-29
**Status:** Approved (design)

## 1. Purpose

A Claude Code plugin that keeps a chosen set of `~/.claude` configuration in sync
across multiple machines via a private git repository. The local machine seeds the
repo on first setup; thereafter, a change made on any machine propagates to the
others. Sync is automatic at session boundaries: pull on session start, push on
session end.

## 2. Goals & Non-Goals

### Goals
- One-time per-machine setup, then hands-off sync.
- Bidirectional: a change on machine A appears on machine B at its next session start.
- Explicit allowlist of what syncs (manifest). Nothing else can leak.
- Never lose data: every overwrite is backed up.
- Never block or break a Claude Code session, even on network/git failure.
- Plugins: every plugin enabled on *any* machine becomes *installed/available* on
  *every* machine; per-machine enabled/disabled state is preserved.

### Non-Goals (v1)
- Real-time / continuous sync (chosen model is session-boundary).
- Syncing ephemeral machine-local state (`sessions/`, `projects/`, `cache/`,
  `*.log`, `security/`, `backups/`, `file-history/`, `.DS_Store`, etc.).
- Syncing the `~/.claude/.agents/` subsystem (marketplace-managed; out of scope).
- Secret allowlisting / overrides (the secret scanner aborts; no override in v1).
- Conflict UI / manual merge tooling (newest-wins + backup is the policy).

## 3. Transport & File Strategy (decided)

- **Transport:** private git repo (versioned, inspectable, conflict-aware).
- **File strategy:** mirror/copy + manifest (NOT symlinks). Symlinks do not survive
  the atomic write-temp-then-rename pattern Claude Code uses for `settings.json`, so
  a copy step is the robust choice. The manifest is an explicit allowlist.

## 4. Architecture

```
~/.claude/                 ← real config Claude Code reads (source of truth)
        ▲   │ copy (manifest-driven)
        │   ▼
~/.claude-sync/            ← git clone of the private repo (per machine)
        ▲   │ git pull / push
        │   ▼
   private git remote      ← durable shared state
```

### Components
- **`manifest.json`** (in the repo) — explicit allowlist of synced paths + per-path
  policy (e.g. `settings.json` → `merge`, everything else → `copy`).
- **`sync_engine.py`** — core logic (Python 3 stdlib only; no third-party deps, no
  venv). Subcommands: `setup`, `pull`, `push`, `status`.
- **Hooks** (`hooks/hooks.json`):
  - `SessionStart` → `sync_engine.py pull`
  - `Stop` (session end) → `sync_engine.py push`
  - Both wrapped to always exit 0; git calls use a short timeout.
- **Commands** (`commands/`):
  - `/sync-setup <git-remote-url>` — one-time per machine.
  - `/sync-status` — show last sync, drift, pending changes.
  - `/sync-push` — manual push on demand.
- **Local config** `~/.claude/sync-plugin.local.json` — machine-local, NOT synced.
  Holds remote URL + clone path. Each machine runs `/sync-setup` once.

## 5. Manifest (seed)

Synced paths under `~/.claude/`:

| Path | Policy | Notes |
|------|--------|-------|
| `settings.json` | merge | key-aware merge; `enabledPlugins` special (§7) |
| `CLAUDE.md` | copy | global instructions |
| `AGENTS.md` | copy | global instructions |
| `agents/` | copy | custom agents |
| `commands/` | copy | custom slash commands |
| `rules/` | copy | rules |
| `hooks/` | copy | hook definitions |
| `scripts/` | copy | hook implementations referenced by settings.json (`.DS_Store` excluded) |
| `skills/` | copy | personal authored skills (grill-me, handoff, learned) |
| `mcp-configs/` | copy | MCP server configs |

Global excludes (never synced, regardless of location): `.DS_Store`, `*.log`,
`sessions/`, `projects/`, `cache/`, `security/`, `backups/`, `file-history/`,
`session-data/`, `session-env/`, `ide/`.

## 6. Data Flow

### Setup — `/sync-setup <url>`
1. Write `~/.claude/sync-plugin.local.json` with remote URL + clone path (`~/.claude-sync`).
2. Clone the remote.
3. If the repo is **empty** → seed: copy all manifest paths in, write `manifest.json`,
   commit, push.
4. If the repo **has content** → treat as new machine: run `pull`.

### Pull — SessionStart
1. `git pull` (short timeout). On failure: log, notice, exit 0.
2. For each manifest path, walk files and compare repo vs local:
   - contents equal → skip.
   - differ → **newest wins**: compare local file mtime vs the repo's last-commit
     time for that path (`git log -1 --format=%ct -- <path>`). Loser is copied to
     `~/.claude/backups/sync/<timestamp>/<path>` first. If repo wins, copy repo→local;
     if local wins, leave local (it will push at session end).
   - `settings.json` uses the merge rule in §7 instead of raw copy.
3. Run **plugin reconciliation** (§7).

### Push — Stop (session end)
1. Copy manifest paths local→repo (honoring excludes; `settings.json` written as the
   merged result so machine-local `enabledPlugins` values are not leaked verbatim —
   see §7).
2. If nothing changed → no-op.
3. Run **secret scan** (§8). If a secret is found → abort push, leave everything
   untouched, surface a clear warning. Otherwise `git commit` + `git push`.

## 7. settings.json merge & plugin reconciliation

`settings.json` is synced with a **key-aware merge**, not a raw copy:

- **`enabledPlugins`** (object keyed by `plugin@marketplace` → bool):
  - **Keys** = union of repo + local. This union is the set of plugins that should be
    *installed/available* everywhere.
  - **Values** (enabled true/false) = the **local machine's** value wins. A key new to
    this machine defaults to **`false`** (installed but disabled — available, not
    forced on).
- **All other keys** in `settings.json` follow newest-wins (whole-object level using
  the file's commit time vs mtime, consistent with §6).
- **`extraKnownMarketplaces`** syncs globally (newest-wins like normal keys), so
  marketplace sources are known everywhere.

**Reconciliation (run on pull, after files applied):** compare desired vs actual:
- For each marketplace in merged `extraKnownMarketplaces` not known locally → add it.
- For each plugin key in merged `enabledPlugins` not installed locally → install it
  (so it becomes available). Do **not** change enabled/disabled state.

> ⚠️ Open detail for planning: the exact non-interactive CLI/commands to (a) add a
> marketplace and (b) install a plugin must be verified during planning (consult
> `~/.claude/PLUGIN_SCHEMA_NOTES.md` and current plugin docs). The *intent* is fixed;
> the precise invocation is a planning task. Reconciliation must degrade gracefully
> (log + continue) if a command is unavailable.

## 7a. Hook coexistence

The plugin's two hooks (`SessionStart` → pull, `Stop` → push) are declared in the
plugin's own `hooks/hooks.json` inside the plugin directory — **not** written into
`~/.claude/settings.json` or `~/.claude/hooks/`. Claude Code **merges** plugin hooks
with the user's settings.json hooks **additively** per event; it does not replace
them. The user's existing SessionStart/Stop hooks (`session-start-bootstrap.js`,
`cost-tracker.js`, `session-end.js`, `stop-format-typecheck.js`, etc.) continue to run
exactly as before; the plugin's pull/push run alongside them.

Because the plugin's hooks live in the plugin dir, they are **not** part of the synced
payload — syncing `settings.json`/`hooks/` never duplicates or clobbers them. The
plugin is installed per-machine (it appears in the `enabledPlugins` union, so it
auto-installs everywhere). The engine treats the user's `hooks/` and `scripts/` as
**read-only** payload — it copies them, never modifies them.

**Ordering:** the push (`Stop`) must run *after* the user's other Stop hooks finish
writing, so it captures their final state. Hook ordering/priority is a planning detail
to confirm against Claude Code's hook execution semantics.

## 8. Secret-scan guard

Before any push, scan staged file contents for common secret patterns:
- `sk-…`, `ghp_…` / `gho_…`, `AKIA[0-9A-Z]{12,}`, private-key headers
  (`-----BEGIN … PRIVATE KEY-----`), and long values on keys matching
  `*token*` / `*secret*` / `*password*` / `*apikey*`.

On match: **abort the push**, leave config untouched, write the offending
file/location to the log, and surface a one-line warning. No override mechanism in v1.

## 9. Conflict resolution

Newest-wins per file using real signals (local mtime vs repo last-commit time). Every
overwrite is backed up to `~/.claude/backups/sync/<timestamp>/`. Nothing is destroyed
irrecoverably.

**Known limitation:** cross-machine clock skew could misjudge "newest" in a rare
simultaneous-edit case. Backups make it fully recoverable. Documented in the README.

## 10. Error handling

Hooks are non-fatal by contract. Any failure — no network, auth error, git error,
setup not yet run — is caught, logged to `~/.claude/backups/sync/sync.log`, surfaced
as a one-line notice, and the hook exits 0. A session is **never** blocked or broken
by sync. Git network operations use a short timeout so SessionStart cannot hang.

## 11. Testing

Stdlib `unittest`, no network — a local **bare repo** (`file://`) stands in for the
remote.

- **Unit:** manifest parsing; newest-wins decision matrix (equal / repo-newer /
  local-newer); `settings.json` merge (key union, local value precedence, new-key
  default false); secret scan (positive + negative); backup creation.
- **Integration:** two clones + two fake `~/.claude` dirs simulating two machines;
  assert a change on A reaches B, newest-wins + backup behave correctly, and excluded
  paths never sync.
- **Plugin reconciliation:** logic tested against a faked plugin/marketplace state;
  the real CLI calls are mocked.

## 12. Plugin packaging (structure — schema verified in planning)

```
sync_plugin/
  .claude-plugin/plugin.json   # plugin manifest (exact location/schema verified in planning)
  hooks/hooks.json             # SessionStart → pull, Stop → push
  commands/
    sync-setup.md
    sync-status.md
    sync-push.md
  scripts/
    sync_engine.py             # core (stdlib only)
    lib/                       # manifest, resolve, merge, secretscan, backup, gitio
  manifest.default.json        # seeded into the repo on first setup
  tests/
  README.md
```

> The exact plugin manifest location/schema (`.claude-plugin/plugin.json` vs
> `plugin.json`) and hook event names (`Stop` vs `SessionEnd`) are to be confirmed
> against current Claude Code plugin docs during planning.
