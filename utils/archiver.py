"""
Auto-extraction of .zip archives after they've been sorted into Zips/.

Only .zip is handled — Python's built-in zipfile module needs no extra
dependency. .rar/.7z/.tar/.gz are left alone (still sorted into Zips/,
just never auto-extracted); those formats would need external tools
(unrar, 7-Zip, etc.) this project doesn't bundle.

Originals are kept by default (DELETE_ZIP_AFTER_EXTRACT = False in
settings), same convention as HEIC->JPG and MOV->MP4 conversion.
"""

import zipfile
from pathlib import Path
from typing import Optional

from config import settings
from utils.logger import log_action


def _unique_extract_dir(zip_path: Path) -> Path:
    """Picks a target folder named after the zip's stem, inside the same
    parent folder. If that folder already exists (e.g. the same archive
    was downloaded twice), appends _1, _2, etc. rather than overwriting
    or merging into whatever's already there."""
    base = zip_path.with_suffix("")
    candidate = base
    counter = 1
    while candidate.exists():
        candidate = base.with_name(f"{base.name}_{counter}")
        counter += 1
    return candidate


def _is_safe_member(target_dir: Path, member_path: Path) -> bool:
    """Guards against 'zip slip' — a malicious/malformed archive whose
    internal paths use ../ to escape the intended extraction folder."""
    try:
        resolved = member_path.resolve()
        return resolved == target_dir.resolve() or target_dir.resolve() in resolved.parents
    except (OSError, ValueError):
        return False


def extract_zip_archive(file_path: Path) -> Optional[Path]:
    """Extracts a .zip in place (same folder it currently lives in — call
    this AFTER sorter.sort_file() has already moved it into Zips/).

    Returns:
        None            if extraction happened (successfully or would have,
                         under DRY_RUN) — nothing further to rename/dup-check,
                         since the zip is now a folder (or gone).
        file_path        unchanged, if extraction is disabled, the file isn't
                         a .zip, or extraction failed — caller should treat
                         it as a normal file and continue the pipeline.
    """
    if not settings.AUTO_EXTRACT_ZIPS or file_path.suffix.lower() != ".zip":
        return file_path

    if not zipfile.is_zipfile(file_path):
        log_action(f"Skipped extraction: {file_path.name} isn't a valid zip file")
        return file_path

    target_dir = _unique_extract_dir(file_path)

    if settings.DRY_RUN:
        log_action(f"Would extract: {file_path.name} -> {target_dir.name}/")
        return None

    try:
        target_dir.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(file_path) as zf:
            for member in zf.namelist():
                member_target = target_dir / member
                if not _is_safe_member(target_dir, member_target):
                    log_action(
                        f"Skipped unsafe archive entry '{member}' in {file_path.name} "
                        "(would extract outside the target folder)"
                    )
                    continue
                zf.extract(member, target_dir)

        log_action(f"Extracted: {file_path.name} -> {target_dir.name}/")

        if settings.DELETE_ZIP_AFTER_EXTRACT:
            file_path.unlink()
            log_action(f"Deleted original zip after extraction: {file_path.name}")

        return None
    except Exception as e:
        log_action(f"FAILED to extract {file_path.name}: {e} — left as a plain zip file")
        return file_path