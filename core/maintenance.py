"""
System maintenance — runs on a schedule (not triggered by file events).

1. Disk space check — warns if usage crosses a threshold.
2. Temp file cleanup — clears OS temp directories ONLY (never touches
   Downloads / Pictures / Videos).
3. Large file report — flags large files inside the 3 watched folders
   (report only, nothing is moved or deleted).
"""

import os
import shutil
import tempfile
from datetime import datetime
from pathlib import Path

from config import settings
from utils.logger import log_action


def check_disk_space():
    usage = shutil.disk_usage(Path.home().anchor)
    percent_used = (usage.used / usage.total) * 100

    if percent_used >= settings.DISK_SPACE_WARNING_PERCENT:
        log_action(
            f"WARNING: Disk usage at {percent_used:.1f}% (threshold {settings.DISK_SPACE_WARNING_PERCENT}%)"
        )
    else:
        log_action(f"Disk usage OK: {percent_used:.1f}% used")

    return percent_used


def clean_temp_files():
    """Clears the OS temp directory only. Never touches user folders."""
    if not settings.TEMP_CLEAN_ENABLED:
        return

    temp_dir = Path(tempfile.gettempdir())
    cleared = 0
    freed_bytes = 0

    for item in temp_dir.iterdir():
        try:
            if item.is_file():
                size = item.stat().st_size
                if settings.DRY_RUN:
                    log_action(f"Would delete temp file: {item.name}")
                else:
                    item.unlink()
                    freed_bytes += size
                cleared += 1
            elif item.is_dir():
                if settings.DRY_RUN:
                    log_action(f"Would delete temp folder: {item.name}")
                else:
                    shutil.rmtree(item, ignore_errors=True)
                cleared += 1
        except (PermissionError, OSError):
            continue  # skip files in use — never force anything

    log_action(
        f"Temp cleanup: {cleared} item(s) {'would be ' if settings.DRY_RUN else ''}cleared "
        f"({freed_bytes / (1024*1024):.1f} MB freed)"
    )


def large_file_report():
    """Scans ONLY Downloads, Pictures, Videos. Report-only — nothing is moved."""
    watched_folders = [
        settings.DOWNLOADS_FOLDER,
        settings.PICTURES_FOLDER,
        settings.VIDEOS_FOLDER,
    ]
    threshold_bytes = settings.LARGE_FILE_THRESHOLD_MB * 1024 * 1024
    large_files = []

    for folder in watched_folders:
        if not folder.exists():
            continue
        for file in folder.rglob("*"):
            if file.is_file():
                try:
                    size = file.stat().st_size
                    if size >= threshold_bytes:
                        large_files.append((file, size))
                except OSError:
                    continue

    with open(settings.REPORT_FILE, "w", encoding="utf-8") as f:
        f.write(f"Large File Report — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Threshold: {settings.LARGE_FILE_THRESHOLD_MB} MB\n")
        f.write("=" * 60 + "\n")
        if not large_files:
            f.write("No large files found.\n")
        for file, size in sorted(large_files, key=lambda x: -x[1]):
            f.write(f"{size / (1024*1024):.1f} MB  —  {file}\n")

    log_action(
        f"Large file report generated: {len(large_files)} file(s) over {settings.LARGE_FILE_THRESHOLD_MB}MB"
    )


def run_maintenance():
    log_action("--- Running system maintenance ---")
    check_disk_space()
    clean_temp_files()
    large_file_report()
    log_action("--- Maintenance complete ---")
