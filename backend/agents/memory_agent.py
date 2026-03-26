"""
Memory Agent (PROPOSAL §4.5 + §4.8)

Dual-purpose agent controlled by invocation context:
1. READ MODE:  Executed during Orchestrator fan-out to search conversation history.
2. UPDATE MODE: Executed at the end of the pipeline to save new durable memory.

## TODO — READ MODE
- [ ] Connect to conversation history DB (messages table)
- [ ] Implement search: keyword grep + optional semantic search over past messages
- [ ] Prioritize concise summaries over dumping raw logs
- [ ] Mark stale or low-confidence memory
- [ ] Distinguish: recent_context vs durable_memory
- [ ] Add try/except with structured failure return

## TODO — UPDATE MODE
- [ ] Extract durable preferences from the completed interaction
- [ ] Extract relationship signals (sentiment shifts, new constraints)
- [ ] Extract unresolved follow-up items
- [ ] Store compact summaries, NOT raw conversation logs
- [ ] Write to DB (memory table), not static MEMORY.md
- [ ] Filter: only store high-value memory, skip transient noise

## DESIGN QUESTION
- [ ] Should READ and UPDATE be split into two separate functions/files?
       Currently using `task_id in state` to distinguish — this is fragile.
       Consider: memory_read_agent() + memory_update_agent()
"""

from backend.graph.state import SubTask

# ────────────────────────────────────────────────────────
# Prompt — READ MODE: search and summarize history
# ────────────────────────────────────────────────────────
MEMORY_READ_PROMPT = """\
You are a Deep Memory Retrieval Agent. Your job is to perform a 'grep-style' semantic/keyword 
search into deep historical conversation logs.

### Instructions
- The Orchestrator calls you ONLY when the recent `short_term_memory` is not enough (e.g., asking about specific old dates, past negotiations, or key decisions from months ago).
- Search the conversation history for information exactly matching the query below.
- Return concise summaries of the key points discussed, NOT raw message dumps.
- For each memory extracted, indicate:
  - `recent` — if it's uniquely from the last 7 days but important
  - `durable` — older but still relevant (like a contract signing or preference)
  - `stale` — old and possibly outdated (flag for human review)
- If no relevant deep history exists, say so clearly.

### Search Query
{task_description}

### Conversation History
{conversation_history}
"""

# ────────────────────────────────────────────────────────
# Prompt — UPDATE MODE: extract and save durable memory
# ────────────────────────────────────────────────────────
MEMORY_UPDATE_PROMPT = """\
You are a Memory Update Agent. Your job is to extract high-value information
from the completed interaction and save it as durable memory.

### Instructions
- Extract ONLY high-value items:
  - New preferences stated by the sender
  - Relationship signals (satisfaction, frustration, new requirements)
  - Unresolved items that need follow-up
  - Key decisions or commitments made
- Do NOT store: greetings, repeated information, transient noise
- Format each memory item as a structured record.

### Completed Interaction
- Sender: {sender_name} ({sender_role})
- Original Message: {raw_message}
- Reply Sent: {reply_text}
- Completed Tasks: {completed_tasks_summary}
"""


def memory_agent_node(state: dict) -> dict:
    """
    Dual-purpose memory agent.

    If state contains 'task_id' → READ MODE (SubTask from fan-out)
    If state contains 'raw_message' → UPDATE MODE (full PipelineState)

    Functions needed (implement later):
    READ MODE:
    - _search_history(query, sender_id) -> list[dict]
    - _summarize_history(raw_results) -> str

    UPDATE MODE:
    - _extract_preferences(interaction_data) -> list[dict]
    - _extract_followups(interaction_data) -> list[dict]
    - _save_to_memory_db(records) -> None
    """
    if "task_id" in state:
        # ── READ MODE (from Orchestrator fan-out) ──
        completed_task = state.copy()
        completed_task["status"] = "completed"
        completed_task["result"] = f"(Stub) Memory retrieved for: {state.get('description')}"
        return {"completed_tasks": [completed_task]}

    else:
        # ── UPDATE MODE (post-send, end of pipeline) ──
        # TODO: Extract and save durable memory
        return {
            "memory_updates": [{"stub": "Saved new preferences extracted from interaction."}]
        }
