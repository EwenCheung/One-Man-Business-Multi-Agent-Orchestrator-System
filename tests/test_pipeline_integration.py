"""Mocked end-to-end integration tests for the LangGraph pipeline."""

from __future__ import annotations

import pytest

from backend.graph import pipeline_graph


def _make_task(
    task_id: str,
    assignee: str,
    description: str,
    *,
    status: str = "pending",
    result: str = "",
) -> dict[str, object]:
    return {
        "task_id": task_id,
        "description": description,
        "assignee": assignee,
        "status": status,
        "result": result,
        "priority": "required",
        "context_needed": [],
        "injected_context": {},
    }


def _default_intake(state: dict[str, object]) -> dict[str, object]:
    raw_message = str(state.get("raw_message", "Test message"))
    return {
        "owner_id": "owner-001",
        "sender_role": "customer",
        "sender_id": "sender-001",
        "external_sender_id": "sender-001",
        "entity_id": "customer-001",
        "sender_name": "Alice",
        "thread_id": "thread-001",
        "conversation_thread_id": "thread-001",
        "intent_label": "pricing",
        "urgency_level": "normal",
        "raw_message": raw_message,
        "soul_context": "Be direct and useful.",
        "rules_context": "Do not disclose sensitive data.",
        "long_term_memory": "Repeat customer.",
        "sender_memory": "Prefers concise replies.",
        "short_term_memory": [{"role": "user", "content": raw_message}],
        "guardrails_passed": True,
        "replan_count": 0,
    }


def _default_reply(_: dict[str, object]) -> dict[str, object]:
    return {
        "generated_reply_text": "Here is the verified reply.",
        "reply_text": "Here is the verified reply.",
        "confidence_note": "High confidence.",
        "confidence_level": "high",
        "unverified_claims": [],
        "tone_flags": [],
    }


def _default_approval_rules(_: dict[str, object]) -> dict[str, object]:
    return {
        "approval_rule_flags": [],
        "approval_rule_requires_approval": False,
    }


def _default_risk(_: dict[str, object]) -> dict[str, object]:
    return {
        "risk_level": "low",
        "risk_flags": [],
        "requires_approval": False,
    }


def _default_memory_update(_: dict[str, object]) -> dict[str, object]:
    return {
        "memory_updates": [{"summary": "Stored a low-risk interaction summary."}],
    }


def _default_memory_read(task: dict[str, object]) -> dict[str, object]:
    return {
        "completed_tasks": [
            _make_task(
                str(task["task_id"]),
                "memory",
                str(task["description"]),
                status="completed",
                result="Historical note retrieved.",
            )
        ]
    }


def _build_test_graph(
    monkeypatch: pytest.MonkeyPatch,
    *,
    intake=_default_intake,
    orchestrator,
    retriever=None,
    policy=None,
    research=None,
    memory_read=_default_memory_read,
    reply=_default_reply,
    approval_rules=_default_approval_rules,
    risk=_default_risk,
    memory_update=_default_memory_update,
    held_reply_id: str = "held-reply-001",
):
    monkeypatch.setattr(pipeline_graph, "intake_node", intake)
    monkeypatch.setattr(pipeline_graph, "orchestrator_agent", orchestrator)
    monkeypatch.setattr(pipeline_graph, "retrieval_agent", retriever or _default_memory_read)
    monkeypatch.setattr(pipeline_graph, "policy_agent", policy or _default_memory_read)
    monkeypatch.setattr(pipeline_graph, "research_agent", research or _default_memory_read)
    monkeypatch.setattr(pipeline_graph, "memory_read_node", memory_read)
    monkeypatch.setattr(pipeline_graph, "reply_agent", reply)
    monkeypatch.setattr(pipeline_graph, "approval_rule_node", approval_rules)
    monkeypatch.setattr(pipeline_graph, "risk_node", risk)
    monkeypatch.setattr(pipeline_graph, "memory_update_node", memory_update)
    monkeypatch.setattr(pipeline_graph, "hold_reply", lambda **_: held_reply_id)
    return pipeline_graph.build_graph()


@pytest.mark.integration
def test_pipeline_auto_sends_low_risk_reply(monkeypatch: pytest.MonkeyPatch):
    def orchestrator(state: dict[str, object]) -> dict[str, object]:
        completed = list(state.get("completed_tasks", []))
        if completed:
            return {"active_tasks": [], "route_to_reply": True}
        return {
            "active_tasks": [
                _make_task(
                    "task-1",
                    "retriever",
                    "Fetch verified bundle pricing guidance.",
                )
            ],
            "route_to_reply": False,
        }

    def retriever(task: dict[str, object]) -> dict[str, object]:
        return {
            "completed_tasks": [
                _make_task(
                    str(task["task_id"]),
                    "retriever",
                    str(task["description"]),
                    status="completed",
                    result="Bundle pricing verified. Approval not required.",
                )
            ]
        }

    graph = _build_test_graph(monkeypatch, orchestrator=orchestrator, retriever=retriever)
    result = graph.invoke({"raw_message": "Can you offer a bundle discount?"})

    assert result["risk_level"] == "low"
    assert result["reply_text"] == "Here is the verified reply."
    assert len(result["completed_tasks"]) == 1
    assert result["completed_tasks"][0]["assignee"] == "retriever"
    assert result["memory_updates"][0]["summary"] == "Stored a low-risk interaction summary."


