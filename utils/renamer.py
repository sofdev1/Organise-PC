"""
Bulk renamer.
Format: Name_ext_DDMMYYYY  e.g. invoice_pdf_15082026.pdf
"""

import re
from datetime import datetime
from pathlib import Path

from config import settings
from utils.logger import log_action


def _date_pattern_for_format(fmt: str) -> str:
    """
    Builds a regex fragment matching any timestamp produced by `fmt`, based on
    a sample of today's date in that format — digit runs become \\d{n}, every
    other character (dashes, underscores, etc.) is matched literally.
    """
    sample = datetime.now().strftime(fmt)
    parts = []
    i = 0
    while i < len(sample):
        if sample[i].isdigit():
            j = i
            while j < len(sample) and sample[j].isdigit():
                j += 1
            parts.append(r"\d{%d}" % (j - i))
            i = j
        else:
            parts.append(re.escape(sample[i]))
            i += 1
    return "".join(parts)


def _already_renamed(stem: str, ext: str) -> bool:
    """
    True if `stem` already ends with "_<ext>_<date>" in our own rename format,
    built dynamically for THIS file's actual extension. This matters because
    some legacy Windows extensions (.dl_, .ex_, .ch_, etc.) already contain an
    underscore themselves — a generic [a-zA-Z0-9]-only pattern misses those and
    causes the same file to be renamed again on every run.
    """
    date_pattern = _date_pattern_for_format(settings.RENAME_DATE_FORMAT)
    pattern = re.compile(rf".+_{re.escape(ext)}_{date_pattern}$")
    return bool(pattern.match(stem))


def rename_file(file_path: Path) -> Path:
    """Renames a single file into Name_ext_date format. Returns the new path."""
    if not file_path.is_file():
        return file_path

    stem = file_path.stem
    ext = file_path.suffix.lstrip(".")

    if _already_renamed(stem, ext):
        return file_path  # already in our format for this exact extension — skip

    timestamp = datetime.now().strftime(settings.RENAME_DATE_FORMAT)
    # Keep the original name clean: strip characters that are awkward in filenames
    clean_stem = re.sub(r"[^\w\-]", "_", stem).strip("_") or "file"

    new_name = f"{clean_stem}_{ext}_{timestamp}{file_path.suffix}"
    new_path = file_path.parent / new_name

    # Guard against collisions within the same run
    counter = 1
    while new_path.exists():
        new_path = (
            file_path.parent
            / f"{clean_stem}_{ext}_{timestamp}_{counter}{file_path.suffix}"
        )
        counter += 1

    if settings.DRY_RUN:
        log_action(f"Would rename: {file_path.name} -> {new_path.name}")
        return file_path
    else:
        try:
            file_path.rename(new_path)
        except OSError as e:
            log_action(
                f"FAILED to rename {file_path.name}: {e} — file left as-is, continuing"
            )
            return file_path  # don't crash the whole run over one locked/permission-denied file
        log_action(f"Renamed: {file_path.name} -> {new_path.name}")
        return new_path
