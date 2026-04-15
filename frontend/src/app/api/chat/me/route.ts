import { getAuthenticatedClient } from "@/lib/api";
import { createAdminClient } from "@/lib/supabase/admin";
import { resolveAuthenticatedStakeholder, stakeholderSenderExternalId } from "@/lib/stakeholder-auth";
import { NextResponse } from "next/server";

export async function GET() {
  const auth = await getAuthenticatedClient({ redirectOnFail: false });

  if (!auth) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const admin = createAdminClient();
  const resolved = await resolveAuthenticatedStakeholder(admin, auth.user);

  if (!resolved) {
    return NextResponse.json({ error: "Owner uses owner chat endpoints" }, { status: 400 });
  }
  const { stakeholder } = resolved;

  const senderExternalId = stakeholderSenderExternalId(stakeholder, auth.user);

  const { data: thread } = await admin
    .from("conversation_threads")
    .select("id, thread_type, title, last_message_at, sender_external_id, sender_name, sender_role, sender_channel")
    .eq("owner_id", stakeholder.owner_id)
    .eq("thread_type", "external_sender")
    .eq("sender_external_id", senderExternalId)
    .maybeSingle();

  if (!thread) {
    return NextResponse.json({ thread: null, messages: [], status: "success" });
  }

  const { data: messages } = await admin
    .from("messages")
    .select("id, direction, content, sender_id, sender_name, sender_role, created_at")
    .eq("owner_id", stakeholder.owner_id)
    .eq("conversation_thread_id", thread.id)
    .order("created_at", { ascending: true });

  return NextResponse.json({
    thread: {
      thread_id: thread.id,
      thread_type: thread.thread_type,
      title: thread.title,
      last_message_at: thread.last_message_at,
      sender: {
        external_id: thread.sender_external_id,
        name: thread.sender_name,
        role: thread.sender_role,
        channel: thread.sender_channel,
      },
    },
    messages: messages ?? [],
    status: "success",
  });
}
