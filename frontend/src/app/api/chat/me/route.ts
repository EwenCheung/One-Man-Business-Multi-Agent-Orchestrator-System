import { getAuthenticatedClient } from "@/lib/api";
import { createAdminClient } from "@/lib/supabase/admin";
import { NextResponse } from "next/server";

const stakeholderTableByRole = {
  customer: "customers",
  supplier: "suppliers",
  partner: "partners",
  investor: "investors",
} as const;

export async function GET() {
  const auth = await getAuthenticatedClient({ redirectOnFail: false });

  if (!auth) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const role = auth.user.user_metadata?.role || "owner";
  const admin = createAdminClient();

  if (role === "owner") {
    return NextResponse.json({ error: "Owner uses owner chat endpoints" }, { status: 400 });
  }

  const table = stakeholderTableByRole[role as keyof typeof stakeholderTableByRole];
  if (!table) {
    return NextResponse.json({ error: "Unsupported chat role" }, { status: 403 });
  }

  const telegramUsername = auth.user.email?.endsWith("@telegram.local")
    ? auth.user.email.slice(0, -"@telegram.local".length)
    : null;
  const filters = [
    auth.user.email && !telegramUsername ? `email.eq.${auth.user.email}` : null,
    auth.user.phone ? `phone.eq.${auth.user.phone}` : null,
    telegramUsername ? `telegram_username.ilike.${telegramUsername}` : null,
  ].filter(Boolean);

  const { data: stakeholder, error: stakeholderError } = await admin
    .from(table)
    .select("id, owner_id, name, email, phone, telegram_username")
    .or(filters.join(","))
    .limit(1)
    .single();

  if (stakeholderError || !stakeholder) {
    return NextResponse.json({ error: "Stakeholder record not found" }, { status: 404 });
  }

  const senderExternalId =
    stakeholder.email || stakeholder.phone || stakeholder.telegram_username || auth.user.email || auth.user.id;

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
