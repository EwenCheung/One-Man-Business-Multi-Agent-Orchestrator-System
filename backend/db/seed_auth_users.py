from __future__ import annotations

import os
from dataclasses import dataclass

from supabase import Client, create_client

from backend.db.engine import SessionLocal
from backend.db.models import Customer, Investor, Partner, Profile, Supplier


@dataclass(frozen=True)
class AuthCandidate:
    role: str
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
                    AuthCandidate(role="owner", email=profile.notifications_email.strip().lower())
                )

        for customer in session.query(Customer).all():
            if customer.email:
                candidates.append(
                    AuthCandidate(role="customer", email=customer.email.strip().lower())
                )
            if customer.phone:
                candidates.append(
                    AuthCandidate(role="customer", phone=normalize_phone(customer.phone))
                )
            if customer.telegram_username:
                username_email = (
                    f"{customer.telegram_username.strip().lstrip('@').lower()}@telegram.local"
                )
                candidates.append(AuthCandidate(role="customer", email=username_email))

        for supplier in session.query(Supplier).all():
            if supplier.email:
                candidates.append(
                    AuthCandidate(role="supplier", email=supplier.email.strip().lower())
                )
            if supplier.phone:
                candidates.append(
                    AuthCandidate(role="supplier", phone=normalize_phone(supplier.phone))
                )

        for partner in session.query(Partner).all():
            if partner.email:
                candidates.append(
                    AuthCandidate(role="partner", email=partner.email.strip().lower())
                )
            if partner.phone:
                candidates.append(
                    AuthCandidate(role="partner", phone=normalize_phone(partner.phone))
                )

        for investor in session.query(Investor).all():
            if investor.email:
                candidates.append(
                    AuthCandidate(role="investor", email=investor.email.strip().lower())
                )
            if investor.phone:
                candidates.append(
                    AuthCandidate(role="investor", phone=normalize_phone(investor.phone))
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


def ensure_auth_user(supabase: Client, candidate: AuthCandidate) -> None:
    try:
        if candidate.email:
            print(f"Creating user for email: {candidate.email} (Role: {candidate.role})")
            supabase.auth.admin.create_user(
                {
                    "email": candidate.email,
                    "password": "Abcd@1234",
                    "email_confirm": True,
                    "user_metadata": {"role": candidate.role},
                }
            )
            return

        if candidate.phone:
            print(f"Creating user for phone: {candidate.phone} (Role: {candidate.role})")
            supabase.auth.admin.create_user(
                {
                    "phone": candidate.phone,
                    "password": "Abcd@1234",
                    "phone_confirm": True,
                    "user_metadata": {"role": candidate.role},
                }
            )
    except Exception as e:
        print(f"  -> Skipped (might already exist): {e}")


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
