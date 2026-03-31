"""
LangGraph Pipeline Graph (Section 6)

Wires all agents into a Supervisor Multi-Agent network using
LangGraph's `Send` API for parallel fan-out / fan-in execution.

Flow:
    intake → orchestrator (Supervisor)

    orchestrator → [FAN-OUT parallel Send to tasks]:
        - retriever(s)
        - policy(s)
        - research(s)
        - memory_read(s)

    [Nodes complete] → [FAN-IN aggregation back to Orchestrator]
    orchestrator evaluates results.
    If route_to_reply=True → reply → risk →
        LOW  → memory_update → END
        MED/HIGH → hold_for_approval → END (owner decides via dashboard)
"""

import logging
import operator
from typing import Annotated, Sequence

from langgraph.graph import StateGraph, END
from langgraph.types import Send

from backend.graph.state import PipelineState, SubTask

# ── Import nodes ──────────────────────────────
from backend.nodes.intake import intake_node
from backend.nodes.risk import risk_node

# ── Import agents ──────────────────────────────
from backend.agents.orchestrator_agent import orchestrator_agent
from backend.agents.retrieval_agent import retrieval_agent
from backend.agents.policy_agent import policy_agent
from backend.agents.research_agent import research_agent
from backend.agents.memory_agent import memory_agent_node
from backend.agents.reply_agent import reply_agent

from backend.utils.error_handler import safe_agent_call
from backend.services.approval_service import hold_reply

logger = logging.getLogger(__name__)


def continue_from_orchestrator(state: PipelineState):
    """
    Supervisor Router Function.
    Evaluates Active Tasks output by the Orchestrator and fans them out
    using the Send API. If ready_to_reply is True, routes out of the loop.
    """
    if state.get("route_to_reply", False):
        return "reply"

    tasks = state.get("active_tasks", [])
    sends = []

    # Fan-out: Map each task to its assigned sub-agent Node
    for task in tasks:
        # ── Selective Context Injection ──
        # Extract requested variables from the global state
        injected = {}
        for key in task.get("context_needed", []):
            if key in state:
                injected[key] = state[key]
        
        # Attach strictly to the designated isolation boundary
        task["injected_context"] = injected
        
        assignee = task.get("assignee")
        if assignee == "retriever":
            sends.append(Send("retriever", task))
        elif assignee == "policy":
            sends.append(Send("policy", task))
        elif assignee == "research":
            sends.append(Send("research", task))
        elif assignee == "memory":
            sends.append(Send("memory_read", task))

    # Fallback to reply if no valid tasks to prevent infinite loop
    if not sends:
        return "reply"
        
    return sends


def route_after_risk(state: PipelineState) -> str:
    """
    Conditional Router: Routes based on risk level after risk evaluation.

    LOW risk → proceed to memory_update (auto-send reply)
    MEDIUM/HIGH risk → hold reply for owner approval via dashboard
    """
    risk_level = state.get("risk_level", "low").lower()
    requires_approval = state.get("requires_approval", False)

    if risk_level in ("medium", "high") or requires_approval:
        return "hold_for_approval"
    return "memory_update"


def hold_for_approval_node(state: PipelineState) -> dict:
    """
    Saves the flagged reply to held_replies table and creates a
    pending_approvals entry for the owner dashboard.

    The reply is NOT sent until the owner approves it via the API.
    """
    reply_text = state.get("reply_text", "")
    risk_level = state.get("risk_level", "medium")
    risk_flags = state.get("risk_flags", [])

    # We need an owner_id — for now use a placeholder that the API layer can resolve
    # In production, this should come from the authenticated user context
    owner_id = state.get("owner_id", "00000000-0000-0000-0000-000000000000")

    try:
        held_reply_id = hold_reply(
            owner_id=owner_id,
            reply_text=reply_text,
            risk_level=risk_level,
            risk_flags=risk_flags,
            sender_id=state.get("sender_id"),
            sender_name=state.get("sender_name"),
            sender_role=state.get("sender_role"),
            thread_id=state.get("thread_id"),
        )
        logger.info(
            "Reply held for approval | risk=%s | held_reply_id=%s | flags=%s",
            risk_level, held_reply_id, risk_flags,
        )
        return {
            "held_reply_id": held_reply_id,
            "reply_text": f"[HELD FOR APPROVAL] {reply_text}",
        }
    except Exception as e:
        logger.error("Failed to hold reply for approval: %s", e)
        # Fallback: still mark as held but log the error
        return {
            "held_reply_id": "",
            "reply_text": f"[HOLD FAILED — REVIEW MANUALLY] {reply_text}",
        }


def build_graph() -> StateGraph:
    """Construct and compile the LangGraph Supervisor pipeline."""
    graph = StateGraph(PipelineState)

    # ── Add main nodes ─────────────────────────────────────────
    graph.add_node("intake", intake_node)
    graph.add_node("orchestrator", orchestrator_agent)
    graph.add_node("reply", reply_agent)
    graph.add_node("risk", risk_node)
    
    # ── Add memory nodes (dual purpose) ────────────────────────
    graph.add_node("memory_read", safe_agent_call(memory_agent_node))
    graph.add_node("memory_update", safe_agent_call(memory_agent_node))

    # ── Add risk approval node ──────────────────────────────────
    graph.add_node("hold_for_approval", hold_for_approval_node)

    # ── Add Sub-Agent Nodes (mapped via Send) ──────────────────
    graph.add_node("retriever", safe_agent_call(retrieval_agent))
    graph.add_node("policy", safe_agent_call(policy_agent))
    graph.add_node("research", safe_agent_call(research_agent))

    # ── Define Edge Flow ───────────────────────────────────────
    graph.set_entry_point("intake")
    graph.add_edge("intake", "orchestrator")

    # ── Supervisor Fan-Out Routing ─────────────────────────────
    # Orchestrator conditionally sends to any number of parallel sub-agents
    graph.add_conditional_edges(
        "orchestrator", 
        continue_from_orchestrator, 
        ["retriever", "policy", "research", "memory_read", "reply"]
    )

    # ── Supervisor Fan-In Routing ──────────────────────────────
    # Sub-agents always return their results back to the Orchestrator
    graph.add_edge("retriever", "orchestrator")
    graph.add_edge("policy", "orchestrator")
    graph.add_edge("research", "orchestrator")
    graph.add_edge("memory_read", "orchestrator")

    # ── Final Output Flow ──────────────────────────────────────
    graph.add_edge("reply", "risk")

    # ── CONDITIONAL: Risk routes based on risk level ───────────
    graph.add_conditional_edges(
        "risk",
        route_after_risk,
        {
            "memory_update": "memory_update",
            "hold_for_approval": "hold_for_approval",
        },
    )

    # ── Terminal edges ─────────────────────────────────────────
    graph.add_edge("memory_update", END)
    graph.add_edge("hold_for_approval", END)

    return graph.compile()


# ── Compiled graph singleton ──────────────────────────────────
pipeline = build_graph()
