"""
Database Models — Unified Supabase Schema

SQLAlchemy ORM models aligned with the Supabase PostgreSQL schema.
All tables use UUID primary keys and owner_id for multi-tenant RLS.
"""

import uuid
from datetime import datetime, date
from typing import Optional
from decimal import Decimal
from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    String,
    Text,
    Numeric,
    Integer,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    func,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base class for all ORM models."""

    pass


class ExternalIdentity(Base):
    __tablename__ = "external_identities"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    external_id: Mapped[str] = mapped_column(Text)
    external_type: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    entity_role: Mapped[str] = mapped_column(Text)
    entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    is_primary: Mapped[Optional[bool]] = mapped_column(
        Boolean, nullable=True, server_default="true"
    )
    identity_metadata = mapped_column(JSONB, nullable=True)
    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (
        Index(
            "ix_external_identities_external_id",
            "owner_id",
            "external_type",
            "external_id",
            unique=True,
        ),
    )


# ─── CORE TABLES ───


class Customer(Base):
    __tablename__ = "customers"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    name: Mapped[str] = mapped_column(Text)
    email: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    company: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[Optional[str]] = mapped_column(Text, nullable=True, server_default="active")
    preference: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    last_contact: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    orders: Mapped[list["Order"]] = relationship(back_populates="customer")


class Product(Base):
    __tablename__ = "products"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    name: Mapped[str] = mapped_column(Text)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    selling_price: Mapped[Optional[Decimal]] = mapped_column(Numeric, nullable=True)
    cost_price: Mapped[Optional[Decimal]] = mapped_column(
        Numeric, nullable=True, server_default="0"
    )
    stock_number: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, server_default="0")
    product_link: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    category: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    description_embedding = mapped_column(Vector(1536), nullable=True)
    orders: Mapped[list["Order"]] = relationship(back_populates="product")
    supplier_products: Mapped[list["SupplierProduct"]] = relationship(back_populates="product")
    partner_product_relations: Mapped[list["PartnerProductRelation"]] = relationship(
        back_populates="product"
    )

    __table_args__ = (
        Index(
            "ix_products_description_embedding",
            "description_embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"description_embedding": "vector_cosine_ops"},
        ),
    )


class Order(Base):
    __tablename__ = "orders"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    customer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("customers.id"))
    product_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("products.id"))
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    total_price: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0)
    order_date: Mapped[date] = mapped_column(Date, server_default=func.current_date())
    status: Mapped[str] = mapped_column(Text, default="pending")
    channel: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    customer: Mapped["Customer"] = relationship(back_populates="orders")
    product: Mapped["Product"] = relationship(back_populates="orders")


# ─── SUPPLIER TABLES ───


class Supplier(Base):
    __tablename__ = "suppliers"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    name: Mapped[str] = mapped_column(Text)
    email: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    category: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    contract_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[Optional[str]] = mapped_column(Text, nullable=True, server_default="active")
    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    supplier_products: Mapped[list["SupplierProduct"]] = relationship(back_populates="supplier")


class SupplierProduct(Base):
    """Junction table: links a supplier to a product with pricing and contract details."""

    __tablename__ = "supplier_products"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    supplier_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("suppliers.id"))
    product_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("products.id"))
    supply_price: Mapped[Optional[Decimal]] = mapped_column(Numeric, nullable=True)
    stock_we_buy: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, server_default="0")
    contract: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    lead_time_days: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    contract_start: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    contract_end: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    is_active: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True, server_default="true")
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    notes_embedding = mapped_column(Vector(1536), nullable=True)
    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    supplier: Mapped["Supplier"] = relationship(back_populates="supplier_products")
    product: Mapped["Product"] = relationship(back_populates="supplier_products")

    __table_args__ = (
        Index(
            "ix_supplier_products_notes_embedding",
            "notes_embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"notes_embedding": "vector_cosine_ops"},
        ),
    )


# ─── INVESTOR TABLES ───


class Investor(Base):
    __tablename__ = "investors"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    name: Mapped[str] = mapped_column(Text)
    email: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    focus: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[Optional[str]] = mapped_column(Text, nullable=True, server_default="active")
    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


# ─── PARTNER TABLES ───


class Partner(Base):
    __tablename__ = "partners"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    name: Mapped[str] = mapped_column(Text)
    email: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    partner_type: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[Optional[str]] = mapped_column(Text, nullable=True, server_default="active")
    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    agreements: Mapped[list["PartnerAgreement"]] = relationship(back_populates="partner")
    partner_product_relations: Mapped[list["PartnerProductRelation"]] = relationship(
        back_populates="partner"
    )


class PartnerAgreement(Base):
    __tablename__ = "partner_agreements"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    partner_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("partners.id"))
    description: Mapped[str] = mapped_column(Text)
    agreement_type: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, server_default="general"
    )
    revenue_share_pct: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2), nullable=True)
    start_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    end_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    is_active: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True, server_default="true")
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    description_embedding = mapped_column(Vector(1536), nullable=True)
    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    partner: Mapped["Partner"] = relationship(back_populates="agreements")
    partner_product_relations: Mapped[list["PartnerProductRelation"]] = relationship(
        back_populates="agreement"
    )

    __table_args__ = (
        Index(
            "ix_partner_agreements_description_embedding",
            "description_embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"description_embedding": "vector_cosine_ops"},
        ),
    )


class PartnerProductRelation(Base):
    __tablename__ = "partner_product_relations"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    partner_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("partners.id"))
    product_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("products.id"))
    agreement_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("partner_agreements.id"), nullable=True
    )
    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    partner: Mapped["Partner"] = relationship(back_populates="partner_product_relations")
    product: Mapped["Product"] = relationship(back_populates="partner_product_relations")
    agreement: Mapped[Optional["PartnerAgreement"]] = relationship(
        back_populates="partner_product_relations"
    )


# ─── POLICY TABLES ───


class PolicyChunk(Base):
    __tablename__ = "policy_chunks"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    source_file: Mapped[str] = mapped_column(Text)
    page_number: Mapped[int] = mapped_column(Integer, server_default="0")
    chunk_index: Mapped[int] = mapped_column(Integer, server_default="0")
    chunk_text: Mapped[str] = mapped_column(Text)
    subheading: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    category: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    hard_constraint: Mapped[bool] = mapped_column(Boolean, default=False)
    embedding = mapped_column(Vector(1536), nullable=False)
    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (
        Index(
            "ix_policy_chunks_embedding",
            "embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )


# ─── MEMORY / MESSAGING TABLES ───


class Message(Base):
    __tablename__ = "messages"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    conversation_thread_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversation_threads.id"), nullable=True
    )
    sender_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    sender_name: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    sender_role: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    direction: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    conversation_thread: Mapped[Optional["ConversationThread"]] = relationship(
        back_populates="messages"
    )

    __table_args__ = (
        Index(
            "ix_messages_owner_thread_created_at",
            "owner_id",
            "conversation_thread_id",
            "created_at",
        ),
    )


class ConversationThread(Base):
    __tablename__ = "conversation_threads"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    thread_type: Mapped[str] = mapped_column(Text)
    title: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    sender_external_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    sender_name: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    sender_role: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    sender_channel: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    last_message_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    messages: Mapped[list["Message"]] = relationship(back_populates="conversation_thread")
    sender_memories: Mapped[list["ConversationSenderMemory"]] = relationship(
        back_populates="conversation_thread"
    )
    conversation_memories: Mapped[list["ConversationMemory"]] = relationship(
        back_populates="conversation_thread"
    )

    __table_args__ = (
        Index("ix_conversation_threads_owner_type", "owner_id", "thread_type"),
        Index("ix_conversation_threads_owner_last_message_at", "owner_id", "last_message_at"),
        Index(
            "ux_conversation_threads_external_sender",
            "owner_id",
            "thread_type",
            "sender_channel",
            "sender_external_id",
            unique=True,
            postgresql_where=(thread_type == "external_sender"),
        ),
    )


class MemoryEntry(Base):
    __tablename__ = "memory_entries"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    sender_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    sender_name: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    sender_role: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    memory_type: Mapped[str] = mapped_column(Text)
    content: Mapped[str] = mapped_column(Text)
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    tags = mapped_column(ARRAY(Text), nullable=True, server_default="{}")
    importance: Mapped[Optional[Decimal]] = mapped_column(
        Numeric, nullable=True, server_default="0.5"
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class MemoryUpdateProposal(Base):
    __tablename__ = "memory_update_proposals"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    target_table: Mapped[str] = mapped_column(Text)
    target_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    proposed_content = mapped_column(JSONB)
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    risk_level: Mapped[Optional[str]] = mapped_column(Text, nullable=True, server_default="low")
    status: Mapped[Optional[str]] = mapped_column(Text, nullable=True, server_default="pending")
    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class PendingApproval(Base):
    __tablename__ = "pending_approvals"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    title: Mapped[str] = mapped_column(Text)
    sender: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    preview: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    proposal_type: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    risk_level: Mapped[Optional[str]] = mapped_column(Text, nullable=True, server_default="low")
    status: Mapped[Optional[str]] = mapped_column(Text, nullable=True, server_default="pending")
    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    proposal_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("memory_update_proposals.id"), nullable=True
    )
    held_reply_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("held_replies.id"), nullable=True
    )


class ReplyReviewRecord(Base):
    __tablename__ = "reply_review_records"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    trace_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    thread_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    sender_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    sender_name: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    sender_role: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    raw_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    reply_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    risk_level: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    risk_flags = mapped_column(JSONB, nullable=True, server_default="[]")
    approval_rule_flags = mapped_column(JSONB, nullable=True, server_default="[]")
    requires_approval: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    final_decision: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    review_label: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    reviewer_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    held_reply_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("held_replies.id"), nullable=True
    )
    message_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("messages.id"), nullable=True
    )
    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


# ─── HELD REPLIES (Risk Approval Flow) ───


class HeldReply(Base):
    __tablename__ = "held_replies"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    thread_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    sender_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    sender_name: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    sender_role: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    reply_text: Mapped[str] = mapped_column(Text)
    risk_level: Mapped[str] = mapped_column(Text, server_default="medium")
    risk_flags = mapped_column(JSONB, server_default="[]")
    status: Mapped[str] = mapped_column(Text, server_default="pending")
    reviewer_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


# ─── OWNER / MEMORY RULES ───


class OwnerMemoryRule(Base):
    __tablename__ = "owner_memory_rules"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    role: Mapped[str] = mapped_column(Text)
    category: Mapped[str] = mapped_column(Text)
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class EntityMemory(Base):
    __tablename__ = "entity_memories"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    entity_role: Mapped[str] = mapped_column(Text)
    entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    memory_type: Mapped[str] = mapped_column(Text)
    content: Mapped[str] = mapped_column(Text)
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    tags = mapped_column(ARRAY(Text), nullable=True, server_default="{}")
    importance: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, server_default="1")
    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class ConversationMemory(Base):
    __tablename__ = "conversation_memories"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    conversation_thread_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversation_threads.id"), nullable=True
    )
    entity_role: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    entity_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    summary: Mapped[str] = mapped_column(Text)
    keywords = mapped_column(ARRAY(Text), nullable=True, server_default="{}")
    happened_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    conversation_thread: Mapped[Optional["ConversationThread"]] = relationship(
        back_populates="conversation_memories"
    )


class ConversationSenderMemory(Base):
    __tablename__ = "conversation_sender_memories"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    conversation_thread_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversation_threads.id")
    )
    sender_external_id: Mapped[str] = mapped_column(Text)
    sender_name: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    sender_role: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    summary: Mapped[str] = mapped_column(Text)
    message_count_since_update: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, server_default="0"
    )
    last_message_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_summarized_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    conversation_thread: Mapped["ConversationThread"] = relationship(
        back_populates="sender_memories"
    )

    __table_args__ = (
        Index(
            "ux_conversation_sender_memories_owner_thread_sender",
            "owner_id",
            "conversation_thread_id",
            "sender_external_id",
            unique=True,
        ),
        Index("ix_conversation_sender_memories_owner_updated_at", "owner_id", "updated_at"),
    )


class DailyDigest(Base):
    __tablename__ = "daily_digest"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    title: Mapped[str] = mapped_column(Text)
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    risk: Mapped[Optional[str]] = mapped_column(Text, nullable=True, server_default="low")
    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Profile(Base):
    __tablename__ = "profiles"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    full_name: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    business_name: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    business_description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    business_industry: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    business_timezone: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, server_default="UTC"
    )
    preferred_language: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, server_default="en"
    )
    default_reply_tone: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, server_default="professional"
    )
    sender_summary_threshold: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, server_default="20"
    )
    notifications_email: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    notifications_enabled: Mapped[Optional[bool]] = mapped_column(
        Boolean, nullable=True, server_default="true"
    )
    memory_context: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    soul_context: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    rule_context: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
