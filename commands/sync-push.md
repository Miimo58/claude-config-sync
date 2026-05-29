---
description: Manually push local config changes to the sync remote now
---

Run:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/sync_engine.py" push
```

If the result status is `blocked`, a possible secret was detected and nothing was
pushed — tell the user to check `~/.claude/backups/sync/sync.log` and remove the
secret before retrying.
