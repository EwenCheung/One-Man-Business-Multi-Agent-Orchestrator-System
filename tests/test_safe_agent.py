import traceback
from backend.utils.error_handler import safe_agent_call
from backend.graph.state import SubTask


def test_safe_agent_call_quarantine():
    # 1. Create a dummy agent that intentionally crashes
    def exploding_agent(task: dict) -> dict:
        raise ValueError("Database connection dropped unexpectedly!")

    # 2. Wrap it with our new harness guard
    safe_exploding_agent = safe_agent_call(exploding_agent)

    # 3. Create a mock subtask from the Orchestrator
    task = {
        "task_id": "task-123",
        "description": "Fetch policies for customer 5",
        "assignee": "policy",
        "status": "pending",
        "result": "",
        "priority": "required",
        "context_needed": ["sender_role"],
        "injected_context": {"sender_role": "Customer"},
    }

    # 4. Execute (it should NOT crash Python, but return a failed state)
    result = safe_exploding_agent(task)

    # 5. Verify Quarantine Payload
    assert "failed_tasks" in result, (
        "Safe wrapper must return a 'failed_tasks' key for LangGraph aggregation"
    )
    assert len(result["failed_tasks"]) == 1

    failure = result["failed_tasks"][0]
    assert failure["status"] == "failed"
    assert failure["task_id"] == "task-123"
    assert "Agent 'policy' failed during execution" in failure["result"]
    assert "execution_failure" in failure["result"]
    assert "Database connection dropped unexpectedly!" in failure["result"]

    print("SUCCESS: Sub-Agent Harness Quarantine works perfectly!")
    print("Failure payload captured successfully:\\n", failure["result"])


if __name__ == "__main__":
    test_safe_agent_call_quarantine()
