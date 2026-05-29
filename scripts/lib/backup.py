"""Back up a config file before it is overwritten by sync."""
import os
import shutil
from typing import Optional

BACKUP_SUBDIR = os.path.join("backups", "sync")


def backup_file(claude_dir: str, relpath: str, timestamp: str) -> Optional[str]:
    """Copy <claude_dir>/<relpath> into backups/sync/<timestamp>/<relpath>.

    Returns the backup path, or None if the source does not exist or the
    resolved destination escapes the backup root (path traversal guard).
    """
    src = os.path.join(claude_dir, relpath)
    if not os.path.isfile(src):
        return None
    backup_root = os.path.realpath(
        os.path.join(claude_dir, BACKUP_SUBDIR, timestamp))
    dest = os.path.realpath(os.path.join(backup_root, relpath))
    if not dest.startswith(backup_root + os.sep):
        return None  # refuse traversal outside backup root
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    shutil.copy2(src, dest)
    return dest
