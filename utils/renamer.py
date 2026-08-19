"""
Bulk renamer.
Format: Name_ext_DDMMYYYY  e.g. invoice_pdf_15082026.pdf
"""

import re
from datetime import datetime
from pathlib import Path

from config import settings
from utils import ai_rename_registry
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


def rename_file(file_path: Path, override_stem: str | None = None) -> Path:
    """Renames a single file into Name_ext_date format. Returns the new path.

    override_stem: if given (e.g. an AI-suggested, user-approved name), that
    stem is used instead of the original filename's stem — everything else
    (extension, timestamp, collision handling, DRY_RUN, logging) still
    applies exactly as normal.
    """
    if not file_path.is_file():
        return file_path

    stem = file_path.stem
    ext = file_path.suffix.lstrip(".")

    if override_stem is None and _already_renamed(stem, ext):
        return file_path  # already in our format for this exact extension — skip

    if override_stem is None and ai_rename_registry.is_ai_named(file_path):
        # This exact file already has a human/AI-approved descriptive name
        # from a previous run. We're only here now because THIS pass has no
        # override_stem to offer (AI unavailable/declined/quota-limited) —
        # that must never mean "treat it like an unrenamed file and stamp
        # the ugly Name_ext_date convention on it", so leave it untouched.
        return file_path

    timestamp = datetime.now().strftime(settings.RENAME_DATE_FORMAT)
    # Keep the original name clean: strip characters that are awkward in filenames
    if override_stem is not None:
        # AI-approved name: use the clean suggested name as-is (no
        # _<ext>_<date> suffix) — the user already approved this exact
        # name, so we shouldn't decorate it further. Collision handling
        # below still applies.
        clean_stem = re.sub(r"[^\w\-]", "_", override_stem).strip("_") or "file"
        new_name = f"{clean_stem}{file_path.suffix}"
    else:
        clean_stem = re.sub(r"[^\w\-]", "_", stem).strip("_") or "file"
        new_name = f"{clean_stem}_{ext}_{timestamp}{file_path.suffix}"

    new_path = file_path.parent / new_name

    # Guard against collisions within the same run
    counter = 1
    while new_path.exists() and new_path != file_path:
        new_path = file_path.parent / f"{clean_stem}_{counter}{file_path.suffix}"
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
        if override_stem is not None:
            # This was an AI-approved rename — remember it forever, so a
            # future run with AI unavailable never downgrades it back to
            # the standard convention.
            ai_rename_registry.forget(file_path)
            ai_rename_registry.mark_ai_named(new_path)
        return new_path
