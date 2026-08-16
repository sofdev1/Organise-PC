"""
Bulk format conversion:
    HEIC -> JPG   (Pictures folder)
    MOV  -> MP4   (Videos folder)

Originals are kept by default (DELETE_ORIGINAL_AFTER_CONVERT = False in settings).

Requirements:
    pip install pillow-heif pillow    (for HEIC -> JPG)
    ffmpeg installed and on PATH      (for MOV -> MP4)
"""

import shutil
import subprocess
from pathlib import Path
from config import settings
from utils.logger import log_action

try:
    from PIL import Image
    import pillow_heif

    pillow_heif.register_heif_opener()
    HEIC_SUPPORT = True
except ImportError:
    HEIC_SUPPORT = False


def _ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None


def convert_heic_to_jpg(file_path: Path) -> Path:
    if not settings.CONVERT_HEIC_TO_JPG or file_path.suffix.lower() != ".heic":
        return file_path

    if not HEIC_SUPPORT:
        log_action(
            "Skipped HEIC conversion: pillow-heif not installed (pip install pillow-heif)"
        )
        return file_path

    target_path = file_path.with_suffix(".jpg")
    if target_path.exists():
        return file_path

    if settings.DRY_RUN:
        log_action(f"Would convert: {file_path.name} -> {target_path.name}")
        return file_path

    try:
        img = Image.open(file_path)
        img.convert("RGB").save(target_path, "JPEG", quality=95)
        log_action(f"Converted: {file_path.name} -> {target_path.name}")

        if settings.DELETE_ORIGINAL_AFTER_CONVERT:
            file_path.unlink()
            log_action(f"Deleted original after conversion: {file_path.name}")
    except Exception as e:
        log_action(f"Failed to convert {file_path.name}: {e}")

    return target_path


def convert_mov_to_mp4(file_path: Path) -> Path:
    if not settings.CONVERT_MOV_TO_MP4 or file_path.suffix.lower() != ".mov":
        return file_path

    if not _ffmpeg_available():
        log_action("Skipped MOV conversion: ffmpeg not found on PATH (install ffmpeg)")
        return file_path

    target_path = file_path.with_suffix(".mp4")
    if target_path.exists():
        return file_path

    if settings.DRY_RUN:
        log_action(f"Would convert: {file_path.name} -> {target_path.name}")
        return file_path

    try:
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-i",
                str(file_path),
                "-c:v",
                "libx264",
                "-c:a",
                "aac",
                str(target_path),
            ],
            check=True,
            capture_output=True,
        )
        log_action(f"Converted: {file_path.name} -> {target_path.name}")

        if settings.DELETE_ORIGINAL_AFTER_CONVERT:
            file_path.unlink()
            log_action(f"Deleted original after conversion: {file_path.name}")
    except subprocess.CalledProcessError as e:
        log_action(f"Failed to convert {file_path.name}: {e}")

    return target_path


def scan_and_convert(folder: Path, extension: str, convert_func):
    if not folder.exists():
        return
    for file in sorted(folder.rglob(f"*{extension}")):
        if file.is_file():
            convert_func(file)
