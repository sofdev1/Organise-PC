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
from collections import defaultdict
from pathlib import Path

from config import settings
from utils import (
    ai_namer,
    ai_rename_registry,
    approval_ui,
    converter,
    duplicates,
    renamer,
    screenshots,
    sorter,
    telegram_bot,
)
from utils.logger import log_action

# Duplicate hashes are tracked PER FOLDER (keyed by the file's actual parent
# directory at the time it's checked, i.e. after sorting has already moved it
# to its destination folder). This means duplicate detection only ever compares
# files that live side-by-side in the same folder — not across the whole
# Downloads/Pictures/Videos tree.
_KNOWN_HASHES = defaultdict(dict)


def _rename_with_ai_assist(file_path: Path) -> Path:
    """Tries an AI-suggested rename first; falls back to the standard
    Name_ext_date convention only if AI naming is off/unavailable or the
    file type isn't supported. If the user explicitly declines a
    suggestion, the file is left exactly as-is (not renamed at all) and
    remembered forever, so it's never re-suggested or silently renamed on
    a later sweep.
    """
    if ai_rename_registry.is_ai_named(file_path):
        # Already has an AI-approved name from a previous run — don't burn
        # a Gemini request re-suggesting a name for it.
        return file_path

    if ai_rename_registry.is_declined(file_path):
        # User already said no to this exact file — leave it alone forever.
        return file_path

    if renamer._already_renamed(file_path.stem, file_path.suffix.lstrip(".")):
        # Already in the standard Name_ext_date convention from before this
        # fix existed — leave it alone rather than re-suggesting.
        return file_path

    suggested_stem = ai_namer.suggest_name(file_path)

    if suggested_stem:
        suggested_display_name = f"{suggested_stem}{file_path.suffix}"
        if settings.AI_RENAME_AUTO_APPROVE:
            log_action(
                f"AI rename auto-approved for {file_path.name}: {suggested_display_name}"
            )
            return renamer.rename_file(file_path, override_stem=suggested_stem)

        if settings.AI_RENAME_APPROVAL_MODE == "telegram":
            sent = telegram_bot.request_approval(
                file_path, suggested_stem, suggested_display_name
            )
            if sent:
                # Fire-and-forget — the Telegram callback handler (_on_button)
                # decides approve/decline later, including marking a decline.
                return file_path
            log_action(
                f"Telegram approval unavailable for {file_path.name} — "
                "falling back to the Windows dialog for this file."
            )

        approved = approval_ui.confirm_rename(file_path.name, suggested_display_name)
        if approved:
            return renamer.rename_file(file_path, override_stem=suggested_stem)

        # Declined: leave the file exactly as-is, and remember it so this
        # exact file is never re-suggested or renamed again.
        ai_rename_registry.mark_declined(file_path)
        log_action(
            f"AI rename declined for {file_path.name} — left with original name, will not ask again"
        )
        return file_path

    # No AI suggestion was possible at all (disabled, unavailable, unsupported
    # file type) — this is the ONLY case that still falls back to the plain
    # naming convention.
    return renamer.rename_file(file_path)

def process_downloads_file(file_path: Path):
    if not file_path.exists() or not file_path.is_file():
        return

    if settings.DOWNLOADS_SORT_ENABLED:
        file_path = sorter.sort_file(file_path)

    if settings.DUPLICATE_CHECK_ENABLED:
        folder_key = str(file_path.parent)
        is_dup = duplicates.check_and_flag_duplicate(
            file_path, _KNOWN_HASHES[folder_key]
        )
        if is_dup:
            return  # duplicate moved out — nothing left to rename

    if settings.RENAME_ENABLED:
        _rename_with_ai_assist(file_path)

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
        is_dup = duplicates.check_and_flag_duplicate(
            file_path, _KNOWN_HASHES[folder_key]
        )
        if is_dup:
            return

    if settings.RENAME_ENABLED:
        # Was previously a plain renamer.rename_file() call — meaning every
        # photo/video in Pictures & Videos silently skipped AI naming
        # entirely and only ever got the standard Name_ext_date convention,
        # regardless of AI_RENAME_ENABLED. Route through the same
        # AI-assist path Downloads uses so images actually get considered.
        _rename_with_ai_assist(file_path)


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
                d for d in dirnames if not sorter._is_excluded(root_path / d)
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
