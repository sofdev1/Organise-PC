"""
Tracks which files have already been given an AI-approved name, so a later
sweep — one where Gemini happens to be unavailable (quota, network,
missing API key, etc.) — never "downgrades" an already-nicely-named file
back into the ugly Name_ext_date convention.

Without this, utils/renamer.py's _already_renamed() check only recognizes
its OWN generated suffix format. A file that was renamed to a clean AI
name (no _ext_date suffix, by design — see renamer.rename_file) doesn't
match that pattern, so on any run where AI naming can't be reached, it
looks exactly like a brand-new, never-renamed file and gets the standard
convention slapped onto it — silently erasing every approved AI name.

Persisted as a small JSON file so it survives restarts. Best-effort: any
read/write failure just means we might re-suggest a name for a file we'd
already handled, never that we accidentally destroy user data.
"""

import json
import threading
from pathlib import Path
from typing import Set

from config import settings

_REGISTRY_FILE = settings.LOG_FOLDER / "ai_named_files.json"
_LOCK = threading.Lock()
_CACHE: Set[str] = None  # loaded lazily, kept in sync with disk on every mutation


def _resolve(path: Path) -> str:
    try:
        return str(path.resolve())
    except OSError:
        return str(path)


def _load() -> Set[str]:
    global _CACHE
    if _CACHE is not None:
        return _CACHE
    try:
        data = json.loads(_REGISTRY_FILE.read_text(encoding="utf-8"))
        _CACHE = set(data) if isinstance(data, list) else set()
    except (OSError, ValueError):
        _CACHE = set()
    return _CACHE


def _save() -> None:
    try:
        _REGISTRY_FILE.write_text(json.dumps(sorted(_CACHE)), encoding="utf-8")
    except OSError:
        pass  # best-effort — a failed write just means this survives one less restart


def is_ai_named(path: Path) -> bool:
    """True if this exact path was previously given an AI-approved name —
    i.e. it should be left alone, not re-processed by the standard
    Name_ext_date convention."""
    with _LOCK:
        return _resolve(path) in _load()


def mark_ai_named(path: Path) -> None:
    """Call after a file has actually been renamed to an AI-approved name."""
    with _LOCK:
        _load().add(_resolve(path))
        _save()


def forget(path: Path) -> None:
    """Call when a path is about to change (e.g. right before renaming it
    again), so a stale entry for its old name doesn't linger forever."""
    with _LOCK:
        cache = _load()
        resolved = _resolve(path)
        if resolved in cache:
            cache.discard(resolved)
            _save()
