"""
Organise_PC — entry point.

Run this to start watching Downloads, Pictures, and Videos.
For DRY RUN vs LIVE mode, edit config/settings.py -> DRY_RUN.

Usage:
    python main.py

Only ONE instance is allowed to run at a time (see _acquire_single_instance_lock
below) — if you try to launch a second one, it exits immediately instead of
running alongside the first. This prevents duplicate/competing background
processes from ever stacking up (e.g. one per login, or one per manual test run).
"""

import sys
import socket

from core import watcher

# Fixed local port used purely as a mutex — nothing is sent over it. Binding
# a TCP socket like this is a reliable single-instance lock on Windows: if
# another instance is already running, the bind fails immediately; if the
# process crashes or is killed, the OS releases the port automatically (no
# stale lock file to clean up manually).
_LOCK_PORT = 54891
_lock_socket = None


def _acquire_single_instance_lock() -> bool:
    global _lock_socket
    _lock_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        _lock_socket.bind(("127.0.0.1", _LOCK_PORT))
        return True
    except OSError:
        return False


if __name__ == "__main__":
    if not _acquire_single_instance_lock():
        print("PC Automation Suite is already running (another instance holds the lock).")
        print("Check Task Manager for an existing pythonw.exe / python.exe process, or")
        print("check logs/activity.log for the currently running instance's activity.")
        sys.exit(0)

    watcher.start()