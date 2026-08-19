"""
AI-suggested filenames using Google's Gemini API.

Reads a file's content (via utils/content_extractor.py) and asks Gemini for
a short, descriptive filename. This is purely advisory: the caller
(core/pipeline.py) always shows the suggestion to the user for approval via
utils/approval_ui.py before anything is renamed, and falls back to the
existing Name_ext_date convention if the API is unavailable, errors out,
the file type isn't supported, or the user declines.

Requires:
    pip install google-genai
    A GEMINI_API_KEY environment variable set on the machine.

Nothing here ever raises out to the caller — any failure just returns None.
"""

import base64
import json
import re
import threading
import time
from pathlib import Path
from typing import Optional

from config import settings
from utils import content_extractor
from utils.logger import log_action

try:
    from google import genai
    from google.genai import types

    _CLIENT = genai.Client()
except Exception:
    # Covers: package not installed, and GEMINI_API_KEY not set/invalid.
    genai = None
    types = None
    _CLIENT = None


_SYSTEM_PROMPT = (
    "You suggest short, descriptive filenames based on a file's content. "
    'Respond with ONLY a JSON object of the form {"suggested_name":"..."} '
    "and nothing else — no markdown, no preamble. The name should be "
    f"{settings.AI_RENAME_MAX_WORDS} words or fewer, lowercase, words "
    "separated by underscores, no file extension, no punctuation besides "
    "underscores and hyphens. Base it on the actual subject matter/content, "
    "not generic terms like 'document' or 'file'."
)

_AI_PAUSED_UNTIL = 0.0

# Simple rate limiter: guarantees at least AI_RENAME_MIN_INTERVAL_SECONDS
# between successive Gemini calls, across all threads (initial sweep is
# sequential, but live watcher events each fire on their own timer thread).
# Without this, a big initial sweep fires many requests in the first few
# seconds, blows straight through the free tier's per-minute quota, and
# then every file scanned during the resulting cooldown silently skips AI
# naming entirely and falls back to the plain Name_ext_date convention —
# not because those files were unsupported, just bad timing.
_RATE_LOCK = threading.Lock()
_LAST_CALL_TIME = 0.0


def _throttle() -> None:
    global _LAST_CALL_TIME
    with _RATE_LOCK:
        now = time.time()
        wait = settings.AI_RENAME_MIN_INTERVAL_SECONDS - (now - _LAST_CALL_TIME)
        if wait > 0:
            time.sleep(wait)
        _LAST_CALL_TIME = time.time()


def _is_ai_paused() -> bool:
    return time.time() < _AI_PAUSED_UNTIL


def _record_quota_pause(error_text: str) -> None:
    global _AI_PAUSED_UNTIL

    match = re.search(
        r"retry(?:\s+in|Delay)?(?:\s*[:=]\s*|\s+)?['\"]?(\d+(?:\.\d+)?)s?",
        error_text,
        re.IGNORECASE,
    )
    if not match:
        return

    retry_seconds = float(match.group(1)) + 1.0
    _AI_PAUSED_UNTIL = max(_AI_PAUSED_UNTIL, time.time() + retry_seconds)
    log_action(
        f"AI rename paused for {retry_seconds:.0f}s due to Gemini quota; "
        "will resume automatically after the cooldown."
    )


def _client_ready() -> bool:
    return _CLIENT is not None


def _sanitize(name: str) -> Optional[str]:
    """Cleans a raw model suggestion into a filesystem-safe stem."""
    if not name or not isinstance(name, str):
        return None
    cleaned = re.sub(r"[^\w\-]", "_", name.strip())
    cleaned = re.sub(r"_{2,}", "_", cleaned).strip("_")
    if not cleaned:
        return None
    return cleaned[: settings.AI_RENAME_MAX_CHARS]


def _parse_suggestion(raw_text: str) -> Optional[str]:
    try:
        data = json.loads(raw_text.strip())
        return _sanitize(data.get("suggested_name", ""))
    except (json.JSONDecodeError, AttributeError):
        # Model didn't follow JSON-only instruction — try to salvage a
        # bare word/line instead of giving up entirely.
        first_line = raw_text.strip().splitlines()[0] if raw_text.strip() else ""
        return _sanitize(first_line)


def suggest_name(file_path: Path) -> Optional[str]:
    """Returns a sanitized, extension-less filename suggestion, or None if
    AI naming isn't available/applicable for this file. Never raises."""
    if not settings.AI_RENAME_ENABLED:
        return None
    if not _client_ready():
        return None
    if not content_extractor.is_ai_nameable(file_path):
        return None
    if _is_ai_paused():
        remaining = max(0, int(_AI_PAUSED_UNTIL - time.time()))
        log_action(
            f"AI rename cooldown active for {remaining}s; waiting before next Gemini request."
        )
        return None

    try:
        text_preview = content_extractor.get_text_preview(file_path)

        if text_preview:
            contents = (
                f"Filename: {file_path.name}\n\n"
                f"Content:\n{text_preview}\n\n"
                f"Return JSON only."
            )
        else:
            image_payload = content_extractor.get_image_payload(file_path)
            if not image_payload:
                return None

            media_type, raw_bytes = image_payload
            contents = [
                types.Part.from_bytes(data=raw_bytes, mime_type=media_type),
                (
                    f"Original filename: {file_path.name}. "
                    "Suggest a concise filename describing what is shown in "
                    "this image. Return JSON only."
                ),
            ]

        _throttle()
        response = _CLIENT.models.generate_content(
            model=settings.AI_RENAME_MODEL,
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=_SYSTEM_PROMPT,
                temperature=0.1,
                max_output_tokens=100,
                response_mime_type="application/json",
            ),
        )

        raw_text = response.text or ""
        suggestion = _parse_suggestion(raw_text)
        if suggestion:
            log_action(f"AI suggested name for {file_path.name}: {suggestion}")
        return suggestion

    except Exception as e:
        error_text = str(e)
        _record_quota_pause(error_text)
        log_action(f"AI naming skipped for {file_path.name}: {error_text}")
        return None
