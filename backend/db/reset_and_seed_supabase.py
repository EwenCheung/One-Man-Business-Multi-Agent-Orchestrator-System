import json
import os
import uuid
from typing import cast

from sqlalchemy import text
from sqlalchemy.engine import Engine

from backend.data import generate_seed_data
from backend.db.engine import SessionLocal, engine
from backend.data.generate_seed_data import OWNERS_FILE
from backend.db.init_db import init as init_db
from backend.db.load_seed_data import load_all
from backend.db.models import Profile
from backend.db.seed_auth_users import get_supabase_admin_client, main as seed_auth_users

OWNER_EMAILS = ["owner1@gmail.com", "owner2@gmail.com"]


def _find_auth_user_id_by_email(email: str) -> str | None:
    db_engine = cast(Engine, engine)
    with db_engine.connect() as conn:
        result = conn.execute(
            text("SELECT id FROM auth.users WHERE lower(email) = :email LIMIT 1"),
            {"email": email.lower()},
        ).first()
    return str(result[0]) if result else None


def _default_memory_context(business_name: str) -> str:
    return (
        "# Long-Term Memory\n\n"
        f"Context for {business_name}. This document stores evolving business history, "
        "high-impact decisions, and stable stakeholder preferences over time."
    )


def _default_soul_context(full_name: str, business_name: str) -> str:
    return (
        "# System Persona\n\n"
        f"You are a proactive and strategic agent acting on behalf of {full_name} for {business_name}. "
        "You prioritize owner benefit, communicate clearly, and avoid unsupported commitments."
    )


def _default_rule_context(business_name: str) -> str:
    return (
        "# Business Rules\n\n"
        f"Default operational rules for {business_name}. Follow pricing, approval, and privacy constraints "
        "strictly, and escalate exceptions for owner review."
    )


def ensure_owner_auth_users() -> list[dict[str, str]]:
    supabase = get_supabase_admin_client()
    if supabase is None:
        raise RuntimeError("Supabase admin client is not configured")

    owners: list[dict[str, str]] = []

    for index, email in enumerate(OWNER_EMAILS, start=1):
        owner_id = _find_auth_user_id_by_email(email)
        if owner_id is None:
            created = supabase.auth.admin.create_user(
                {
                    "email": email,
                    "password": "Abcd@1234",
                    "email_confirm": True,
                    "user_metadata": {"role": "owner"},
                }
            )
            owner_id = str(created.user.id)

        owners.append(
            {
                "label": f"owner{index}",
                "email": email,
                "id": owner_id,
                "full_name": f"Owner {index}",
                "business_name": f"Owner {index} Business",
                "business_description": f"Seeded business for owner {index}",
            }
        )

    OWNERS_FILE.parent.mkdir(parents=True, exist_ok=True)
    _ = OWNERS_FILE.write_text(json.dumps(owners, indent=2))
    return owners


def wipe_business_data() -> None:
    tables = [
        "pending_approvals",
        "reply_review_records",
        "held_replies",
        "memory_update_proposals",
        "messages",
        "conversation_sender_memories",
        "conversation_memories",
        "conversation_threads",
        "external_identities",
        "memory_entries",
        "entity_memories",
        "owner_memory_rules",
        "daily_digest",
        "partner_product_relations",
        "partner_agreements",
        "supplier_products",
        "orders",
        "investors",
        "partners",
        "suppliers",
        "customers",
        "products",
        "profiles",
    ]
    db_engine = cast(Engine, engine)
    with db_engine.connect() as conn:
        _ = conn.execute(
            text(f"TRUNCATE TABLE {', '.join(f'public.{table}' for table in tables)} CASCADE")
        )
        conn.commit()


def seed_owner_profiles(owners: list[dict[str, str]]) -> None:
    session = SessionLocal()
    try:
        for owner in owners:
            profile = Profile(
                id=uuid.UUID(owner["id"]),
                full_name=owner["full_name"],
                business_name=owner["business_name"],
                business_description=owner["business_description"],
                notifications_email=owner["email"],
                telegram_bot_token=None,
                telegram_webhook_secret=None,
                default_reply_tone="professional",
                memory_context=_default_memory_context(owner["business_name"]),
                soul_context=_default_soul_context(owner["full_name"], owner["business_name"]),
                rule_context=_default_rule_context(owner["business_name"]),
            )
            session.add(profile)
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def main() -> None:
    init_db()
    owners = ensure_owner_auth_users()
    wipe_business_data()
    seed_owner_profiles(owners)
    generate_seed_data.main()
    load_all(with_embeddings=False)

    _ = os.environ.setdefault("SUPABASE_URL", os.environ.get("SUPABASE_URL", ""))
    _ = os.environ.setdefault(
        "SUPABASE_SERVICE_ROLE_KEY", os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
    )
    seed_auth_users()
    print("Supabase reset and reseed complete.")


if __name__ == "__main__":
    main()
