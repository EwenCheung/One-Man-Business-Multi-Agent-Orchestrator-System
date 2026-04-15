"""
Telegram Webhook Integration

Receives Telegram updates via webhook and dispatches them to the orchestrator pipeline.

Endpoint:
  POST /webhook  → Receives Telegram updates and triggers pipeline asynchronously
"""

import asyncio
import logging
import time
from typing import Any

from fastapi import APIRouter, HTTPException, Request, status

from backend.config import settings
from backend.db.engine import SessionLocal
from backend.db.models import Profile
from backend.services.conversation_memory import (
    add_message_to_thread,
    get_or_create_conversation_thread,
)
from backend.services.identity_resolution import resolve_or_create_sender
from backend.integrations.telegram_sender import send_telegram_chat_action, send_telegram_message
from backend.models import IncomingMessage

logger = logging.getLogger(__name__)
telegram_router = APIRouter(tags=["telegram"])
_PROCESSED_UPDATE_IDS: dict[str, float] = {}
_CHAT_LOCKS: dict[str, asyncio.Lock] = {}
_CHAT_LOCK_LAST_USED: dict[str, float] = {}
_DEDUP_TTL_SECONDS = 120.0
_CHAT_LOCK_TTL_SECONDS = 900.0
START_REPLY_TEXT = (
    "Hi! I’m the shop assistant. You can ask about products, pricing, stock, orders, or support, "
    "and I’ll help you here on Telegram."
)


def _build_start_reply_text(profile: Profile | None) -> str:
    business_name = (profile.business_name or "").strip() if profile else ""
    if business_name:
        return (
            f"Hi! I’m the {business_name}'s assistant. You can ask question about products, "
            "pricing, stock, orders, or support, and I’ll help you here on Telegram."
        )
    return START_REPLY_TEXT


def _prune_processed_updates() -> None:
    cutoff = time.time() - _DEDUP_TTL_SECONDS
    stale_keys = [key for key, seen_at in _PROCESSED_UPDATE_IDS.items() if seen_at < cutoff]
    for key in stale_keys:
        _ = _PROCESSED_UPDATE_IDS.pop(key, None)


def _remember_update(update_id: str) -> bool:
    if not update_id:
        return True
    _prune_processed_updates()
    if update_id in _PROCESSED_UPDATE_IDS:
        return False
    _PROCESSED_UPDATE_IDS[update_id] = time.time()
    return True


def _prune_chat_locks() -> None:
    cutoff = time.time() - _CHAT_LOCK_TTL_SECONDS
    stale_chat_ids = [
        chat_id
        for chat_id, last_seen in _CHAT_LOCK_LAST_USED.items()
        if last_seen < cutoff
        and (existing_lock := _CHAT_LOCKS.get(chat_id)) is not None
        and not existing_lock.locked()
    ]
    for chat_id in stale_chat_ids:
        _ = _CHAT_LOCKS.pop(chat_id, None)
        _ = _CHAT_LOCK_LAST_USED.pop(chat_id, None)


def _chat_lock(chat_id: str | None) -> asyncio.Lock | None:
    if not chat_id:
        return None
    _prune_chat_locks()
    lock = _CHAT_LOCKS.get(chat_id)
    if lock is None:
        lock = asyncio.Lock()
        _CHAT_LOCKS[chat_id] = lock
    _CHAT_LOCK_LAST_USED[chat_id] = time.time()
    return lock


def extract_telegram_message(payload: dict[str, Any]) -> IncomingMessage | None:
    """
    Extract sender info and message text from Telegram webhook payload.

    Telegram payload structure:
    {
        "update_id": 123456789,
        "message": {
            "message_id": 123,
            "from": {
                "id": 987654321,
                "is_bot": false,
                "first_name": "John",
                "last_name": "Doe",
                "username": "johndoe"
            },
            "chat": {
                "id": 987654321,
                ...
            },
            "date": 1234567890,
            "text": "Hello, bot!",
            "contact": {
                "phone_number": "+1234567890",
                "first_name": "John"
            }
        }
    }

    Primary identity: tg:<telegram_user_id>
    Aliases passed via telegram_username and contact phone for existing role resolution.
    """
    message = payload.get("message")
    if not message:
        return None

    raw_message = message.get("text", "")
    if not raw_message:
        return None

    from_user = message.get("from", {})
    contact = message.get("contact", {})
    chat = message.get("chat", {})

    telegram_user_id = str(from_user.get("id", ""))
    if not telegram_user_id:
        return None

    sender_id = f"tg:{telegram_user_id}"

    first_name = from_user.get("first_name", "")
    last_name = from_user.get("last_name", "")
    sender_name = " ".join(filter(None, [first_name, last_name])) or None

    telegram_username = from_user.get("username")
    telegram_chat_id = str(chat.get("id", "")) if chat else None
    telegram_contact_phone = contact.get("phone_number")

    return IncomingMessage(
        raw_message=raw_message,
        sender_id=sender_id,
        owner_id=None,
        sender_name=sender_name,
        thread_id=None,
        sender_role=None,
        telegram_update_id=str(payload.get("update_id", "")) or None,
        telegram_user_id=telegram_user_id,
        telegram_username=telegram_username,
        telegram_chat_id=telegram_chat_id,
        telegram_contact_phone=telegram_contact_phone,
    )


