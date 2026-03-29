"""
Owner Approval Service

Handles the hold → notify → approve/reject → send/edit cycle
for replies flagged by the Risk Node.

## TODO
- [ ] Save held reply to DB (HeldReply table) with risk_level and risk_flags
- [ ] Notify owner (webhook / email / dashboard push)
- [ ] Handle approve action: release reply, trigger memory_update, mark as sent
- [ ] Handle reject action: return to reply agent for edit, or discard
- [ ] Handle edit action: owner provides edited text, skip re-risk or re-risk
- [ ] Track approval latency and timeout (auto-escalate if no response in N hours)
"""


# TODO: async def hold_reply(reply_text: str, risk_level: str, risk_flags: list, thread_id: str) -> str:
#     """
#     Saves a held reply to the database.
#     Returns the held_reply_id for tracking.
#     """
#     pass


# TODO: async def notify_owner(held_reply_id: str, channel: str = "dashboard") -> bool:
#     """
#     Sends a notification to the owner about a pending approval.
#     Channel options: "dashboard", "email", "webhook"
#     """
#     pass


# TODO: async def approve_reply(held_reply_id: str, reviewer_notes: str = "") -> dict:
#     """
#     Approves a held reply. Triggers send + memory update.
#     Returns: {"status": "approved", "sent": True}
#     """
#     pass


# TODO: async def reject_reply(held_reply_id: str, reason: str = "") -> dict:
#     """
#     Rejects a held reply. Routes back for editing or discards.
#     Returns: {"status": "rejected", "action": "edit" | "discard"}
#     """
#     pass

def approve_memory(proposal_id: str):
    session = SupabaseSessionLocal()

    proposal = session.execute(text("""
        SELECT * FROM memory_update_proposals
        WHERE id = :id
    """), {"id": proposal_id}).mappings().first()

    if not proposal:
        raise Exception("Proposal not found")

    records = proposal["proposed_content"]

    for r in records:
        session.execute(text("""
            INSERT INTO memory_entries (
                owner_id, sender_id, sender_name, sender_role,
                memory_type, content, summary, tags, importance
            )
            VALUES (
                :owner_id, :sender_id, :sender_name, :sender_role,
                :memory_type, :content, :summary, :tags, :importance
            )
        """), r)

    session.execute(text("""
        UPDATE memory_update_proposals
        SET status = 'approved'
        WHERE id = :id
    """), {"id": proposal_id})

    session.commit()