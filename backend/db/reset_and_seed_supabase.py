import json
import os
from pathlib import Path
import uuid
from typing import cast

from sqlalchemy import text
from sqlalchemy.engine import Engine

from backend.db.engine import SessionLocal, engine
from backend.db.generate_seed_data import OWNERS_FILE, main as generate_seed_data
from backend.db.init_db import init as init_db
from backend.db.load_seed_data import load_all
from backend.db.models import Profile
from backend.db.seed_auth_users import get_supabase_admin_client, main as seed_auth_users

OWNER_EMAILS = ["owner1@gmail.com", "owner2@gmail.com"]


def ensure_owner_auth_users() -> list[dict[str, str]]:
    supabase = get_supabase_admin_client()
    if supabase is None:
        raise RuntimeError("Supabase admin client is not configured")

    users = supabase.auth.admin.list_users()
    owners: list[dict[str, str]] = []

    for index, email in enumerate(OWNER_EMAILS, start=1):
        existing = next((user for user in users if (user.email or "").lower() == email), None)
        if existing is None:
            created = supabase.auth.admin.create_user(
                {
                    "email": email,
                    "password": "Abcd@1234",
                    "email_confirm": True,
                    "user_metadata": {"role": "owner"},
                }
            )
            owner_id = str(created.user.id)
        else:
            owner_id = str(existing.id)

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
    OWNERS_FILE.write_text(json.dumps(owners, indent=2))
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
        conn.execute(
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
                memory_context="",
                soul_context="",
                rule_context="",
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
    generate_seed_data()
    load_all(with_embeddings=False)

    os.environ.setdefault("SUPABASE_URL", os.environ.get("SUPABASE_URL", ""))
    os.environ.setdefault(
        "SUPABASE_SERVICE_ROLE_KEY", os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
    )
    seed_auth_users()
    print("Supabase reset and reseed complete.")


if __name__ == "__main__":
    main()
