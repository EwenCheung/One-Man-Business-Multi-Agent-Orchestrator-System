"""
Agents package — LLM-powered agents using LangChain/LangGraph.

Each agent in this directory wraps an LLM call for a specific pipeline stage.
Deterministic logic (no LLM) belongs in backend/nodes/ instead.

Agents:
  - triage_agent       → Intent classification, role prediction (Section 7.2)
  - policy_agent       → Policy & constraint lookup (Section 7.8)
  - orchestrator_agent → Core planner / router (Section 7.4)
  - retriever_agent    → Internal hybrid retrieval (Section 7.5)
  - research_agent     → External research (Section 7.6)
  - reply_agent        → Reply generation (Section 7.7)
  - update_agent       → Memory update selection (Section 7.10)
"""