@pytest.mark.integration
def test_pipeline_holds_medium_risk_reply_for_owner_approval(monkeypatch: pytest.MonkeyPatch):
    def orchestrator(state: dict[str, object]) -> dict[str, object]:
        if state.get("completed_tasks"):
            return {"active_tasks": [], "route_to_reply": True}
        return {
            "active_tasks": [
                _make_task(
                    "task-1",
                    "retriever",
                    "Fetch shipping policy and delivery constraints.",
                )
            ],
            "route_to_reply": False,
        }

    def retriever(task: dict[str, object]) -> dict[str, object]:
        return {
            "completed_tasks": [
                _make_task(
                    str(task["task_id"]),
                    "retriever",
                    str(task["description"]),
                    status="completed",
                    result="Shipping policy retrieved.",
                )
            ]
        }

    def reply(_: dict[str, object]) -> dict[str, object]:
        return {
            "generated_reply_text": "We guarantee delivery by Friday.",
            "reply_text": "We guarantee delivery by Friday.",
            "confidence_note": "Medium confidence due to delivery promise.",
            "confidence_level": "medium",
            "unverified_claims": ["delivery by Friday"],
            "tone_flags": ["over-committed"],
        }

    def approval_rules(_: dict[str, object]) -> dict[str, object]:
        return {
            "approval_rule_flags": ["APPROVAL RULE: Delivery commitment detected"],
            "approval_rule_requires_approval": True,
        }

    def risk(_: dict[str, object]) -> dict[str, object]:
        return {
            "risk_level": "medium",
            "risk_flags": ["Delivery commitment detected"],
            "requires_approval": True,
        }

    graph = _build_test_graph(
        monkeypatch,
        orchestrator=orchestrator,
        retriever=retriever,
        reply=reply,
        approval_rules=approval_rules,
        risk=risk,
    )
    result = graph.invoke({"raw_message": "Can you guarantee delivery by Friday?"})

    assert result["risk_level"] == "medium"
    assert result["held_reply_id"] == "held-reply-001"
    assert result["generated_reply_text"] == "We guarantee delivery by Friday."
    assert result["reply_text"] == "[HELD FOR APPROVAL]"


@pytest.mark.integration
def test_pipeline_fans_out_and_aggregates_parallel_subagents(monkeypatch: pytest.MonkeyPatch):
    def orchestrator(state: dict[str, object]) -> dict[str, object]:
        completed = list(state.get("completed_tasks", []))
        if len(completed) >= 2:
            return {"active_tasks": [], "route_to_reply": True}
        return {
            "active_tasks": [
                _make_task("task-r", "retriever", "Fetch internal stock data."),
                _make_task("task-p", "policy", "Check discount approval policy."),
            ],
            "route_to_reply": False,
        }

    def retriever(task: dict[str, object]) -> dict[str, object]:
        return {
            "completed_tasks": [
                _make_task(
                    str(task["task_id"]),
                    "retriever",
                    str(task["description"]),
                    status="completed",
                    result="Stock level confirmed.",
                )
            ]
        }

    def policy(task: dict[str, object]) -> dict[str, object]:
        return {
            "completed_tasks": [
                _make_task(
                    str(task["task_id"]),
                    "policy",
                    str(task["description"]),
                    status="completed",
                    result="Discount within approved range.",
                )
            ]
        }

    graph = _build_test_graph(
        monkeypatch,
        orchestrator=orchestrator,
        retriever=retriever,
        policy=policy,
    )
    result = graph.invoke({"raw_message": "Can we approve this bulk quote?"})

    assignees = sorted(task["assignee"] for task in result["completed_tasks"])
    assert assignees == ["policy", "retriever"]
    assert result["route_to_reply"] is True
    assert result["reply_text"] == "Here is the verified reply."


@pytest.mark.integration
def test_pipeline_quarantines_subagent_failure_and_still_completes(monkeypatch: pytest.MonkeyPatch):
    def orchestrator(state: dict[str, object]) -> dict[str, object]:
        failed = list(state.get("failed_tasks", []))
        completed = list(state.get("completed_tasks", []))
        if failed or completed:
            return {"active_tasks": [], "route_to_reply": True}
        return {
            "active_tasks": [
                _make_task("task-1", "retriever", "Fetch latest supplier pricing.")
            ],
            "route_to_reply": False,
        }

    def retriever(_: dict[str, object]) -> dict[str, object]:
        raise RuntimeError("database timeout")

    def reply(state: dict[str, object]) -> dict[str, object]:
        assert len(state.get("failed_tasks", [])) == 1
        return {
            "generated_reply_text": "I need to verify supplier pricing before confirming terms.",
            "reply_text": "I need to verify supplier pricing before confirming terms.",
            "confidence_note": "Low confidence because retrieval failed.",
            "confidence_level": "low",
            "unverified_claims": [],
            "tone_flags": [],
        }

    graph = _build_test_graph(monkeypatch, orchestrator=orchestrator, retriever=retriever, reply=reply)
    result = graph.invoke({"raw_message": "Can you confirm the supplier pricing?"})

    assert len(result["failed_tasks"]) == 1
    failed_task = result["failed_tasks"][0]
    assert failed_task["status"] == "failed"
    assert failed_task["assignee"] == "retriever"
    assert result["reply_text"] == "I need to verify supplier pricing before confirming terms."
    assert result["risk_level"] == "low"
