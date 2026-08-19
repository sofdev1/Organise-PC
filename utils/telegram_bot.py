"""
Telegram-based approval for AI-suggested filenames.

When settings.AI_RENAME_APPROVAL_MODE == "telegram", each AI rename
suggestion is sent to your Telegram chat as a message with Approve/Skip
buttons, instead of popping a Windows dialog.

Important: this is fire-and-forget. core/pipeline.py sends the suggestion
and immediately moves on to the next file — it never blocks waiting for you
to tap a button. The file is left completely untouched until you respond:

The bot stays SILENT until you send it /start. Even if the process is
running and fully configured (token + chat id set), request_approval()
reports "not ready" and callers fall back to the Windows dialog path for
every file until the configured chat has sent /start at least once. This
avoids the bot suddenly messaging you the moment the watcher launches,
before you've actually opened the chat.

  * Tap "Approve"  -> the file is renamed right then, from inside the
                       Telegram callback handler (whenever that happens to be).
  * Tap "Skip"     -> the file is left with its original name, permanently
                       (there is no fallback to the standard Name_ext_date
                       convention for Telegram-routed suggestions — you
                       either approve the AI name or the file stays as-is).
  * Never tap      -> the file simply stays as-is until you do.

Once you tap a button, the result message ("Renamed..." / "Skipped...")
auto-deletes from the chat per settings.TELEGRAM_AUTO_DELETE_SECONDS
(0 = instantly, right after you tap) — this only removes the Telegram
message itself, logs/activity.log keeps the permanent record regardless.

Also registers a small set of tappable slash-commands (/start, /help,
/status, /pending, /skipall, /clearall) — Telegram shows these in the "/"
menu. /clearall wipes every message the bot has sent in this chat at once
(it cannot delete messages you typed — Telegram's Bot API only allows a
bot to delete its own messages).

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
from typing import Any, Dict, Tuple

from config import settings
from utils.logger import log_action

try:
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
    from telegram.ext import Application, CallbackQueryHandler, CommandHandler
    from telegram.constants import ParseMode
except Exception:
    # Covers: python-telegram-bot not installed.
    # Use Any so type-checkers don't treat the later attribute access as
    # happening on a None literal when the optional dependency is absent.
    InlineKeyboardButton: Any = None
    InlineKeyboardMarkup: Any = None
    BotCommand: Any = None
    Application: Any = None
    CallbackQueryHandler: Any = None
    CommandHandler: Any = None
    ParseMode: Any = None


_loop: Any = None  # asyncio event loop the bot runs on, in its own thread
_app: Any = None  # telegram.ext.Application instance
_thread = None
_lock = threading.Lock()

# request_id -> (file_path_str, suggested_stem, original_name, suggested_display_name)
_PENDING: Dict[str, Tuple[str, str, str, str]] = {}
_next_id = 0

# Every message the bot has sent this session, as (chat_id, message_id) —
# lets /clearall wipe the whole chat on demand. Entries are removed once a
# message is actually deleted (via auto-delete or /clearall itself) so we
# never try to double-delete something that's already gone.
_SENT_MESSAGE_IDS: list = []

_COMMANDS = [
    ("start", "What this bot does"),
    ("help", "List commands"),
    ("status", "Current settings & pending count"),
    ("pending", "List files awaiting your approval"),
    ("skipall", "Skip every pending suggestion right now"),
    ("clearall", "Erase every message this bot has sent in this chat"),
]


def _package_ready() -> bool:
    return Application is not None


def _configured() -> bool:
    return bool(settings.TELEGRAM_ENABLED and settings.TELEGRAM_BOT_TOKEN and settings.TELEGRAM_CHAT_ID)


# Set True only once the configured chat sends /start. Until then,
# request_approval() reports "not ready" so callers fall back to the dialog
# path — the bot stays completely silent and sends nothing unprompted, even
# if it's fully configured and running in the background.
_user_started = False


def _ready() -> bool:
    return _package_ready() and _configured() and _user_started


def _is_authorized(update) -> bool:
    """Only respond to the configured chat — anyone else who finds the bot
    (e.g. by its username) gets ignored, since this bot can rename files
    on your PC."""
    chat = update.effective_chat
    if chat is None:
        return False
    try:
        return str(chat.id) == str(settings.TELEGRAM_CHAT_ID)
    except Exception:
        return False


def _track_message(chat_id, message_id) -> None:
    """Records a message the bot just sent, so /clearall can find it later."""
    _SENT_MESSAGE_IDS.append((chat_id, message_id))


async def _delete_message(chat_id, message_id) -> bool:
    """Deletes one message right now. Returns True on success, False if it
    was already gone/too old/otherwise undeletable (never raises)."""
    try:
        await _app.bot.delete_message(chat_id=chat_id, message_id=message_id)
        return True
    except Exception:
        return False  # already deleted, edited away, >48h old, etc. — harmless


async def _schedule_delete(chat_id, message_id, delay_seconds) -> None:
    """Deletes a Telegram message after a delay. Only removes it from the
    chat — logs/activity.log is untouched and remains the permanent record."""
    await asyncio.sleep(delay_seconds)
    await _delete_message(chat_id, message_id)
    if (chat_id, message_id) in _SENT_MESSAGE_IDS:
        _SENT_MESSAGE_IDS.remove((chat_id, message_id))


def _fire_delete(chat_id, message_id) -> None:
    """Deletes a message per TELEGRAM_AUTO_DELETE_SECONDS: instantly if 0,
    after a delay if >0, or not at all if explicitly set to None."""
    delay = getattr(settings, "TELEGRAM_AUTO_DELETE_SECONDS", 0)
    if delay is None:
        return  # auto-delete explicitly disabled — leave the message in the chat

    if delay <= 0:
        async def _instant():
            await _delete_message(chat_id, message_id)
            if (chat_id, message_id) in _SENT_MESSAGE_IDS:
                _SENT_MESSAGE_IDS.remove((chat_id, message_id))
        asyncio.create_task(_instant())
    else:
        asyncio.create_task(_schedule_delete(chat_id, message_id, delay))


async def _on_button(update, context):
    # Local import: renamer -> ... avoids any import-order issues at module
    # load time, and keeps this module importable even if renamer someday
    # imports something telegram-adjacent.
    from utils import renamer

    query = update.callback_query
    await query.answer()

    if not _is_authorized(update):
        return

    action, _, request_id = (query.data or "").partition(":")
    entry = _PENDING.pop(request_id, None)
    if entry is None:
        await query.edit_message_text("This suggestion already expired or was already handled.")
        _fire_delete(query.message.chat_id, query.message.message_id)
        return

    file_path_str, suggested_stem, original_name, suggested_display_name = entry
    file_path = Path(file_path_str)

    if action == "approve":
        if not file_path.exists():
            log_action(f"Telegram approval for {original_name} arrived too late — file no longer exists.")
            await query.edit_message_text(f"⚠️ {original_name} no longer exists — nothing to rename.")
        else:
            new_path = renamer.rename_file(file_path, override_stem=suggested_stem)
            log_action(f"Telegram-approved rename: {original_name} -> {new_path.name}")
            await query.edit_message_text(f"✅ Renamed:\n{original_name}\n→ {new_path.name}")
    else:
        log_action(f"Telegram rename skipped by user for {original_name} — left as-is.")
        await query.edit_message_text(f"⏭️ Skipped — kept as:\n{original_name}")

    _fire_delete(query.message.chat_id, query.message.message_id)


async def _cmd_start(update, context):
    if not _is_authorized(update):
        return

    global _user_started
    already_started = _user_started
    _user_started = True

    if already_started:
        text = (
            "🤖 Already running — I'll keep sending AI rename suggestions here "
            "with Approve/Skip buttons.\n\nSend /help to see what else I can do."
        )
    else:
        text = (
            "🤖 *Organise_PC*\n\n"
            "Started! From now on I'll send AI rename suggestions here with "
            "Approve/Skip buttons. Nothing gets renamed until you tap Approve — "
            "tap Skip (or ignore it) and the file keeps its original name.\n\n"
            "Send /help to see what else I can do."
        )
        log_action("Telegram: user sent /start — suggestions will now be sent to this chat.")

    msg = await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)
    _track_message(msg.chat_id, msg.message_id)


async def _cmd_help(update, context):
    if not _is_authorized(update):
        return
    lines = "\n".join(f"/{name} — {desc}" for name, desc in _COMMANDS)
    msg = await update.message.reply_text(lines)
    _track_message(msg.chat_id, msg.message_id)


async def _cmd_status(update, context):
    if not _is_authorized(update):
        return
    text = (
        "*Organise_PC status*\n\n"
        f"DRY\\_RUN: `{settings.DRY_RUN}`\n"
        f"AI\\_RENAME\\_ENABLED: `{settings.AI_RENAME_ENABLED}`\n"
        f"AI\\_RENAME\\_AUTO\\_APPROVE: `{settings.AI_RENAME_AUTO_APPROVE}`\n"
        f"Approval mode: `{settings.AI_RENAME_APPROVAL_MODE}`\n"
        f"Started (\\/start sent): `{_user_started}`\n"
        f"Pending suggestions: `{len(_PENDING)}`\n"
        f"Tracked messages: `{len(_SENT_MESSAGE_IDS)}`"
    )
    msg = await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)
    _track_message(msg.chat_id, msg.message_id)


async def _cmd_pending(update, context):
    if not _is_authorized(update):
        return
    if not _PENDING:
        msg = await update.message.reply_text("Nothing pending right now — all caught up.")
        _track_message(msg.chat_id, msg.message_id)
        return
    lines = ["Waiting on your approval:\n"]
    for _, (_, _, original_name, suggested_display_name) in _PENDING.items():
        lines.append(f"• {original_name} → {suggested_display_name}")
    msg = await update.message.reply_text("\n".join(lines))
    _track_message(msg.chat_id, msg.message_id)


async def _cmd_skipall(update, context):
    if not _is_authorized(update):
        return
    count = len(_PENDING)
    for _, (_, _, original_name, _) in list(_PENDING.items()):
        log_action(f"Telegram rename skipped (via /skipall) for {original_name} — left as-is.")
    _PENDING.clear()
    msg = await update.message.reply_text(
        f"Skipped {count} pending suggestion(s). All those files keep their original names."
    )
    _track_message(msg.chat_id, msg.message_id)


async def _cmd_clearall(update, context):
    """Deletes every message the bot has sent in this chat this session —
    suggestions, confirmations, and other command replies alike. Cannot
    delete messages YOU typed (Telegram's Bot API doesn't allow bots to
    delete other users' messages, even in a private chat)."""
    if not _is_authorized(update):
        return

    chat_id = update.effective_chat.id
    targets = [(cid, mid) for (cid, mid) in _SENT_MESSAGE_IDS if str(cid) == str(chat_id)]

    deleted = 0
    for cid, mid in targets:
        if await _delete_message(cid, mid):
            deleted += 1
        if (cid, mid) in _SENT_MESSAGE_IDS:
            _SENT_MESSAGE_IDS.remove((cid, mid))

    skipped_pending = len(_PENDING)
    _PENDING.clear()  # their suggestion messages are gone now too

    log_action(f"Telegram: /clearall deleted {deleted} message(s), cleared {skipped_pending} pending suggestion(s).")

    confirmation = await update.message.reply_text(
        f"🧹 Cleared {deleted} message(s)."
        + (f" ({skipped_pending} pending suggestion(s) also cleared — those files keep their original names.)"
           if skipped_pending else "")
    )
    _track_message(confirmation.chat_id, confirmation.message_id)
    _fire_delete(confirmation.chat_id, confirmation.message_id)  # don't leave the confirmation lingering either


def _build_app():
    app = Application.builder().token(settings.TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CallbackQueryHandler(_on_button))
    app.add_handler(CommandHandler("start", _cmd_start))
    app.add_handler(CommandHandler("help", _cmd_help))
    app.add_handler(CommandHandler("status", _cmd_status))
    app.add_handler(CommandHandler("pending", _cmd_pending))
    app.add_handler(CommandHandler("skipall", _cmd_skipall))
    app.add_handler(CommandHandler(getattr(settings, "TELEGRAM_CLEAR_ALL_COMMAND", "clearall"), _cmd_clearall))
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
        try:
            await _app.bot.set_my_commands(
                [BotCommand(name, desc) for name, desc in _COMMANDS]
            )
        except Exception as e:
            log_action(f"Could not register Telegram command menu: {e}")
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
            sent = await _app.bot.send_message(
                chat_id=settings.TELEGRAM_CHAT_ID, text=text, reply_markup=keyboard
            )
            _track_message(sent.chat_id, sent.message_id)
        except Exception as e:
            log_action(f"Failed to send Telegram suggestion for {file_path.name}: {e}")

    asyncio.run_coroutine_threadsafe(_send(), _loop)
    log_action(f"Sent Telegram rename suggestion for {file_path.name}: {suggested_display_name}")
    return True