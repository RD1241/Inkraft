"""
backup_sqlite.py — simple, consistent SQLite backup for the Inkraft data dir.

Backs up every *.db under settings.DB_DIR using the sqlite3 online-backup API
(safe to run while the app is live) into DATA_DIR/backups/<UTC-timestamp>/, and
prunes to the most recent KEEP backups.

Run manually:        python tools/backup_sqlite.py
Run on a schedule:   point Railway's cron / a host cron at this script.
Override retention:  BACKUP_KEEP=14 python tools/backup_sqlite.py
"""
import os
import sys
import glob
import time
import shutil
import sqlite3
from datetime import datetime, timezone

# Bootstrap so this runs from anywhere (matches the other tools/ scripts).
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import settings  # noqa: E402

KEEP = int(os.environ.get("BACKUP_KEEP", "7"))


def _backup_one(src_db: str, dst_db: str) -> None:
    """Consistent online backup of a single SQLite DB."""
    src = sqlite3.connect(src_db)
    try:
        dst = sqlite3.connect(dst_db)
        try:
            with dst:
                src.backup(dst)
        finally:
            dst.close()
    finally:
        src.close()


def main() -> int:
    db_dir = settings.DB_DIR
    backup_root = os.path.join(os.environ.get("DATA_DIR", settings.BASE_DIR), "backups")
    os.makedirs(backup_root, exist_ok=True)

    db_files = sorted(glob.glob(os.path.join(db_dir, "*.db")))
    if not db_files:
        print(f"[backup] No .db files found in {db_dir}; nothing to do.")
        return 0

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%SZ")
    dest = os.path.join(backup_root, stamp)
    os.makedirs(dest, exist_ok=True)

    for db in db_files:
        name = os.path.basename(db)
        try:
            _backup_one(db, os.path.join(dest, name))
            print(f"[backup] {name} -> {dest}")
        except Exception as e:
            print(f"[backup][WARN] Failed to back up {name}: {e}")

    # Prune old backups, keep the most recent KEEP.
    existing = sorted(
        d for d in glob.glob(os.path.join(backup_root, "*")) if os.path.isdir(d)
    )
    for old in existing[:-KEEP] if KEEP > 0 else []:
        try:
            shutil.rmtree(old)
            print(f"[backup] Pruned old backup {old}")
        except Exception as e:
            print(f"[backup][WARN] Failed to prune {old}: {e}")

    print(f"[backup] Done. Kept newest {KEEP} backup(s) in {backup_root}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
