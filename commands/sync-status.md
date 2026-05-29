---
description: Show config sync status (remote, branch, pending changes)
---

Run:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/sync_engine.py" status
```

Summarize the JSON for the user: whether sync is configured, the remote URL, the
current branch line, and how many files differ from the last commit.
