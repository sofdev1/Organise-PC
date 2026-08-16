"""
Sorts files in Downloads into subfolders by type (PDFs, Images, Installers, Zips, ...).
Only acts inside DOWNLOADS_FOLDER. Unmatched extensions are left alone.
"""

import shutil
from pathlib import Path

from config import settings
from utils.logger import log_action

# Category subfolders we manage — used to avoid re-sorting files that are
# already inside one of our own destination folders.
_MANAGED_FOLDER_NAMES = set(settings.DOWNLOADS_CATEGORY_MAP.keys()) | {
    settings.DUPLICATES_FOLDER_NAME,
    settings.SCREENSHOT_DEST_FOLDER_NAME,
}


def _category_for(file_path: Path):
    ext = file_path.suffix.lower()
    for category, extensions in settings.DOWNLOADS_CATEGORY_MAP.items():
        if ext in extensions:
            return category
    return None


def _is_excluded(file_path: Path) -> bool:
    """True if file_path lives anywhere inside one of DOWNLOADS_EXCLUDED_FOLDERS.
    Resolves both sides to absolute paths first, so this is immune to drive-letter
    casing, relative-path quirks, or symlinks — it directly checks 'is this file
    inside that excluded directory', not just 'does a path segment match a name'."""
    try:
        resolved = file_path.resolve()
    except OSError:
        resolved = file_path

    for folder_name in settings.DOWNLOADS_EXCLUDED_FOLDERS:
        excluded_root = (settings.DOWNLOADS_FOLDER / folder_name).resolve()
        if resolved == excluded_root or excluded_root in resolved.parents:
            return True
    return False


def sort_file(file_path: Path) -> Path:
    """Moves a single file into its category subfolder (and an extension
    subfolder within it, for categories listed in SUBSORT_BY_EXTENSION_CATEGORIES).
    Returns the new (or unchanged) path."""
    if not file_path.is_file():
        return file_path

    if _is_excluded(file_path):
        return file_path  # inside an excluded folder (e.g. Projects) — never touch

    # Don't re-sort files already sitting inside a managed subfolder — UNLESS
    # that folder is a category we still need to sub-sort by extension (e.g.
    # files sitting directly in Documents/ before this feature existed).
    parent_name = file_path.parent.name
    grandparent_name = file_path.parent.parent.name if file_path.parent.parent else None

    if grandparent_name in settings.SUBSORT_BY_EXTENSION_CATEGORIES:
        return file_path  # already one level deep in Documents/<ext>/ — done

    if (
        parent_name in _MANAGED_FOLDER_NAMES
        and parent_name not in settings.SUBSORT_BY_EXTENSION_CATEGORIES
    ):
        return (
            file_path  # sitting in a managed folder that doesn't need further sorting
        )

    category = _category_for(file_path)
    if category is None:
        return file_path  # unrecognized type — leave it exactly where it is

    ext_label = file_path.suffix.lower().lstrip(".") or "no_extension"
    if category in settings.SUBSORT_BY_EXTENSION_CATEGORIES:
        dest_folder = settings.DOWNLOADS_FOLDER / category / ext_label
        dest_label = f"{category}/{ext_label}/"
    else:
        dest_folder = settings.DOWNLOADS_FOLDER / category
        dest_label = f"{category}/"

    target_path = dest_folder / file_path.name

    if target_path.exists():
        target_path = dest_folder / f"{file_path.stem}_1{file_path.suffix}"

    if settings.DRY_RUN:
        log_action(f"Would sort: {file_path.name} -> {dest_label}")
        return file_path
    else:
        try:
            dest_folder.mkdir(parents=True, exist_ok=True)
            shutil.move(str(file_path), str(target_path))
        except OSError as e:
            log_action(
                f"FAILED to sort {file_path.name}: {e} — file left as-is, continuing"
            )
            return file_path  # don't crash the whole run over one locked/permission-denied file
        log_action(f"Sorted: {file_path.name} -> {dest_label}")
        return target_path


def sort_existing_downloads():
    """One-off pass over everything currently in Downloads (top level only)."""
    if not settings.DOWNLOADS_FOLDER.exists():
        return
    for file in sorted(settings.DOWNLOADS_FOLDER.iterdir()):
        if file.is_file():
            sort_file(file)
