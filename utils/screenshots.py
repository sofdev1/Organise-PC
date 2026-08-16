"""
Organizes screenshots (from Pictures and Videos) into:
    Screenshots/<image|video>/YYYY-MM/
and renames them to:
    Screenshot_image_DDMMYYYY_HHMMSS.ext
    Screenshot_video_DDMMYYYY_HHMMSS.ext
"""

import shutil
from datetime import datetime
from pathlib import Path

from config import settings
from utils.logger import log_action

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"}
VIDEO_EXTENSIONS = {".mp4", ".mkv", ".mov", ".avi", ".wmv"}


def is_screenshot(file_path: Path) -> bool:
    return settings.SCREENSHOT_KEYWORD in file_path.stem.lower()


def organize_screenshot(file_path: Path) -> Path:
    if not file_path.is_file() or not is_screenshot(file_path):
        return file_path

    # Skip files already inside our managed Screenshots tree
    if settings.SCREENSHOT_DEST_FOLDER_NAME in file_path.parts:
        return file_path

    ext = file_path.suffix.lower()
    if ext in IMAGE_EXTENSIONS:
        media_type = "image"
    elif ext in VIDEO_EXTENSIONS:
        media_type = "video"
    else:
        return file_path  # not a recognized media type, leave alone

    # Use file modification time for the month bucket (closer to "when it was taken")
    mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
    month_folder = mtime.strftime("%Y-%m")
    timestamp = mtime.strftime(settings.RENAME_DATE_FORMAT)

    root = settings.PICTURES_FOLDER if media_type == "image" else settings.VIDEOS_FOLDER
    dest_folder = (
        root / settings.SCREENSHOT_DEST_FOLDER_NAME / media_type / month_folder
    )
    new_name = f"Screenshot_{media_type}_{timestamp}{ext}"
    target_path = dest_folder / new_name

    counter = 1
    while target_path.exists():
        target_path = (
            dest_folder / f"Screenshot_{media_type}_{timestamp}_{counter}{ext}"
        )
        counter += 1

    if settings.DRY_RUN:
        log_action(
            f"Would organize screenshot: {file_path.name} -> {target_path.relative_to(root)}"
        )
        return file_path
    else:
        dest_folder.mkdir(parents=True, exist_ok=True)
        shutil.move(str(file_path), str(target_path))
        log_action(
            f"Organized screenshot: {file_path.name} -> {target_path.relative_to(root)}"
        )
        return target_path


def scan_folder_for_screenshots(folder: Path):
    if not folder.exists():
        return
    for file in sorted(folder.iterdir()):
        if file.is_file():
            organize_screenshot(file)
