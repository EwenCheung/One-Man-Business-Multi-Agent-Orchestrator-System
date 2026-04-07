from __future__ import annotations

import re
import uuid
from typing import Any

from sqlalchemy.orm import Session
from sqlalchemy import text

from backend.config import settings
from backend.db.models import Customer, ExternalIdentity, Investor, Partner, Supplier, Profile


def _canonical_phone(value: str) -> str:
    return re.sub(r"[^\d+]", "", value or "")


def _canonical_email(value: str) -> str:
    return (value or "").strip().lower()


def _detect_external_type(external_id: str) -> str:
    value = (external_id or "").strip()
    if "@" in value:
        return "email"
    if any(char.isdigit() for char in value):
        return "phone"
    return "username"


def _normalize_external_id(external_id: str, external_type: str) -> str:
    if external_type == "phone":
        return _canonical_phone(external_id)
    if external_type == "email":
        return _canonical_email(external_id)
    return (external_id or "").strip().lower()


def _looks_like_uuid(value: str) -> bool:
    try:
        uuid.UUID(str(value))
        return True
    except (ValueError, TypeError):
        return False


def _role_model_pairs() -> list[tuple[str, type]]:
    return [
        ("customer", Customer),
        ("supplier", Supplier),
        ("partner", Partner),
        ("investor", Investor),
    ]


def _find_existing_entity_by_uuid(session: Session, candidate_id: str) -> dict[str, Any] | None:
    try:
        candidate_uuid = uuid.UUID(str(candidate_id))
    except (ValueError, TypeError):
        return None

    for role, model in _role_model_pairs():
        row = session.query(model).filter_by(id=candidate_uuid).first()
        if row:
            return {
                "entity_role": role,
                "entity_id": str(row.id),
                "owner_id": str(row.owner_id),
                "record": row,
            }
    return None


def _find_existing_entity_by_profile_fields(
    session: Session,
    normalized_external_id: str,
    external_type: str,
) -> dict[str, Any] | None:
    owner_uuid = uuid.UUID(settings.OWNER_ID)
    col_name: str | None = None
    if external_type == "phone":
        col_name = "phone"
    elif external_type == "email":
        col_name = "email"

    if col_name is None:
        return None

    for role, model in _role_model_pairs():
        if not hasattr(model, col_name):
            continue
        col = getattr(model, col_name)
        row = (
            session.query(model)
            .filter(model.owner_id == owner_uuid, col == normalized_external_id)
            .first()
        )
        if row:
            return {
                "entity_role": role,
                "entity_id": str(row.id),
                "owner_id": str(row.owner_id),
                "record": row,
            }
    return None


def _ensure_external_identity(
    session: Session,
    *,
    owner_id: str,
    external_id: str,
    external_type: str,
    entity_role: str,
    entity_id: str,
) -> None:
    try:
        owner_uuid = uuid.UUID(str(owner_id))
    except (ValueError, TypeError):
        owner_uuid = owner_id

    try:
        entity_uuid = uuid.UUID(str(entity_id))
    except (ValueError, TypeError):
        entity_uuid = entity_id

    normalized_external_id = _normalize_external_id(external_id, external_type)
    existing = (
        session.query(ExternalIdentity)
        .filter_by(
            owner_id=owner_uuid,
            external_type=external_type,
            external_id=normalized_external_id,
        )
        .first()
    )
    if existing:
        return

    session.add(
        ExternalIdentity(
            owner_id=owner_uuid,
            external_id=normalized_external_id,
            external_type=external_type,
            entity_role=entity_role,
            entity_id=entity_uuid,
            identity_metadata={"source": "auto-resolved"},
        )
    )


