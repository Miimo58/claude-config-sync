---
description: Configure config sync for this machine against a private git remote
argument-hint: <git-remote-url>
---

Run the sync engine setup with the provided remote URL.

Run this exact command (substituting the user's URL for `$ARGUMENTS`):

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/sync_engine.py" setup "$ARGUMENTS"
```

If the repo is empty, it is seeded from this machine's config. If it already has
content, this machine is synced from the repo (newest-wins, with backups under
`~/.claude/backups/sync/`). Report the command's output to the user.
