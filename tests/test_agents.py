"""
Agent Tests — verify each sub-agent handles inputs correctly.

## TODO
- [ ] Test retriever_agent with mocked DB call → returns structured result
- [ ] Test policy_agent with known RULE.md → returns allowed/disallowed
- [ ] Test research_agent with mocked web search → returns sourced findings
- [ ] Test memory_agent READ mode → returns relevant history summary
- [ ] Test memory_agent UPDATE mode → extracts and formats durable memory
- [ ] Test reply_agent with mocked LLM → applies correct tone per role
- [ ] Test each agent returns correct dict shape (completed_tasks list)
- [ ] Test each agent handles empty/missing input gracefully
"""


def test_retriever_returns_completed_task():
    """Retriever should return a dict with 'completed_tasks' list."""
    from backend.agents.retrieval_agent import retrieval_agent

    task = {
        "task_id": "1",
        "description": "Fetch stock for laptops",
        "assignee": "retriever",
        "status": "pending",
        "result": "",
        "injected_context": {"sender_role": "customer", "sender_id": "cust-01"},
    }
    result = retrieval_agent(task)

    assert "completed_tasks" in result
    assert len(result["completed_tasks"]) == 1
    assert result["completed_tasks"][0]["status"] == "completed"


def test_policy_returns_completed_task():
    """Policy should return a dict with 'completed_tasks' list."""
    from backend.agents.policy_agent import policy_agent

    task = {
        "task_id": "2",
        "description": "Check discount policy",
        "assignee": "policy",
        "status": "pending",
        "result": "",
    }
    result = policy_agent(task)

    assert "completed_tasks" in result
    assert result["completed_tasks"][0]["status"] == "completed"


def test_memory_read_mode():
    """Memory agent with task_id should run in READ mode."""
    from backend.agents.memory_agent import memory_read_node

    task = {
        "task_id": "3",
        "description": "Search past negotiations",
        "assignee": "memory",
        "status": "pending",
        "result": "",
        "injected_context": {"owner_id": "00000000-0000-0000-0000-000000000000"},
    }
    result = memory_read_node(task)

    assert "completed_tasks" in result


def test_memory_update_mode():
    """Memory agent without task_id should run in UPDATE mode."""
    from backend.agents.memory_agent import memory_update_node

    state = {
        "raw_message": "Hello",
        "reply_text": "Hi there",
        "sender_name": "Test",
        "owner_id": "00000000-0000-0000-0000-000000000000",
    }
    result = memory_update_node(state)

    assert "memory_updates" in result


def test_reply_returns_text():
    """Reply agent should return reply_text and confidence_note."""
    from backend.agents.reply_agent import reply_agent

    state = {
        "sender_role": "customer",
        "completed_tasks": [],
        "soul_context": "",
        "rules_context": "",
    }
    result = reply_agent(state)

    assert "reply_text" in result
    assert "confidence_note" in result
