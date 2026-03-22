"""
LangGraph Pipeline Graph (Section 6)

Wires all agents and nodes into a single StateGraph using a
hub-and-spoke architecture around the Orchestrator.

Flow:
    receiver → triage → context_builder → policy → orchestrator

    orchestrator → [conditional routing based on plan]:
        - retriever → [returns to orchestrator]
        - research  → [returns to orchestrator]
        - policy    → [revisit, returns to orchestrator]
        - reply     → [proceeds to risk layer]

    reply → risk → update → END
"""

from langgraph.graph import StateGraph, END

from backend.graph.state import PipelineState

# ── Import nodes (deterministic) ──────────────────────────────
from backend.nodes.receiver import receiver_node
from backend.nodes.context_builder import context_builder_node
from backend.nodes.risk import risk_node

# ── Import agents (LLM-powered) ──────────────────────────────
from backend.agents.triage_agent import triage_agent
from backend.agents.policy_agent import policy_agent
from backend.agents.orchestrator_agent import orchestrator_agent
from backend.agents.retriever_agent import retriever_agent
from backend.agents.research_agent import research_agent
from backend.agents.reply_agent import reply_agent
from backend.agents.update_agent import update_agent


def route_orchestrator(state: PipelineState) -> str:
    """
    Hub-and-spoke routing: Decide the next step for the orchestrator.
    Routes to internal retrieval, external research, revisiting policy,
    or proceeding to draft the reply.
    """
    # Default to 'reply' if not specified
    next_step = state.get("orchestrator_next_step", "reply")
    
    if next_step in ["retriever", "research", "policy"]:
        return next_step
        
    return "reply"


def build_graph() -> StateGraph:
    """
    Construct and return the compiled LangGraph pipeline.

    Returns:
        A compiled StateGraph ready to .invoke() or .stream().
    """
    graph = StateGraph(PipelineState)

    # ── Add nodes ─────────────────────────────────────────────
    graph.add_node("receiver", receiver_node)
    graph.add_node("triage", triage_agent)
    graph.add_node("context_builder", context_builder_node)
    graph.add_node("policy", policy_agent)
    graph.add_node("orchestrator", orchestrator_agent)
    graph.add_node("retriever", retriever_agent)
    graph.add_node("research", research_agent)
    graph.add_node("reply", reply_agent)
    graph.add_node("risk", risk_node)
    graph.add_node("update", update_agent)

    # ── Define Initial Linear Flow ────────────────────────────
    graph.set_entry_point("receiver")

    graph.add_edge("receiver", "triage")
    graph.add_edge("triage", "context_builder")
    graph.add_edge("context_builder", "policy")
    graph.add_edge("policy", "orchestrator")

    # ── Orchestrator Hub-and-Spoke Routing ────────────────────
    graph.add_conditional_edges("orchestrator", route_orchestrator, {
        "retriever": "retriever",
        "research": "research",
        "policy": "policy",
        "reply": "reply",
    })

    # Return paths back to Orchestrator hub
    graph.add_edge("retriever", "orchestrator")
    graph.add_edge("research", "orchestrator")
    # Note: "policy" already has an edge to "orchestrator" above!

    # ── Final Output & Memory Flow ────────────────────────────
    graph.add_edge("reply", "risk")
    graph.add_edge("risk", "update")
    graph.add_edge("update", END)

    return graph.compile()


# ── Compiled graph singleton ──────────────────────────────────
pipeline = build_graph()
