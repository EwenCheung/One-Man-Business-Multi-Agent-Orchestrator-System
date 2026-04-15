from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

from supabase import Client, create_client
from sqlalchemy import select, text

from backend.db.engine import SessionLocal
from backend.db.models import Customer, ExternalIdentity, Investor, Partner, Profile, Supplier


@dataclass(frozen=True)
class AuthCandidate:
    role: str
    owner_id: str | None = None
    email: str | None = None
    phone: str | None = None


def get_supabase_admin_client() -> Client | None:
    supabase_url = os.environ.get("SUPABASE_URL")
    supabase_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")

    if not supabase_url or not supabase_key:
        print("Error: Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY environment variables.")
        print("Please ensure they are set in your .env file.")
        return None

    return create_client(supabase_url, supabase_key)


def normalize_phone(phone: str | None) -> str | None:
    if not phone:
        return None
    normalized = phone.strip().replace(" ", "").replace("-", "")
    if not normalized:
        return None
    return normalized if normalized.startswith("+") else f"+{normalized}"


def load_auth_candidates() -> list[AuthCandidate]:
    session = SessionLocal()
    try:
        candidates: list[AuthCandidate] = []

        for profile in session.query(Profile).all():
            if profile.notifications_email:
                candidates.append(
                    AuthCandidate(
                        role="owner",
                        owner_id=str(profile.id),
                        email=profile.notifications_email.strip().lower(),
                    )
                )

        for customer in session.query(Customer).all():
            if customer.email:
                candidates.append(
                    AuthCandidate(
                        role="customer",
                        owner_id=str(customer.owner_id),
                        email=customer.email.strip().lower(),
                    )
                )
            if customer.phone:
                candidates.append(
                    AuthCandidate(
                        role="customer",
                        owner_id=str(customer.owner_id),
                        phone=normalize_phone(customer.phone),
                    )
                )
            if customer.telegram_username:
                username_email = (
                    f"{customer.telegram_username.strip().lstrip('@').lower()}@telegram.local"
                )
                candidates.append(
                    AuthCandidate(
                        role="customer",
                        owner_id=str(customer.owner_id),
                        email=username_email,
                    )
                )

        for supplier in session.query(Supplier).all():
            if supplier.email:
                candidates.append(
                    AuthCandidate(
                        role="supplier",
                        owner_id=str(supplier.owner_id),
                        email=supplier.email.strip().lower(),
                    )
                )
            if supplier.phone:
                candidates.append(
                    AuthCandidate(
                        role="supplier",
                        owner_id=str(supplier.owner_id),
                        phone=normalize_phone(supplier.phone),
                    )
                )

        for partner in session.query(Partner).all():
            if partner.email:
                candidates.append(
                    AuthCandidate(
                        role="partner",
                        owner_id=str(partner.owner_id),
                        email=partner.email.strip().lower(),
                    )
                )
            if partner.phone:
                candidates.append(
                    AuthCandidate(
                        role="partner",
                        owner_id=str(partner.owner_id),
                        phone=normalize_phone(partner.phone),
                    )
                )

        for investor in session.query(Investor).all():
            if investor.email:
                candidates.append(
                    AuthCandidate(
                        role="investor",
                        owner_id=str(investor.owner_id),
                        email=investor.email.strip().lower(),
                    )
                )
            if investor.phone:
                candidates.append(
                    AuthCandidate(
                        role="investor",
                        owner_id=str(investor.owner_id),
                        phone=normalize_phone(investor.phone),
                    )
                )

        seen: set[tuple[str, str, str]] = set()
        unique_candidates: list[AuthCandidate] = []
        for candidate in candidates:
            key = (candidate.role, candidate.email or "", candidate.phone or "")
            if key in seen:
                continue
            seen.add(key)
            unique_candidates.append(candidate)

        return unique_candidates
    finally:
        session.close()


def _extract_user_id(response: Any) -> str | None:
    user = getattr(response, "user", None)
    if user and getattr(user, "id", None):
        return str(user.id)

    data = getattr(response, "data", None)
    if isinstance(data, dict):
        maybe_user = data.get("user")
        if isinstance(maybe_user, dict) and maybe_user.get("id"):
            return str(maybe_user["id"])
    return None


def _find_auth_user_id(candidate: AuthCandidate) -> str | None:
    session = SessionLocal()
    try:
        if candidate.email:
            result = session.execute(
                text("SELECT id FROM auth.users WHERE lower(email) = :email LIMIT 1"),
                {"email": candidate.email.lower()},
            ).first()
            if result:
                return str(result[0])

        if candidate.phone:
            result = session.execute(
                text("SELECT id FROM auth.users WHERE phone = :phone LIMIT 1"),
                {"phone": candidate.phone},
            ).first()
            if result:
                return str(result[0])
    finally:
        session.close()

    return None


def _upsert_external_identity_link(candidate: AuthCandidate, supabase_user_id: str) -> None:
    if candidate.role == "owner" or not candidate.owner_id:
        return

    session = SessionLocal()
    try:
        external_type = "email" if candidate.email else "phone"
        external_id = candidate.email if candidate.email else candidate.phone
        if external_id is None:
            return

        identity = session.execute(
            select(ExternalIdentity).where(
                ExternalIdentity.owner_id == candidate.owner_id,
                ExternalIdentity.entity_role == candidate.role,
                ExternalIdentity.external_type == external_type,
                ExternalIdentity.external_id == external_id,
            )
        ).scalar_one_or_none()

        if identity is None:
            return

        metadata = dict(identity.identity_metadata or {})
        metadata["supabase_user_id"] = supabase_user_id
        identity.identity_metadata = metadata
        session.commit()
    finally:
        session.close()


def ensure_auth_user(supabase: Client, candidate: AuthCandidate) -> None:
    response = None
    try:
        if candidate.email:
            print(f"Creating user for email: {candidate.email} (Role: {candidate.role})")
            response = supabase.auth.admin.create_user(
                {
                    "email": candidate.email,
                    "password": "Abcd@1234",
                    "email_confirm": True,
                    "user_metadata": {
                        "role": candidate.role,
                        **({"owner_id": candidate.owner_id} if candidate.owner_id else {}),
                    },
                }
            )
        elif candidate.phone:
            print(f"Creating user for phone: {candidate.phone} (Role: {candidate.role})")
            response = supabase.auth.admin.create_user(
                {
                    "phone": candidate.phone,
                    "password": "Abcd@1234",
                    "phone_confirm": True,
                    "user_metadata": {
                        "role": candidate.role,
                        **({"owner_id": candidate.owner_id} if candidate.owner_id else {}),
                    },
                }
            )
    except Exception as e:
        print(f"  -> Skipped (might already exist): {e}")

    supabase_user_id = _extract_user_id(response) if response is not None else None
    if not supabase_user_id:
        supabase_user_id = _find_auth_user_id(candidate)
    if supabase_user_id:
        _upsert_external_identity_link(candidate, supabase_user_id)


def main() -> None:
    supabase = get_supabase_admin_client()
    if supabase is None:
        return

    candidates = load_auth_candidates()
    print(f"Found {len(candidates)} stakeholder auth candidate(s) to process.")

    for candidate in candidates:
        ensure_auth_user(supabase, candidate)

    print("\nAuth seeding complete! Stakeholders can log in with password 'Abcd@1234'.")


if __name__ == "__main__":
    main()