def _is_start_command(message_text: str) -> bool:
    return message_text.strip().split(maxsplit=1)[0].lower() == "/start"


def _handle_start_message(incoming: IncomingMessage) -> None:
    session = SessionLocal()
    try:
        aliases = []
        if incoming.telegram_username:
            aliases.append(incoming.telegram_username)
        if incoming.telegram_contact_phone:
            aliases.append(incoming.telegram_contact_phone)

        resolved_identity = resolve_or_create_sender(
            session,
            incoming.sender_id,
            incoming.sender_name,
            aliases=aliases or None,
            telegram_username=incoming.telegram_username,
            telegram_chat_id=incoming.telegram_chat_id,
            owner_id=incoming.owner_id,
        )
        thread = get_or_create_conversation_thread(
            session,
            owner_id=resolved_identity["owner_id"],
            sender_role=resolved_identity["sender_role"],
            external_sender_id=incoming.sender_id,
            sender_name=incoming.sender_name,
            sender_channel="telegram",
        )
        profile = session.query(Profile).filter_by(id=resolved_identity["owner_id"]).first()
        start_reply_text = _build_start_reply_text(profile)
        _ = add_message_to_thread(
            session,
            owner_id=resolved_identity["owner_id"],
            conversation_thread_id=thread.id,
            sender_id=incoming.sender_id,
            sender_name=incoming.sender_name,
            sender_role=resolved_identity["sender_role"],
            direction="inbound",
            content=incoming.raw_message,
        )
        _ = add_message_to_thread(
            session,
            owner_id=resolved_identity["owner_id"],
            conversation_thread_id=thread.id,
            sender_id=incoming.sender_id,
            sender_name=incoming.sender_name,
            sender_role=resolved_identity["sender_role"],
            direction="outbound",
            content=start_reply_text,
        )
        session.commit()
        if incoming.telegram_chat_id:
            _ = send_telegram_message(
                resolved_identity["owner_id"], incoming.telegram_chat_id, start_reply_text
            )
    except Exception as e:
        session.rollback()
        logger.error("Error handling Telegram /start: %s", e, exc_info=True)
    finally:
        session.close()


@telegram_router.post("/webhook", status_code=status.HTTP_200_OK)
async def telegram_webhook(request: Request):
    """
    Receive Telegram updates and dispatch to orchestrator pipeline.

    Returns 200 OK immediately to prevent Telegram retries while
    processing happens in the background.
    """
    provided_secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token")
    require_secret = settings.APP_ENV.lower() != "development"

    if require_secret and not provided_secret:
        raise HTTPException(status_code=403, detail="Missing Telegram webhook secret")

    if not provided_secret:
        resolved_owner_id = settings.OWNER_ID
    else:
        session = SessionLocal()
        try:
            profile = (
                session.query(Profile).filter_by(telegram_webhook_secret=provided_secret).first()
            )
        finally:
            session.close()

        if not profile:
            raise HTTPException(status_code=403, detail="Unknown Telegram webhook secret")

        resolved_owner_id = str(profile.id)

    try:
        payload = await request.json()
    except Exception:
        return {"ok": True}

    incoming = extract_telegram_message(payload)
    if not incoming:
        return {"ok": True}

    incoming.owner_id = resolved_owner_id

    if incoming.telegram_update_id and not _remember_update(incoming.telegram_update_id):
        return {"ok": True}

    if _is_start_command(incoming.raw_message):
        _ = asyncio.create_task(asyncio.to_thread(_handle_start_message, incoming))
        return {"ok": True}

    if incoming.telegram_chat_id:
        _ = asyncio.create_task(
            asyncio.to_thread(
                send_telegram_chat_action,
                incoming.owner_id or settings.OWNER_ID,
                incoming.telegram_chat_id,
                "typing",
            )
        )

    _ = asyncio.create_task(_process_telegram_message(incoming))

    return {"ok": True}


async def _process_telegram_message(incoming: IncomingMessage) -> None:
    """
    Process Telegram message through orchestrator pipeline.

    Runs in background to avoid blocking webhook response.
    """
    try:
        from backend.api.router import process_incoming_message

        lock = _chat_lock(incoming.telegram_chat_id)
        if lock is None:
            _ = await process_incoming_message(incoming, trusted_owner_id=incoming.owner_id)
            return

        async with lock:
            _ = await process_incoming_message(incoming, trusted_owner_id=incoming.owner_id)
    except Exception as e:
        logger.error("Error processing Telegram message: %s", e, exc_info=True)
