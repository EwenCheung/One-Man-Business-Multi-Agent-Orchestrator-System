"""
Agents package — LLM-powered agents using LangChain/LangGraph.

Each agent in this directory wraps an LLM call for a specific pipeline stage.
Deterministic logic belongs in backend/nodes/ instead.

Active Agents:
  - orchestrator_agent → Core planner / router
  - retrieval_agent    → Internal hybrid retrieval
  - research_agent     → External research
  - policy_agent       → Policy & constraint lookup
  - memory_agent       → Deep historical grep (READ) and preference extraction (UPDATE)
  - reply_agent        → Reply generation & tone adjustment
"""
