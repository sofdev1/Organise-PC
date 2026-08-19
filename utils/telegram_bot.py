"""
Telegram-based approval for AI-suggested filenames.

When settings.AI_RENAME_APPROVAL_MODE == "telegram", each AI rename
suggestion is sent to your Telegram chat as a message with Approve/Skip
buttons, instead of popping a Windows dialog.

Important: this is fire-and-forget. core/pipeline.py sends the suggestion
and immediately moves on to the next file — it never blocks waiting for you
to tap a button. The file is left completely untouched until you respond:

  * Tap "Approve"  -> the file is renamed right then, from inside the
                       Telegram callback handler (whenever that happens to be).
  * Tap "Skip"     -> the file is left with its original name, permanently
                       (there is no fallback to the standard Name_ext_date
                       convention for Telegram-routed suggestions — you
                       either approve the AI name or the file stays as-is).
  * Never tap      -> the file simply stays as-is until you do.

Requires:
    pip install python-telegram-bot>=21.0
    TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID set (see .env.example / README)

Nothing here ever raises out to the caller — request_approval() returns
False on any setup problem, and the pipeline falls back to the Windows
dialog for that file when that happens.
"""

import asyncio
import threading
from pathlib import Path
from typing import Dict, Tuple

from config import settings
from utils.logger import log_action

try:
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    from telegram.ext import Application, CallbackQueryHandler
except Exception:
    # Covers: python-telegram-bot not installed.
    InlineKeyboardButton = None
    InlineKeyboardMarkup = None
    Application = None
    CallbackQueryHandler = None


_loop = None  # asyncio event loop the bot runs on, in its own thread
_app = None  # telegram.ext.Application instance
_thread = None
_lock = threading.Lock()

# request_id -> (file_path_str, suggested_stem, original_name, suggested_display_name)
_PENDING: Dict[str, Tuple[str, str, str, str]] = {}
_next_id = 0


def _package_ready() -> bool:
    return Application is not None


def _configured() -> bool:
    return bool(settings.TELEGRAM_ENABLED and settings.TELEGRAM_BOT_TOKEN and settings.TELEGRAM_CHAT_ID)


def _ready() -> bool:
    return _package_ready() and _configured()


async def _on_button(update, context):
    # Local import: renamer -> ... avoids any import-order issues at module
    # load time, and keeps this module importable even if renamer someday
    # imports something telegram-adjacent.
    from utils import renamer

    query = update.callback_query
    await query.answer()

    action, _, request_id = (query.data or "").partition(":")
    entry = _PENDING.pop(request_id, None)
    if entry is None:
        await query.edit_message_text("This suggestion already expired or was already handled.")
        return

    file_path_str, suggested_stem, original_name, suggested_display_name = entry
    file_path = Path(file_path_str)

    if action == "approve":
        if not file_path.exists():
            log_action(f"Telegram approval for {original_name} arrived too late — file no longer exists.")
            await query.edit_message_text(f"⚠️ {original_name} no longer exists — nothing to rename.")
            return
        new_path = renamer.rename_file(file_path, override_stem=suggested_stem)
        log_action(f"Telegram-approved rename: {original_name} -> {new_path.name}")
        await query.edit_message_text(f"✅ Renamed:\n{original_name}\n→ {new_path.name}")
    else:
        log_action(f"Telegram rename skipped by user for {original_name} — left as-is.")
        await query.edit_message_text(f"⏭️ Skipped — kept as:\n{original_name}")


def _build_app():
    app = Application.builder().token(settings.TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CallbackQueryHandler(_on_button))
    return app


def _run_loop():
    global _app, _loop
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    _loop = loop
    _app = _build_app()

    async def _main():
        await _app.initialize()
        await _app.start()
        await _app.updater.start_polling(drop_pending_updates=True)

    try:
        loop.run_until_complete(_main())
        loop.run_forever()
    except Exception as e:
        log_action(f"Telegram bot loop stopped unexpectedly: {e}")


def start() -> None:
    """Starts the Telegram bot's own polling loop in a background thread.
    Safe to call once at watcher startup. No-op (logged) if Telegram isn't
    enabled/configured or python-telegram-bot isn't installed — the app
    keeps working normally with dialog-based approval in that case."""
    global _thread

    if not settings.TELEGRAM_ENABLED:
        return

    if not _package_ready():
        log_action(
            "TELEGRAM_ENABLED is True but python-telegram-bot isn't installed "
            "(pip install python-telegram-bot>=21.0) — falling back to dialog approval."
        )
        return

    if not _configured():
        log_action(
            "TELEGRAM_ENABLED is True but TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID "
            "aren't set — falling back to dialog approval."
        )
        return

    with _lock:
        if _thread is not None:
            return
        _thread = threading.Thread(target=_run_loop, daemon=True, name="telegram-bot")
        _thread.start()

    log_action("Telegram approval bot started — AI rename suggestions will be sent there.")


def request_approval(file_path: Path, suggested_stem: str, suggested_display_name: str) -> bool:
    """Sends an Approve/Skip suggestion to Telegram and returns immediately —
    it does NOT wait for a reply. Returns True once the send has been
    queued, False if Telegram isn't available right now (not configured,
    package missing, or the bot thread hasn't started yet), in which case
    the caller should fall back to another approval path for this file."""
    if not _ready() or _app is None or _loop is None:
        return False

    global _next_id
    with _lock:
        _next_id += 1
        request_id = str(_next_id)
    _PENDING[request_id] = (str(file_path), suggested_stem, file_path.name, suggested_display_name)

    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("✅ Approve", callback_data=f"approve:{request_id}"),
                InlineKeyboardButton("⏭️ Skip", callback_data=f"skip:{request_id}"),
            ]
        ]
    )
    text = f"🤖 AI rename suggestion\n\n{file_path.name}\n→ {suggested_display_name}"

    async def _send():
        try:
            await _app.bot.send_message(
                chat_id=settings.TELEGRAM_CHAT_ID, text=text, reply_markup=keyboard
            )
        except Exception as e:
            log_action(f"Failed to send Telegram suggestion for {file_path.name}: {e}")

    asyncio.run_coroutine_threadsafe(_send(), _loop)
    log_action(f"Sent Telegram rename suggestion for {file_path.name}: {suggested_display_name}")
    return True
