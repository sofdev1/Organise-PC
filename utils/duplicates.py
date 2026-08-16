"""
Duplicate detection by file content hash (SHA-256).
Only compares files within the same watched folder tree — never crosses
into unrelated parts of the system.
"""

import hashlib
import shutil
from pathlib import Path
from config import settings
from utils.logger import log_action

_HASH_CACHE = {}  # path_str -> (mtime, size, hash) to avoid re-hashing unchanged files


def _hash_file(path: Path, chunk_size: int = 65536) -> str:
    key = str(path)
    try:
        stat = path.stat()
    except OSError:
        return ""

    cached = _HASH_CACHE.get(key)
    if cached and cached[0] == stat.st_mtime and cached[1] == stat.st_size:
        return cached[2]

    try:
        sha256 = hashlib.sha256()
        with open(path, "rb") as f:
            while chunk := f.read(chunk_size):
                sha256.update(chunk)
        digest = sha256.hexdigest()
    except OSError as e:
        log_action(
            f"FAILED to hash {path.name}: {e} — skipping duplicate check for this file"
        )
        return ""

    _HASH_CACHE[key] = (stat.st_mtime, stat.st_size, digest)
    return digest


def check_and_flag_duplicate(file_path: Path, known_hashes: dict) -> bool:
    """
    Checks a single file against a dict of {hash: path} seen so far in this run.
    If it's a duplicate, moves it to a 'Duplicates' subfolder next to it.
    Returns True if the file was flagged as a duplicate.

    Files already sitting inside a Duplicates folder are skipped entirely — they've
    already been flagged once, so we never re-compare them against each other
    (which would otherwise create a nested Duplicates/Duplicates/ folder).
    """
    if not file_path.is_file():
        return False

    if file_path.parent.name == settings.DUPLICATES_FOLDER_NAME:
        return False  # already resolved — don't re-flag or nest further

    file_hash = _hash_file(file_path)
    if not file_hash:
        return False

    if file_hash in known_hashes:
        original = known_hashes[file_hash]
        dup_folder = file_path.parent / settings.DUPLICATES_FOLDER_NAME
        target = dup_folder / file_path.name

        if settings.DRY_RUN:
            log_action(
                f"Would flag duplicate: {file_path.name} (same content as {original.name}) -> {target}"
            )
        else:
            try:
                dup_folder.mkdir(exist_ok=True)
                if target.exists():
                    target = dup_folder / f"{file_path.stem}_dup{file_path.suffix}"
                shutil.move(str(file_path), str(target))
            except OSError as e:
                log_action(
                    f"FAILED to move duplicate {file_path.name}: {e} — file left as-is, continuing"
                )
                return False  # don't crash the whole run over one locked/permission-denied file
            log_action(
                f"Moved duplicate: {file_path.name} (same content as {original.name}) -> {target}"
            )
        return True

    known_hashes[file_hash] = file_path
    return False


def scan_folder_for_duplicates(folder: Path):
    """One-off scan of a folder (non-recursive into Duplicates/ itself)."""
    known_hashes = {}
    if not folder.exists():
        return

    for file in sorted(folder.iterdir()):
        if file.is_file() and file.parent.name != settings.DUPLICATES_FOLDER_NAME:
            check_and_flag_duplicate(file, known_hashes)
