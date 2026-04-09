"""API request/response models."""

from typing import Any

from pydantic import BaseModel, Field


class IncomingMessage(BaseModel):
    raw_message: str = Field(..., min_length=1)
    sender_id: str = Field(..., min_length=1)
    owner_id: str | None = None
    sender_name: str | None = None
    thread_id: str | None = None
    sender_role: str | None = None
    telegram_update_id: str | None = None
    telegram_user_id: str | None = None
    telegram_username: str | None = None
    telegram_chat_id: str | None = None
    telegram_contact_phone: str | None = None


class PipelineResult(BaseModel):
    reply_text: str
    risk_level: str
    requires_approval: bool
    status: str
    trace: dict[str, Any] = Field(default_factory=dict)
