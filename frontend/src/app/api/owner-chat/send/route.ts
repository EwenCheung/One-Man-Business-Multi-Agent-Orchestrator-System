import { getAuthenticatedClient } from "@/lib/api";
import { getBackendBaseUrl, getInternalBackendHeaders } from "@/lib/backend";
import { createAdminClient } from "@/lib/supabase/admin";
import { NextRequest, NextResponse } from "next/server";

const stakeholderTableByRole = {
  customer: "customers",
  supplier: "suppliers",
  partner: "partners",
  investor: "investors",
} as const;

export async function POST(request: NextRequest) {
  const auth = await getAuthenticatedClient({ redirectOnFail: false });

  if (!auth) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const body = (await request.json()) as {
    raw_message?: string;
    thread_id?: string;
    sender_name?: string;
  };

  if (!body.raw_message?.trim()) {
    return NextResponse.json({ error: "raw_message is required" }, { status: 400 });
  }

  const role = auth.user.user_metadata?.role || "owner";
  const payload: Record<string, string | undefined> = {
    raw_message: body.raw_message,
    thread_id: body.thread_id,
  };

  if (role === "owner") {
    payload.owner_id = auth.user.id;
    payload.sender_id = auth.user.id;
    payload.sender_name = body.sender_name ?? auth.user.email ?? "Owner";
  } else {
    const admin = createAdminClient();
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

    const { data: stakeholder, error } = await admin
      .from(table)
      .select("id, owner_id, name, email, phone, telegram_username")
      .or(filters.join(","))
      .limit(1)
      .single();

    if (error || !stakeholder) {
      return NextResponse.json({ error: "Stakeholder record not found" }, { status: 404 });
    }

    payload.owner_id = stakeholder.owner_id;
    payload.sender_id =
      stakeholder.email || stakeholder.phone || stakeholder.telegram_username || auth.user.email || auth.user.id;
    payload.sender_name = body.sender_name ?? stakeholder.name ?? auth.user.email ?? role;
  }

  const response = await fetch(`${getBackendBaseUrl()}/api/v1/messages/incoming`, {
    method: "POST",
    headers: getInternalBackendHeaders({
      "Content-Type": "application/json",
    }),
    body: JSON.stringify(payload),
    cache: "no-store",
  });

  const text = await response.text();

  if (!response.ok) {
    return NextResponse.json(
      { error: text || "Backend request failed" },
      { status: response.status }
    );
  }

  try {
    return NextResponse.json(JSON.parse(text));
  } catch {
    return NextResponse.json({ error: "Failed to parse backend response as JSON" }, { status: 502 });
  }
}
