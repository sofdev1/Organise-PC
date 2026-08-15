"""
The processing pipeline applied to every file event.

Order matters:
  1. Screenshot organize (Pictures/Videos only) — pulls screenshots out first
  2. Format conversion (HEIC->JPG, MOV->MP4)
  3. Downloads sort (by type, Downloads only)
  4. Duplicate check (content hash)
  5. Rename (Name_ext_date_time) — always last, so earlier steps see clean names
"""
import os
from pathlib import Path
from config import settings
from utils import sorter, screenshots, converter, duplicates, renamer

# Duplicate hashes are tracked per-folder for the lifetime of the running process
_KNOWN_HASHES = {
    "downloads": {},
    "pictures": {},
    "videos": {},
}


def _folder_key(path: Path) -> str:
    try:
        path.relative_to(settings.DOWNLOADS_FOLDER)
        return "downloads"
    except ValueError:
        pass
    try:
        path.relative_to(settings.PICTURES_FOLDER)
        return "pictures"
    except ValueError:
        pass
    try:
        path.relative_to(settings.VIDEOS_FOLDER)
        return "videos"
    except ValueError:
        return "downloads"


def process_downloads_file(file_path: Path):
    if not file_path.exists() or not file_path.is_file():
        return

    if settings.DOWNLOADS_SORT_ENABLED:
        file_path = sorter.sort_file(file_path)

    if settings.DUPLICATE_CHECK_ENABLED:
        is_dup = duplicates.check_and_flag_duplicate(file_path, _KNOWN_HASHES["downloads"])
        if is_dup:
            return  # duplicate moved out — nothing left to rename

    if settings.RENAME_ENABLED:
        renamer.rename_file(file_path)

    if sorter._is_excluded(file_path):
        return  # inside an excluded folder (e.g. Projects) — never touch


def process_media_file(file_path: Path):
    """Used for both Pictures and Videos folders."""
    if not file_path.exists() or not file_path.is_file():
        return

    if settings.SCREENSHOT_ORGANIZE_ENABLED and screenshots.is_screenshot(file_path):
        file_path = screenshots.organize_screenshot(file_path)

    ext = file_path.suffix.lower()
    if ext == ".heic":
        file_path = converter.convert_heic_to_jpg(file_path)
    elif ext == ".mov":
        file_path = converter.convert_mov_to_mp4(file_path)

    if settings.DUPLICATE_CHECK_ENABLED:
        key = _folder_key(file_path)
        duplicates.check_and_flag_duplicate(file_path, _KNOWN_HASHES[key])


def run_initial_sweep():
    """One pass over existing files in all 3 folders at startup, using the same pipeline.
    Downloads is walked manually (not Path.rglob) so excluded folders (e.g. Projects) are
    pruned from the walk entirely and never descended into — not just skipped per-file."""
    if settings.DOWNLOADS_FOLDER.exists():
        for root, dirnames, filenames in os.walk(settings.DOWNLOADS_FOLDER):
            root_path = Path(root)
            dirnames[:] = [
                d for d in dirnames
                if not sorter._is_excluded(root_path / d)
            ]
            for name in sorted(filenames):
                process_downloads_file(root_path / name)

    if settings.PICTURES_FOLDER.exists():
        for f in sorted(settings.PICTURES_FOLDER.rglob("*")):
            if f.is_file():
                process_media_file(f)

    if settings.VIDEOS_FOLDER.exists():
        for f in sorted(settings.VIDEOS_FOLDER.rglob("*")):
            if f.is_file():
                process_media_file(f)
