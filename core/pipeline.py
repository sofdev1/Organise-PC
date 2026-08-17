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
from collections import defaultdict
from config import settings
from utils import sorter, screenshots, converter, duplicates, renamer

# Duplicate hashes are tracked PER FOLDER (keyed by the file's actual parent
# directory at the time it's checked, i.e. after sorting has already moved it
# to its destination folder). This means duplicate detection only ever compares
# files that live side-by-side in the same folder — not across the whole
# Downloads/Pictures/Videos tree.
_KNOWN_HASHES = defaultdict(dict)


def process_downloads_file(file_path: Path):
    if not file_path.exists() or not file_path.is_file():
        return

    if settings.DOWNLOADS_SORT_ENABLED:
        file_path = sorter.sort_file(file_path)

    if settings.DUPLICATE_CHECK_ENABLED:
        folder_key = str(file_path.parent)
        is_dup = duplicates.check_and_flag_duplicate(file_path, _KNOWN_HASHES[folder_key])
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
        folder_key = str(file_path.parent)
        duplicates.check_and_flag_duplicate(file_path, _KNOWN_HASHES[folder_key])


def run_initial_sweep():
    """One pass over existing files in all 3 folders at startup, using the same pipeline.
    Downloads is walked manually (not Path.rglob) so excluded folders (e.g. Projects) are
    pruned from the walk entirely and never descended into — not just skipped per-file.
    """
    if settings.DOWNLOADS_FOLDER.exists():
        downloads_files = []
        for root, dirnames, filenames in os.walk(settings.DOWNLOADS_FOLDER):
            root_path = Path(root)
            dirnames[:] = [
                d for d in dirnames
                if not sorter._is_excluded(root_path / d)
            ]
            for name in sorted(filenames):
                downloads_files.append(root_path / name)

        for f in downloads_files:
            process_downloads_file(f)

    if settings.PICTURES_FOLDER.exists():
        for f in sorted(settings.PICTURES_FOLDER.rglob("*")):
            if f.is_file():
                process_media_file(f)

    if settings.VIDEOS_FOLDER.exists():
        for f in sorted(settings.VIDEOS_FOLDER.rglob("*")):
            if f.is_file():
                process_media_file(f)
