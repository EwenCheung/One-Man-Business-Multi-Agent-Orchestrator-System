"""
Database Models (PROPOSAL §10)

SQLAlchemy ORM models for all persistent tables.

## TODO
- [ ] Define Message model (id, thread_id, sender_id, content, role, timestamp, status)
- [ ] Define SenderProfile model (id, name, role, email, metadata, created_at)
- [ ] Define PolicyRule model (id, category, rule_text, hard_constraint, created_at)
- [x] Define PolicyChunk model - chunked policy docs with pgvector embeddings
- [ ] Define MemoryRecord model (id, sender_id, memory_type, content, confidence, created_at, expires_at)
- [ ] Add pgvector column on MemoryRecord and PolicyRule
"""

from datetime import datetime, date
from decimal import Decimal
from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    String, Text, Numeric, Integer, Boolean,
    Date, DateTime, ForeignKey, Index, func
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

class Base(DeclarativeBase):
    """Base class for all ORM models."""
    pass

# ─── CORE TABLES ───

class Customer(Base):
    __tablename__ = "customers"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    email: Mapped[str] = mapped_column(String(255), nullable=True)
    phone: Mapped[str] = mapped_column(String(50), nullable=True)
    address: Mapped[str] = mapped_column(Text, nullable=True)
    platform: Mapped[str] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    orders: Mapped[list["Order"]] = relationship(back_populates="customer")

class Product(Base):
    __tablename__ = "products"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text, nullable=True)
    selling_price: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    cost_price: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    stock_quantity: Mapped[int] = mapped_column(Integer, default=0)
    category: Mapped[str] = mapped_column(String(100), nullable=True)
    link: Mapped[str] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
    description_embedding = mapped_column(Vector(1536), nullable=True)
    orders: Mapped[list["Order"]] = relationship(back_populates="product")
    supply_contracts: Mapped[list["SupplyContract"]] = relationship(back_populates="product")
    partner_products: Mapped[list["PartnerProduct"]] = relationship(back_populates="product")

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
    id: Mapped[int] = mapped_column(primary_key=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"))
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))
    quantity: Mapped[int] = mapped_column(Integer)
    total_price: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    order_date: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    channel: Mapped[str] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    customer: Mapped["Customer"] = relationship(back_populates="orders")
    product: Mapped["Product"] = relationship(back_populates="orders")

# ─── SUPPLIER TABLES ───

class Supplier(Base):
    __tablename__ = "suppliers"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    contact_person: Mapped[str] = mapped_column(String(255), nullable=True)
    email: Mapped[str] = mapped_column(String(255), nullable=True)
    phone: Mapped[str] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    supply_contracts: Mapped[list["SupplyContract"]] = relationship(back_populates="supplier")

class SupplyContract(Base):
    __tablename__ = "supply_contracts"
    id: Mapped[int] = mapped_column(primary_key=True)
    supplier_id: Mapped[int] = mapped_column(ForeignKey("suppliers.id"))
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))
    supply_price: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    total_order_qty: Mapped[int] = mapped_column(Integer, default=1)
    lead_time_days: Mapped[int] = mapped_column(Integer, nullable=True)
    contract_start: Mapped[date] = mapped_column(Date)
    contract_end: Mapped[date] = mapped_column(Date, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    notes: Mapped[str] = mapped_column(Text, nullable=True)
    notes_embedding = mapped_column(Vector(1536), nullable=True)
    supplier: Mapped["Supplier"] = relationship(back_populates="supply_contracts")
    product: Mapped["Product"] = relationship(back_populates="supply_contracts")

    __table_args__ = (
        Index(
            "ix_supply_contracts_notes_embedding",
            "notes_embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"notes_embedding": "vector_cosine_ops"},
        ),
    )

# ─── PARTNER TABLES ───

class Partner(Base):
    __tablename__ = "partners"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    contact_person: Mapped[str] = mapped_column(String(255), nullable=True)
    email: Mapped[str] = mapped_column(String(255), nullable=True)
    phone: Mapped[str] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    agreements: Mapped[list["PartnerAgreement"]] = relationship(back_populates="partner")
    partner_products: Mapped[list["PartnerProduct"]] = relationship(back_populates="partner")

class PartnerAgreement(Base):
    __tablename__ = "partner_agreements"
    id: Mapped[int] = mapped_column(primary_key=True)
    partner_id: Mapped[int] = mapped_column(ForeignKey("partners.id"))
    description: Mapped[str] = mapped_column(Text, nullable=True)
    agreement_type: Mapped[str] = mapped_column(String(50))
    revenue_share_pct: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=True)
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    notes: Mapped[str] = mapped_column(Text, nullable=True)
    description_embedding = mapped_column(Vector(1536), nullable=True)
    partner: Mapped["Partner"] = relationship(back_populates="agreements")
    partner_products: Mapped[list["PartnerProduct"]] = relationship(back_populates="agreement")

    __table_args__ = (
        Index(
            "ix_partner_agreements_description_embedding",
            "description_embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"description_embedding": "vector_cosine_ops"},
        ),
    )

class PartnerProduct(Base):
    __tablename__ = "partner_products"
    id: Mapped[int] = mapped_column(primary_key=True)
    partner_id: Mapped[int] = mapped_column(ForeignKey("partners.id"))
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))
    agreement_id: Mapped[int] = mapped_column(ForeignKey("partner_agreements.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    partner: Mapped["Partner"] = relationship(back_populates="partner_products")
    product: Mapped["Product"] = relationship(back_populates="partner_products")
    agreement: Mapped["PartnerAgreement"] = relationship(back_populates="partner_products")

# ─── POLICY TABLES ───

class PolicyChunk(Base):
    __tablename__ = "policy_chunks"

    id: Mapped[int] = mapped_column(primary_key=True)
    source_file: Mapped[str] = mapped_column(String(255))
    page_number: Mapped[int] = mapped_column(Integer)
    chunk_index: Mapped[int] = mapped_column(Integer)
    chunk_text: Mapped[str] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(100), nullable=True)
    hard_constraint: Mapped[bool] = mapped_column(Boolean, default=False)
    embedding = mapped_column(Vector(1536), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    # Use HNSW index to build embedding
    __table_args__ = (
        Index(
            "ix_policy_chunks_embedding",
            "embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )
