import logging
import time
from uuid import UUID
from typing import Any

import httpx
from backend.db.models import Profile

logger = logging.getLogger(__name__)
STREAM_EDIT_DELAY_SECONDS = 1.0
MAX_STREAM_STEPS = 4


def extract_telegram_chat_id(sender_external_id: str) -> str | None:
    if not sender_external_id or not sender_external_id.startswith("tg:"):
        return None
    return sender_external_id.replace("tg:", "")


def _get_bot_token(owner_id: str) -> str | None:
    from backend.db.engine import SessionLocal

    try:
        owner_uuid = UUID(owner_id)
    except (ValueError, TypeError):
        logger.error(f"Invalid owner_id: {owner_id}")
        return None

    session = SessionLocal()
    try:
        profile = session.query(Profile).filter_by(id=owner_uuid).first()
        if not profile:
            logger.error(f"Profile not found for owner: {owner_id}")
            return None
        if not profile.telegram_bot_token:
            logger.warning(f"No telegram_bot_token configured for owner: {owner_id}")
            return None
        return profile.telegram_bot_token
    finally:
        session.close()


def _telegram_api_request(
    owner_id: str, method: str, payload: dict[str, Any]
) -> dict[str, Any] | None:
    bot_token = _get_bot_token(owner_id)
    if not bot_token:
        return None

    url = f"https://api.telegram.org/bot{bot_token}/{method}"

    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.post(url, json=payload)
        if response.status_code != 200:
            logger.error(f"Telegram API error ({method}): {response.status_code} - {response.text}")
            return None
        payload = response.json()
        if payload.get("ok") is not True:
            logger.error(f"Telegram API rejected {method}: {payload}")
            return None
        return payload
    except Exception as e:
        logger.error(f"Failed Telegram API request {method}: {e}", exc_info=True)
        return None


def send_telegram_chat_action(owner_id: str, chat_id: str, action: str = "typing") -> bool:
    payload = {
        "chat_id": chat_id,
        "action": action,
    }
    return _telegram_api_request(owner_id, "sendChatAction", payload) is not None


def _build_stream_steps(text: str) -> list[str]:
    normalized = (text or "").strip()
    if not normalized:
        return []

    paragraphs = [part.strip() for part in normalized.split("\n\n") if part.strip()]
    if len(paragraphs) <= MAX_STREAM_STEPS:
        steps: list[str] = []
        current = ""
        for part in paragraphs:
            current = f"{current}\n\n{part}".strip()
            steps.append(current)
        return steps or [normalized]

    chunk_size = max(1, len(normalized) // MAX_STREAM_STEPS)
    steps = []
    cursor = 0
    while cursor < len(normalized):
        next_cursor = min(len(normalized), cursor + chunk_size)
        if next_cursor < len(normalized):
            boundary = normalized.rfind(" ", cursor, next_cursor)
            if boundary > cursor:
                next_cursor = boundary
        snippet = normalized[:next_cursor].strip()
        if snippet:
            steps.append(snippet)
        cursor = next_cursor
        if len(steps) >= MAX_STREAM_STEPS:
            break

    if not steps or steps[-1] != normalized:
        steps.append(normalized)
    return steps


def send_telegram_message(
    owner_id: str,
    chat_id: str,
    text: str,
) -> bool:
    payload = {
        "chat_id": chat_id,
        "text": text,
    }
    result = _telegram_api_request(owner_id, "sendMessage", payload)
    if result is not None:
        logger.info(f"Telegram message sent to chat_id={chat_id}")
        return True
    return False


def send_telegram_stream_reply(owner_id: str, chat_id: str, text: str) -> bool:
    steps = _build_stream_steps(text)
    if not steps:
        return False

    first_result = _telegram_api_request(
        owner_id,
        "sendMessage",
        {
            "chat_id": chat_id,
            "text": steps[0],
        },
    )
    if first_result is None:
        return False

    message_id = (first_result.get("result") or {}).get("message_id")
    if not message_id or len(steps) == 1:
        return True

    for step in steps[1:]:
        time.sleep(STREAM_EDIT_DELAY_SECONDS)
        edit_result = _telegram_api_request(
            owner_id,
            "editMessageText",
            {
                "chat_id": chat_id,
                "message_id": message_id,
                "text": step,
            },
        )
        if edit_result is None:
            return False

    return True


def send_telegram_reply(
    owner_id: str,
    sender_external_id: str | None,
    reply_text: str,
    chat_id: str | None = None,
) -> bool:
    if not sender_external_id and not chat_id:
        logger.warning("No sender_external_id provided for Telegram reply")
        return False

    resolved_chat_id = chat_id or extract_telegram_chat_id(sender_external_id or "")
    if not resolved_chat_id:
        logger.info(f"sender_external_id '{sender_external_id}' is not a Telegram ID (tg:*)")
        return False

    return send_telegram_stream_reply(owner_id, resolved_chat_id, reply_text)
