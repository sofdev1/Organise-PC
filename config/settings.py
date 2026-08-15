"""
Central configuration for Organise_PC.
Edit the paths below to match your system before running.
"""

import os
from pathlib import Path

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
LARGE_FILE_THRESHOLD_MB = 500     # flag files bigger than this, in the 3 watched folders only
TEMP_CLEAN_ENABLED = True         # only clears OS temp dirs, never your Downloads/Pictures/Videos

# ============================================================
# LOGGING
# ============================================================
LOG_FOLDER = Path(__file__).resolve().parent.parent / "logs"
LOG_FILE = LOG_FOLDER / "activity.log"
REPORT_FILE = LOG_FOLDER / "maintenance_report.txt"

LOG_FOLDER.mkdir(exist_ok=True)
