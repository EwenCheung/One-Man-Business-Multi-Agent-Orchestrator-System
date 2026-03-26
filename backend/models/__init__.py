"""API request/response models."""

from typing import Any

from pydantic import BaseModel, Field


class IncomingMessage(BaseModel):
    raw_message: str = Field(..., min_length=1)
    sender_id: str = Field(..., min_length=1)
    sender_name: str | None = None


class PipelineResult(BaseModel):
    reply_text: str
    risk_level: str
    requires_approval: bool
    status: str
    trace: dict[str, Any] = Field(default_factory=dict)

