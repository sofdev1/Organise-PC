"""
Central configuration for Organise_PC.
Edit the paths below to match your system before running.
"""

import os
from pathlib import Path

try:
    from dotenv import load_dotenv

    # Loads GEMINI_API_KEY / TELEGRAM_* etc. from a .env file sitting next to
    # this project's root (see .env.example), so you don't have to manually
    # set them in every new terminal session. Silently does nothing if
    # python-dotenv isn't installed or there's no .env file — everything
    # still works via real environment variables either way.
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
except ImportError:
    pass

# ============================================================
# SCOPE — the suite ONLY ever touches these three folders.
# Nothing outside these paths is read, moved, renamed, or deleted.
# ============================================================
HOME = Path.home()

DOWNLOADS_FOLDER = HOME / "Downloads"
PICTURES_FOLDER = HOME / "Pictures"
VIDEOS_FOLDER = HOME / "Videos"

# ============================================================
# SAFETY
# ============================================================
DRY_RUN = False  # <-- Keep True until you've reviewed the logs. Set False to let it actually act.

# ============================================================
# DOWNLOADS SORTING (by file type)
# ============================================================
DOWNLOADS_SORT_ENABLED = True

DOWNLOADS_CATEGORY_MAP = {
    "PDFs": [".pdf"],
    "Images": [".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".heic", ".svg"],
    "Installers": [".exe", ".msi", ".dmg", ".pkg", ".apk"],
    "Zips": [".zip", ".rar", ".7z", ".tar", ".gz"],
    "Documents": [".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".txt", ".csv"],
    "Videos": [".mp4", ".mkv", ".mov", ".avi", ".wmv"],
    "Audio": [".mp3", ".wav", ".flac", ".m4a"],
}
# Folders inside Downloads that must NEVER be touched, scanned, or moved —
# matched by folder name anywhere in a file's path under Downloads. Add any
# folder here that you don't want this suite reaching into (e.g. the folder
# this project itself lives in, work-in-progress folders, etc.).
DOWNLOADS_EXCLUDED_FOLDERS = ["Projects"]
# Anything not matched above is left untouched in Downloads (not "Other"-bucketed),
# so unrecognized files are never silently moved.
# Within the "Documents" category, further split into subfolders by extension
# (e.g. Documents/pdf/, Documents/docx/, Documents/xlsx/). Set to a list of
# category names to apply this to more than just Documents, or [] to disable.
SUBSORT_BY_EXTENSION_CATEGORIES = ["Documents"]

# ============================================================
# AUTO-RENAME (applies to files in Downloads AFTER sorting)
# Format: Name_ext_DDMMYYYY_HHMMSS  e.g. invoice_pdf_15082026_143210
# ============================================================
RENAME_ENABLED = True
RENAME_DATE_FORMAT = "%d%m%Y"

# ============================================================
# AI-ASSISTED RENAME (optional layer on top of AUTO-RENAME above)
# Before falling back to Name_ext_date, tries reading the file's content,
# asks Google Gemini for a short descriptive name, and pops a Windows Yes/No
# dialog for you to approve it. Declined / failed / unsupported file types
# always fall straight through to the normal AUTO-RENAME convention above —
# this never blocks or skips a file.
#
# Requires:
#   pip install google-genai pypdf python-docx
#   A GEMINI_API_KEY environment variable set on this machine.
#
# Gemini 2.5 Flash-Lite has a free API tier (subject to Google's current
# rate limits). No credit card is required for the free tier in eligible use.
# ============================================================
AI_RENAME_ENABLED = True  # <-- flip to True once GEMINI_API_KEY is set
AI_RENAME_MODEL = "gemini-3.5-flash-lite"  # free-tier friendly, fast naming model
AI_RENAME_EXTENSIONS = [
    ".pdf", ".docx", ".txt", ".csv", ".md",
    ".jpg", ".jpeg", ".png",
]
AI_RENAME_PREVIEW_CHARS = 3000  # how much text content to send per file
AI_RENAME_MAX_IMAGE_MB = 5  # images larger than this skip AI naming (still gets standard rename)
AI_RENAME_MAX_WORDS = 6
AI_RENAME_MAX_CHARS = 60  # hard cap on the suggested filename stem length
AI_RENAME_TIMEOUT_SECONDS = 15  # API call timeout
# Minimum gap enforced between successive Gemini calls, across every file
# and every thread. Free tier is 15 requests/minute -> 60/15 = 4s apart is
# the bare minimum; padded a bit so a slightly slow response never still
# tips you over. Without this, a big initial sweep fires a burst of
# requests, exhausts the quota in the first few seconds, and every file
# scanned during the resulting ~30-60s cooldown silently skips AI naming
# and falls back to the plain convention — not a per-file failure, just
# bad timing. Increase this if you're still seeing 429/RESOURCE_EXHAUSTED
# in logs/activity.log, or raise it further if you're on a paid tier with
# more headroom and want faster sweeps.
AI_RENAME_MIN_INTERVAL_SECONDS = 4.5
AI_RENAME_AUTO_APPROVE = False  # True = rename instantly, no approval step at all
AI_RENAME_APPROVAL_TIMEOUT_SECONDS = 30  # dialog auto-dismisses to "No" after this

# ============================================================
# TELEGRAM APPROVAL (alternative to the Windows dialog above)
# Only relevant when AI_RENAME_AUTO_APPROVE = False. Instead of a Windows
# message box, each AI rename suggestion is sent to your Telegram chat as
# a message with Approve/Skip buttons.
#
# This never blocks the watcher: the suggestion is sent and the watcher
# immediately moves on to the next file. The rename itself only happens
# later, whenever you tap Approve in Telegram — tapping Skip leaves that
# file with its original name for good (no fallback to Name_ext_date for
# Telegram-routed files, unlike the dialog path).
#
# Setup:
#   1. pip install python-telegram-bot>=21.0
#   2. Message @BotFather on Telegram -> /newbot -> copy the token it gives you
#   3. Message @userinfobot (or similar) to get your own numeric chat id
#   4. Set TELEGRAM_ENABLED=True, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID below
#      (or via environment variables / .env — see .env.example)
# ============================================================
TELEGRAM_ENABLED = os.environ.get("TELEGRAM_ENABLED", "False") == "True"
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

# "telegram" -> route approvals through Telegram (falls back to "dialog" for
# a given file if Telegram isn't reachable/configured at that moment).
# "dialog"   -> always use the Windows message box.
AI_RENAME_APPROVAL_MODE = "telegram" if TELEGRAM_ENABLED else "dialog"
# After you tap Approve/Skip, the result message ("Renamed..."/"Skipped...")
# auto-deletes from the Telegram chat after this many seconds — keeps the
# chat tidy instead of accumulating a permanent scrollback of every past
# rename. This ONLY removes the Telegram message; logs/activity.log is
# untouched and remains the full permanent record either way. Set to 0 to
# disable auto-delete and keep every message in the chat.
TELEGRAM_AUTO_DELETE_SECONDS = 5

# ============================================================
# DUPLICATE DETECTION (Downloads, Pictures, Videos)
# Matches by file content hash (SHA-256), not just filename.
# Moves duplicates into a 'Duplicates' folder inside the same parent.
# ============================================================
DUPLICATE_CHECK_ENABLED = True
DUPLICATES_FOLDER_NAME = "Duplicates"

# ============================================================
# SCREENSHOT ORGANIZATION (Pictures + Videos, screenshot files only)
# Detected by filename containing 'screenshot' (case-insensitive)
# or being in a known screenshot folder (e.g. Windows' default).
# Sorted into: Screenshots/<image|video>/YYYY-MM/
# Renamed to: Screenshot_image_DDMMYYYY_HHMMSS.ext
# ============================================================
SCREENSHOT_ORGANIZE_ENABLED = True
SCREENSHOT_KEYWORD = "screenshot"
SCREENSHOT_DEST_FOLDER_NAME = "Screenshots"

# ============================================================
# FORMAT CONVERSION
# HEIC -> JPG (Pictures), MOV -> MP4 (Videos)
# Originals are KEPT by default (converted copy saved alongside).
# Requires: pillow-heif (for HEIC) and ffmpeg installed on system (for MOV).
# ============================================================
CONVERT_HEIC_TO_JPG = True
CONVERT_MOV_TO_MP4 = True
DELETE_ORIGINAL_AFTER_CONVERT = False  # keep True->False safe default: keeps originals

# ============================================================
# SYSTEM MAINTENANCE (scheduled, not event-driven)
# ============================================================
MAINTENANCE_ENABLED = True
MAINTENANCE_INTERVAL_HOURS = 6

DISK_SPACE_WARNING_PERCENT = 90  # warn if usage crosses this %
LARGE_FILE_THRESHOLD_MB = (
    500  # flag files bigger than this, in the 3 watched folders only
)
TEMP_CLEAN_ENABLED = (
    True  # only clears OS temp dirs, never your Downloads/Pictures/Videos
)

# ============================================================
# LOGGING
# ============================================================
LOG_FOLDER = Path(__file__).resolve().parent.parent / "logs"
LOG_FILE = LOG_FOLDER / "activity.log"
REPORT_FILE = LOG_FOLDER / "maintenance_report.txt"

LOG_FOLDER.mkdir(exist_ok=True)
