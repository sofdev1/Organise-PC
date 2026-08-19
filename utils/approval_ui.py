"""
Approval prompt for AI-suggested filenames.

Organise_PC runs as a background watcher (often via pythonw.exe with no
console attached), so we can't rely on `input()` — it can silently fail or
never be seen. Instead this pops a native Windows message box, which works
regardless of whether a console window exists.

The box times out after AI_RENAME_APPROVAL_TIMEOUT_SECONDS and defaults to
"No" on timeout — a missed prompt should never leave a file unrenamed AND
un-fallback-renamed; the pipeline always does one or the other.

Non-Windows fallback: uses a plain console input() with the same timeout
default, so the project still runs (degraded) on macOS/Linux for testing.
"""

import platform

from config import settings
from utils.logger import log_action

IS_WINDOWS = platform.system() == "Windows"

# MessageBoxTimeoutW return codes we care about
_IDYES = 6
_IDTIMEOUT = 32000

_MB_YESNO = 0x00000004
_MB_ICONQUESTION = 0x00000020
_MB_TOPMOST = 0x00040000
_MB_SETFOREGROUND = 0x00010000


def _ask_windows(original_name: str, suggested_display_name: str) -> bool:
    import ctypes

    timeout_ms = settings.AI_RENAME_APPROVAL_TIMEOUT_SECONDS * 1000
    text = (
        f"Organise_PC suggests renaming:\n\n"
        f"  {original_name}\n"
        f"to:\n"
        f"  {suggested_display_name}\n\n"
        f"Rename it? (auto-'No' in {settings.AI_RENAME_APPROVAL_TIMEOUT_SECONDS}s)"
    )
    flags = _MB_YESNO | _MB_ICONQUESTION | _MB_TOPMOST | _MB_SETFOREGROUND

    user32 = ctypes.windll.user32
    try:
        # MessageBoxTimeoutW is undocumented but has shipped in user32.dll
        # since Windows 2000 — used here so an unattended watcher never
        # blocks forever waiting on a dialog nobody sees.
        result = user32.MessageBoxTimeoutW(
            0, text, "Organise_PC — AI rename suggestion", flags, 0, timeout_ms
        )
    except AttributeError:
        # Extremely old/locked-down systems without MessageBoxTimeoutW —
        # fall back to a plain (non-timing-out) MessageBoxW.
        result = user32.MessageBoxW(0, text, "Organise_PC — AI rename suggestion", flags)

    if result == _IDTIMEOUT:
        log_action(f"AI rename prompt timed out for {original_name} — defaulting to No")
        return False
    return result == _IDYES


def _ask_console(original_name: str, suggested_display_name: str) -> bool:
    """Non-Windows fallback for dev/testing — no real timeout enforcement."""
    prompt = (
        f"\nAI suggests renaming '{original_name}' -> '{suggested_display_name}'. "
        "Rename? [y/N]: "
    )
    try:
        answer = input(prompt).strip().lower()
    except EOFError:
        return False
    return answer == "y"


def confirm_rename(original_name: str, suggested_display_name: str) -> bool:
    """Shows the approval prompt and returns True only on an explicit Yes.
    Any failure (no display attached, headless session, etc.) safely
    defaults to False so the pipeline falls back to the standard rename.
    When auto-approval is enabled, the dialog is bypassed entirely."""
    if settings.AI_RENAME_AUTO_APPROVE:
        log_action(f"AI rename auto-approved for {original_name}: {suggested_display_name}")
        return True

    try:
        if IS_WINDOWS:
            return _ask_windows(original_name, suggested_display_name)
        return _ask_console(original_name, suggested_display_name)
    except Exception as e:
        log_action(f"AI rename approval prompt failed ({e}) — defaulting to No")
        return False
