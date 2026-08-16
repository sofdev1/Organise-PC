"""
Standalone cleanup script — reverses the "_<ext>_<date>" suffix added by the
main suite's renamer, restoring original filenames.

SCOPE: by default this ONLY targets legacy Windows driver-cache style
extensions that end in an underscore (.dl_, .ex_, .ch_, .bi_, .da_, .ic_,
.pr_, .in_, .up_, .xp_, .AV_, etc.) — the files whose renaming broke due to
their unusual extension. Normal files (.docx, .pptx, .csv, images, etc.) are
left completely alone.

To widen scope, edit TARGET_EXTENSIONS below (see comment there).

Example:
    cnabb809_dl__15082026.dl_ -> cnabb809.dl_

This is separate from main.py — run it manually, it does not run
automatically or watch folders.

Usage:
    python cleanup_rename.py

Scope: Downloads, Pictures, Videos only (same as the main suite), and it
skips the same DOWNLOADS_EXCLUDED_FOLDERS (e.g. Projects/).

Self-contained: only depends on config/settings.py (no other project files),
so it can be dropped into the project root on its own.
"""

import re
from pathlib import Path
from datetime import datetime

from config import settings

DRY_RUN = False  # <-- keep True until you've reviewed the preview, then set False to actually rename
PAGE_SIZE = 20

# Only files whose extension matches this filter are touched.
# Default: extensions ending in "_" (legacy Windows driver-cache files like
# .dl_, .ex_, .ch_, .bi_, .da_, .ic_, .pr_, .in_, .up_, .xp_, .AV_) PLUS the
# extra extensions listed below (driver/installer files that don't end in
# an underscore themselves, but are the same kind of file: .dll, .inf, .cat).
TARGET_EXTENSIONS = (
    "ends_with_underscore"  # "ends_with_underscore" | None | a list like ["dl_", "ex_"]
)
EXTRA_EXTENSIONS = [
    "dll",
    "inf",
    "cat",
    "ini",
]  # matched case-insensitively, in addition to TARGET_EXTENSIONS


def _matches_scope(ext: str) -> bool:
    if ext.lower() in (e.lower() for e in EXTRA_EXTENSIONS):
        return True
    if TARGET_EXTENSIONS is None:
        return True
    if TARGET_EXTENSIONS == "ends_with_underscore":
        return ext.endswith("_")
    return ext in TARGET_EXTENSIONS


# ---------------------------------------------------------------------------
# Self-contained helpers (no dependency on utils/ beyond what's guaranteed
# to exist, so this script works even if your utils/ folder is out of date)
# ---------------------------------------------------------------------------


def _date_pattern_for_format(fmt: str) -> str:
    """Builds a regex fragment matching any timestamp produced by `fmt` —
    digit runs become \\d{n}, everything else matched literally."""
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


def _is_excluded(file_path: Path) -> bool:
    """True if file_path lives inside a folder listed in DOWNLOADS_EXCLUDED_FOLDERS."""
    excluded_folders = getattr(settings, "DOWNLOADS_EXCLUDED_FOLDERS", [])
    try:
        resolved = file_path.resolve()
    except OSError:
        resolved = file_path
    for folder_name in excluded_folders:
        excluded_root = (settings.DOWNLOADS_FOLDER / folder_name).resolve()
        if resolved == excluded_root or excluded_root in resolved.parents:
            return True
    return False


def _paginate(lines, page_size=PAGE_SIZE, title="Changes"):
    total = len(lines)
    if total == 0:
        print(f"\n{title}: none.\n")
        return
    print(f"\n{title}: {total} total\n" + "=" * 50)
    for i in range(0, total, page_size):
        page = lines[i : i + page_size]
        start_num, end_num = i + 1, min(i + page_size, total)
        for offset, line in enumerate(page):
            print(f"{start_num + offset:>4}. {line}")
        remaining = total - end_num
        if remaining <= 0:
            print("=" * 50)
            print(f"End of list ({total} total).\n")
            break
        print("-" * 50)
        user_input = (
            input(
                f"Showing {start_num}-{end_num} of {total}. "
                f"Press Enter for next {min(page_size, remaining)} (or 'q' to stop): "
            )
            .strip()
            .lower()
        )
        if user_input == "q":
            print(f"Stopped. {remaining} more item(s) not shown.\n")
            break


# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------


def _strip_suffix(file_path: Path):
    """If file_path matches our own '_<ext>_<date>[_<N>]' rename format AND its
    extension is in scope, returns the original path (suffix stripped).
    Otherwise returns None."""
    stem = file_path.stem
    ext = file_path.suffix.lstrip(".")

    if not _matches_scope(ext):
        return None

    date_pattern = _date_pattern_for_format(settings.RENAME_DATE_FORMAT)
    # Optional trailing "_N" collision counter (e.g. "..._15082026_1")
    pattern = re.compile(
        rf"^(?P<original>.+)_{re.escape(ext)}_{date_pattern}(?:_\d+)?$"
    )

    match = pattern.match(stem)
    if not match:
        return None

    original_stem = match.group("original")
    restored_suffix = file_path.suffix
    if restored_suffix.endswith("_"):
        restored_suffix = restored_suffix[:-1]  # drop the trailing underscore too

    restored_name = f"{original_stem}{restored_suffix}"
    restored_path = file_path.parent / restored_name

    counter = 1
    while restored_path.exists() and restored_path != file_path:
        restored_path = file_path.parent / f"{original_stem}_{counter}{restored_suffix}"
        counter += 1

    return restored_path


def run():
    print(f"Cleanup starting (DRY_RUN={DRY_RUN})")
    print(f"Scope: extensions matching {TARGET_EXTENSIONS!r}")
    print("Scanning: Downloads, Pictures, Videos ...")

    actions = []
    folders = [
        settings.DOWNLOADS_FOLDER,
        settings.PICTURES_FOLDER,
        settings.VIDEOS_FOLDER,
    ]

    for folder in folders:
        if not folder.exists():
            continue
        for file_path in sorted(folder.rglob("*")):
            if not file_path.is_file():
                continue
            if _is_excluded(file_path):
                continue

            restored_path = _strip_suffix(file_path)
            if restored_path is None:
                continue

            if DRY_RUN:
                actions.append(
                    f"Would restore: {file_path.name} -> {restored_path.name}"
                )
            else:
                file_path.rename(restored_path)
                actions.append(f"Restored: {file_path.name} -> {restored_path.name}")

    _paginate(actions, title="Filenames to restore")

    if DRY_RUN:
        print(
            "\nNothing was actually renamed. Set DRY_RUN = False in this script to apply it for real."
        )
    else:
        print("\nDone. Original filenames restored where matched.")


if __name__ == "__main__":
    run()
