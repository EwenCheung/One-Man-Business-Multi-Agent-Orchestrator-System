import uuid

from backend.config import settings
from backend.db.models import Customer, ExternalIdentity
from backend.services.identity_resolution import resolve_or_create_sender


def test_resolve_existing_customer_by_phone_creates_mapping(db_session):
    owner_id = uuid.UUID(settings.OWNER_ID)
    phone = "+65 9000 1234"

    customer = Customer(
        owner_id=owner_id,
        name="Resolver Existing",
        phone="+6590001234",
        status="active",
    )
    db_session.add(customer)
    db_session.commit()

    try:
        resolved = resolve_or_create_sender(db_session, phone, "Resolver Existing")

        assert resolved["sender_role"] == "customer"
        assert resolved["entity_id"] == str(customer.id)

        mapping = (
            db_session.query(ExternalIdentity)
            .filter_by(owner_id=owner_id, entity_id=customer.id, external_type="phone")
            .first()
        )
        assert mapping is not None
        assert mapping.external_id == "+6590001234"
    finally:
        db_session.query(ExternalIdentity).filter_by(entity_id=customer.id).delete()
        db_session.query(Customer).filter_by(id=customer.id).delete()
        db_session.commit()


def test_resolve_unknown_sender_creates_customer_and_mapping(db_session):
    owner_id = uuid.UUID(settings.OWNER_ID)
    phone = "+65 9111 2233"

    resolved = resolve_or_create_sender(db_session, phone, "Auto Created")
    created_customer_id = uuid.UUID(resolved["entity_id"])

    try:
        assert resolved["sender_role"] == "customer"

        customer = db_session.query(Customer).filter_by(id=created_customer_id).first()
        assert customer is not None
        assert customer.owner_id == owner_id
        assert customer.phone == "+6591112233"

        mapping = (
            db_session.query(ExternalIdentity)
            .filter_by(owner_id=owner_id, entity_id=created_customer_id, external_type="phone")
            .first()
        )
        assert mapping is not None
        assert mapping.external_id == "+6591112233"
    finally:
        db_session.query(ExternalIdentity).filter_by(entity_id=created_customer_id).delete()
        db_session.query(Customer).filter_by(id=created_customer_id).delete()
        db_session.commit()
