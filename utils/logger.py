"""
Simple shared logger — writes to console and to logs/activity.log
"""

import logging
from config import settings

logger = logging.getLogger("pc_automation")
logger.setLevel(logging.INFO)

if not logger.handlers:
    formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s", "%Y-%m-%d %H:%M:%S")

    file_handler = logging.FileHandler(settings.LOG_FILE, encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)


def log_action(action: str, dry_run: bool = None):
    """Prefix log lines with [DRY RUN] when in dry-run mode."""
    if dry_run is None:
        dry_run = settings.DRY_RUN
    prefix = "[DRY RUN] " if dry_run else ""
    logger.info(f"{prefix}{action}")
