"""
Nodes package — deterministic / rule-based logic (no LLM).

These nodes do NOT call an LLM. They perform pure logic like
message normalization, context assembly, and rule-based risk checks.

LLM-powered logic belongs in backend/agents/ instead.

Nodes:
  - receiver        → Standardize incoming messages (Section 7.1)
  - context_builder → Assemble initial context (Section 7.3)
  - risk            → Rule-based risk evaluation (Section 7.9)
"""
