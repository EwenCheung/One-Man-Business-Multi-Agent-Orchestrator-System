"""
SQLAlchemy ORM models — maps to PostgreSQL tables.

See AGENTS.md Section 9 for the full schema spec.
Add your table models here.
"""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""
    pass


# TODO: Define ORM table models here. Suggested tables from AGENTS.md:
#   - Contact           (contact_id, name, role_type, email, company, ...)
#   - ConversationThread (thread_id, contact_id, status, summary, ...)
#   - Message           (message_id, thread_id, sender_id, content, ...)
#   - Product           (product_id, name, description, selling_price, stock, ...)
#   - Supplier          (supplier_id, contact_id, supply_terms, ...)
#   - Investor          (investor_id, contact_id, portfolio_interest, ...)
#   - Partner           (partner_id, contact_id, agreement_summary, ...)
#   - ProductMetric     (product_id, cost, roi, daily_sales, margin, ...)
#   - MemoryEntry       (memory_id, contact_id, memory_type, summary, embedding, ...)
#   - PolicyRule        (rule_id, applicable_role, rule_text, severity, ...)
