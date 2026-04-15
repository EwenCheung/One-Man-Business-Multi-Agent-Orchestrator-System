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

OWNER_SEED_PROFILES = {
    "owner1": {
        "full_name": "Ethan Tan",
        "business_name": "Northstar Workspace Supply",
        "business_description": "An owner-led SMB that sells workspace accessories and desk setup bundles to schools, small offices, and purchasing teams.",
    },
    "owner2": {
        "full_name": "Maya Lim",
        "business_name": "Luna Brew & Pack",
        "business_description": "An owner-led SMB supplying café takeaway packaging, brew tools, and beverage service essentials to independent food and beverage operators.",
    },
}


def _find_auth_user_id_by_email(email: str) -> str | None:
    db_engine = cast(Engine, engine)
    with db_engine.connect() as conn:
        result = conn.execute(
            text("SELECT id FROM auth.users WHERE lower(email) = :email LIMIT 1"),
            {"email": email.lower()},
        ).first()
    return str(cast(object, result[0])) if result else None


def _default_memory_context(owner_label: str, business_name: str) -> str:
    if owner_label == "owner1":
        return (
            "# Long-Term Memory\n\n"
            f"{business_name} wins on reliable fulfilment, practical bundles, and concise B2B communication. "
            "Key remembered facts should include recurring buying patterns from schools and office teams, discount boundaries, "
            "delivery timing expectations, and supplier risks affecting keyboard, mouse, and desk accessory stock."
        )

    return (
        "# Long-Term Memory\n\n"
        f"{business_name} grows through repeat wholesale orders from cafés and food operators. "
        "Key remembered facts should include reorder cadence, packaging preferences, margin-sensitive products, partner campaign learnings, "
        "and investor focus on cash flow, stock turnover, and branch expansion readiness."
    )


def _default_soul_context(owner_label: str, full_name: str, business_name: str) -> str:
    if owner_label == "owner1":
        return (
            "# SOUL\n\n"
            "## Identity\n\n"
            f"You speak for {full_name} of {business_name}. You are a sharp, reliable operator for a fast-moving product business serving schools, teams, and office buyers. "
            "You optimize for repeat orders, clear execution, practical upsell opportunities, and protecting margin.\n\n"
            "## Voice\n\n"
            "- Be direct, commercially aware, and operationally clear.\n"
            "- Lead with what is available, what can ship, and what decision is needed.\n"
            "- Offer simple next steps instead of long explanations.\n"
            "- Sound like an owner who cares about reliability and repeat business."
        )

    return (
        "# SOUL\n\n"
        "## Identity\n\n"
        f"You speak for {full_name} of {business_name}. You are a calm but commercially sharp operator for a hospitality supply business serving cafés and food operators. "
        "You optimize for recurring wholesale revenue, smooth supplier coordination, practical promotions, and strong customer retention.\n\n"
        "## Voice\n\n"
        "- Be warm, decisive, and business-minded.\n"
        "- Keep replies easy to act on, especially around stock, delivery, and repeat ordering.\n"
        "- Protect margin, but stay service-oriented.\n"
        "- Sound like an owner balancing growth, operations, and long-term relationships."
    )


def _default_rule_context(owner_label: str, business_name: str) -> str:
    if owner_label == "owner1":
        return (
            "# Business Rules\n\n"
            f"For {business_name}: do not promise stock, delivery dates, or bulk pricing unless supported by current data. "
            "Discounts above 12 percent, custom bundle pricing, or urgent exception requests require owner approval. Keep customer replies concise, accurate, and commercially safe."
        )

    return (
        "# Business Rules\n\n"
        f"For {business_name}: do not commit to wholesale pricing, payment term changes, or rush fulfilment without verified stock and margin coverage. "
        "Any exception on packaging specs, branding requests, or discounting above 10 percent requires owner approval. Protect service quality and repeat-order profitability."
    )


def ensure_owner_auth_users() -> list[dict[str, str]]:
    supabase = get_supabase_admin_client()
    if supabase is None:
        raise RuntimeError("Supabase admin client is not configured")

    owners: list[dict[str, str]] = []

    for index, email in enumerate(OWNER_EMAILS, start=1):
        owner_label = f"owner{index}"
        profile_defaults = OWNER_SEED_PROFILES[owner_label]
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
                "label": owner_label,
                "email": email,
                "id": owner_id,
                "full_name": profile_defaults["full_name"],
                "business_name": profile_defaults["business_name"],
                "business_description": profile_defaults["business_description"],
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
                memory_context=_default_memory_context(owner["label"], owner["business_name"]),
                soul_context=_default_soul_context(
                    owner["label"], owner["full_name"], owner["business_name"]
                ),
                rule_context=_default_rule_context(owner["label"], owner["business_name"]),
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
