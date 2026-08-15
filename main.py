"""
Organise_PC — entry point.

Run this to start watching Downloads, Pictures, and Videos.
For DRY RUN vs LIVE mode, edit config/settings.py -> DRY_RUN.

Usage:
    python main.py
"""

from core import watcher

if __name__ == "__main__":
    watcher.start()