def _is_owner_identity(
    session: Session,
    external_sender_id: str,
    external_type: str,
    normalized_external_id: str,
) -> bool:
    """Check if the incoming sender identity matches the owner UUID or email."""
    owner_uuid = uuid.UUID(settings.OWNER_ID)

    # Case 1: Sender ID matches owner UUID
    if _looks_like_uuid(external_sender_id):
        try:
            sender_uuid = uuid.UUID(str(external_sender_id))
            if sender_uuid == owner_uuid:
                return True
        except (ValueError, TypeError):
            pass

    # Case 2: Email matches owner's profile email or auth.users email
    if external_type == "email":
        owner_profile = session.query(Profile).filter_by(id=owner_uuid).first()
        if owner_profile and owner_profile.notifications_email:
            owner_email = _canonical_email(owner_profile.notifications_email)
            if normalized_external_id == owner_email:
                return True

        # Fallback: check auth.users if profile email not set
        result = session.execute(
            text("SELECT email FROM auth.users WHERE id = :owner_id"),
            {"owner_id": str(owner_uuid)},
        ).first()
        if result and result[0]:
            auth_email = _canonical_email(result[0])
            if normalized_external_id == auth_email:
                return True

    return False


def resolve_or_create_sender(
    session: Session,
    external_sender_id: str,
    sender_name: str | None = None,
) -> dict[str, str]:
    owner_uuid = uuid.UUID(settings.OWNER_ID)
    external_type = _detect_external_type(external_sender_id)
    normalized_external_id = _normalize_external_id(external_sender_id, external_type)

    # Guard: if sender matches owner, return owner identity without creating customer
    if _is_owner_identity(session, external_sender_id, external_type, normalized_external_id):
        return {
            "external_sender_id": external_sender_id,
            "sender_id": str(owner_uuid),
            "entity_id": str(owner_uuid),
            "sender_role": "owner",
            "owner_id": str(owner_uuid),
        }

    if _looks_like_uuid(external_sender_id):
        by_uuid = _find_existing_entity_by_uuid(session, external_sender_id)
        if by_uuid:
            _ensure_external_identity(
                session,
                owner_id=by_uuid["owner_id"],
                external_id=external_sender_id,
                external_type=external_type,
                entity_role=by_uuid["entity_role"],
                entity_id=by_uuid["entity_id"],
            )
            session.commit()
            return {
                "external_sender_id": external_sender_id,
                "sender_id": by_uuid["entity_id"],
                "entity_id": by_uuid["entity_id"],
                "sender_role": by_uuid["entity_role"],
                "owner_id": by_uuid["owner_id"],
            }

    mapped = (
        session.query(ExternalIdentity)
        .filter_by(
            owner_id=owner_uuid,
            external_type=external_type,
            external_id=normalized_external_id,
        )
        .first()
    )
    if mapped:
        return {
            "external_sender_id": external_sender_id,
            "sender_id": str(mapped.entity_id),
            "entity_id": str(mapped.entity_id),
            "sender_role": mapped.entity_role,
            "owner_id": str(mapped.owner_id),
        }

    by_profile = _find_existing_entity_by_profile_fields(
        session, normalized_external_id, external_type
    )
    if by_profile:
        _ensure_external_identity(
            session,
            owner_id=by_profile["owner_id"],
            external_id=external_sender_id,
            external_type=external_type,
            entity_role=by_profile["entity_role"],
            entity_id=by_profile["entity_id"],
        )
        session.commit()
        return {
            "external_sender_id": external_sender_id,
            "sender_id": by_profile["entity_id"],
            "entity_id": by_profile["entity_id"],
            "sender_role": by_profile["entity_role"],
            "owner_id": by_profile["owner_id"],
        }

    new_customer = Customer(
        owner_id=owner_uuid,
        name=(sender_name or "New Customer").strip() or "New Customer",
        email=normalized_external_id if external_type == "email" else None,
        phone=normalized_external_id if external_type == "phone" else None,
        status="active",
        notes=f"Auto-created from inbound sender '{external_sender_id}'.",
    )
    session.add(new_customer)
    session.flush()

    session.add(
        ExternalIdentity(
            owner_id=owner_uuid,
            external_id=normalized_external_id,
            external_type=external_type,
            entity_role="customer",
            entity_id=new_customer.id,
            identity_metadata={"source": "auto-created-from-intake"},
        )
    )
    session.commit()

    return {
        "external_sender_id": external_sender_id,
        "sender_id": str(new_customer.id),
        "entity_id": str(new_customer.id),
        "sender_role": "customer",
        "owner_id": settings.OWNER_ID,
    }
