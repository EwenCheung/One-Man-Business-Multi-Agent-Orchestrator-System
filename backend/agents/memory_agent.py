"""
Memory Agent (Section 8.3 & 7.10)

Dual-purpose agent controlled by state:
1. READ MODE: Executed during Orchestrator fan-out to search history.
2. UPDATE MODE: Executed at the end of the graph to save new preferences.
"""

def memory_agent_node(state: dict) -> dict:
    """
    If state contains 'task_id', it's a SubTask mapping (READ MODE).
    If state contains 'raw_message', it's the PipelineState (UPDATE MODE).
    """
    if "task_id" in state:
        # ── READ MODE (Grep search / History lookup) ──
        completed_task = state.copy()
        completed_task["status"] = "completed"
        completed_task["result"] = f"(Stub) Memory retrieved for: {state.get('description')}"
        return {"completed_tasks": [completed_task]}
        
    else:
        # ── UPDATE MODE (Post-send summarize & save) ──
        # TODO: Summarize interaction and extract new preferences for MEMORY.md
        return {
            "memory_updates": [{"stub": "Saved new preferences extracted from interaction."}]
        }
