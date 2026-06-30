"""In-app periodic SQLite backup scheduler.

Runs tools/backup_sqlite.main() on a daemon thread every BACKUP_INTERVAL_HOURS
(default 24). Railway volumes attach to a single service, so a separate cron
service can't reach this service's /data volume — running the backup in-process
is the clean fit. ONLY active when DATA_DIR is set (a host with the persistent
volume, e.g. Railway); local dev is skipped so it doesn't create backup clutter.
A failed backup is logged and never affects request serving (daemon thread).
"""
import os
import time
import threading

_started = False


def _loop(interval_seconds: int, initial_delay: int):
    # Import lazily so a missing dep never blocks app startup.
    from tools.backup_sqlite import main as run_backup
    time.sleep(initial_delay)
    while True:
        try:
            run_backup()
        except Exception as e:
            print(f"[BackupScheduler] backup run failed: {e}")
        time.sleep(interval_seconds)


def start_backup_scheduler():
    """Start the daily SQLite backup thread (prod/volume only). Idempotent."""
    global _started
    if _started:
        return
    if not os.environ.get("DATA_DIR"):
        print("[BackupScheduler] DATA_DIR unset (local dev) — periodic backup disabled.")
        return
    try:
        hours = float(os.environ.get("BACKUP_INTERVAL_HOURS", "24"))
    except ValueError:
        hours = 24.0
    interval = max(3600, int(hours * 3600))  # floor of 1h
    t = threading.Thread(
        target=_loop, args=(interval, 60), daemon=True, name="sqlite-backup"
    )
    t.start()
    _started = True
    print(f"[BackupScheduler] started — SQLite backup every {hours}h (first run in 60s).")
