import re

with open("backend/agents/memory_agent.py", "r") as f:
    content = f.read()

# 1. Add OWNER_MEMORY_UPDATE_PROMPT near MEMORY_UPDATE_PROMPT
owner_prompt = """
OWNER_MEMORY_UPDATE_PROMPT = \"\"\"\\
You are an expert Executive Assistant. Your job is to update the long-term memory document for the business owner.
You must compact the new interactions into the existing memory context, keeping the total document under 200 lines.

Business Description:
{business_description}

Existing Memory Context:
{previous_memory}

New Interaction to Integrate:
Owner said: {raw_message}
System did/replied: {reply_text}
Completed Tasks: {completed_tasks_summary}

Please output the updated, fully compacted memory context in plain text format. Retain all important historical facts, but integrate the new information logically and concisely.
\"\"\"
"""
content = content.replace("SENDER_SUMMARY_PROMPT = \"\"\"", owner_prompt + "\nSENDER_SUMMARY_PROMPT = \"\"\"")

# 2. Modify memory_update_node to handle owner role
owner_update_logic = """
        if (sender_role or "").lower() == "owner":
            from backend.db.models import Profile
            try:
                owner_uuid = __import__("uuid").UUID(str(owner_id))
            except Exception:
                owner_uuid = owner_id
            profile = session.query(Profile).filter(Profile.id == owner_uuid).first()
            if profile:
                business_desc = profile.business_description or ""
                prev_mem = profile.memory_context or ""
                
                llm = get_chat_llm(scope="memory", temperature=0.0)
                prompt = OWNER_MEMORY_UPDATE_PROMPT.format(
                    business_description=business_desc,
                    previous_memory=prev_mem,
                    raw_message=raw_message,
                    reply_text=reply_text,
                    completed_tasks_summary=completed_tasks_summary,
                )
                updated_memory = _normalize_text(getattr(llm.invoke(prompt), "content", ""))
                if updated_memory:
                    profile.memory_context = updated_memory
                    profile.updated_at = _utc_now()
                    session.commit()
                    return {
                        "memory_updates": {
                            "status": "completed",
                            "message": "Owner long-term memory updated and compacted.",
                            "count": 1,
                            "persisted_to": "profiles.memory_context"
                        }
                    }

"""

target_string = """
        sender_summary_update = None
        if (sender_role or "").lower() != "owner":
"""
content = content.replace(target_string, owner_update_logic + target_string)

with open("backend/agents/memory_agent.py", "w") as f:
    f.write(content)

