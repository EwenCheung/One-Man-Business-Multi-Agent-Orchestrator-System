"""
Database Models (PROPOSAL §10)

SQLAlchemy ORM models for all persistent tables.

## TODO
- [ ] Define Message model (id, thread_id, sender_id, content, role, timestamp, status)
- [ ] Define ConversationThread model (id, sender_id, subject, created_at, updated_at)
- [ ] Define SenderProfile model (id, name, role, email, metadata, created_at)
- [ ] Define PolicyRule model (id, category, rule_text, hard_constraint, created_at)
- [ ] Define MemoryRecord model (id, sender_id, memory_type, content, confidence, created_at, expires_at)
- [ ] Define HeldReply model (id, thread_id, reply_text, risk_level, risk_flags, status, created_at)
- [ ] Add pgvector column for semantic search on MemoryRecord and PolicyRule
- [ ] Add indexes for common queries (sender_id, thread_id, status)
"""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base class for all ORM models."""
    pass


# TODO: class Message(Base):
#     __tablename__ = "messages"
#     id, thread_id, sender_id, content, role, timestamp, status


# TODO: class ConversationThread(Base):
#     __tablename__ = "conversation_threads"
#     id, sender_id, subject, created_at, updated_at


# TODO: class SenderProfile(Base):
#     __tablename__ = "sender_profiles"
#     id, name, role, email, company, metadata, created_at


# TODO: class PolicyRule(Base):
#     __tablename__ = "policy_rules"
#     id, category, rule_text, hard_constraint, embedding (pgvector), created_at


# TODO: class MemoryRecord(Base):
#     __tablename__ = "memory_records"
#     id, sender_id, memory_type, content, confidence, embedding (pgvector), created_at, expires_at


# TODO: class HeldReply(Base):
#     __tablename__ = "held_replies"
#     id, thread_id, reply_text, risk_level, risk_flags, status, reviewer_notes, created_at
