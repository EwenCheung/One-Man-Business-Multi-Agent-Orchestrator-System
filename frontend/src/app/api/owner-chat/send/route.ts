import { getAuthenticatedClient } from "@/lib/api";
import { getBackendBaseUrl, getInternalBackendHeaders } from "@/lib/backend";
import { resolveAuthenticatedStakeholder, stakeholderSenderExternalId } from "@/lib/stakeholder-auth";
import { createAdminClient } from "@/lib/supabase/admin";
import { NextRequest, NextResponse } from "next/server";

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

  const admin = createAdminClient();
  const { data: ownerProfile } = await admin
    .from("profiles")
    .select("id")
    .eq("id", auth.user.id)
    .maybeSingle();

  const payload: Record<string, string | undefined> = {
    raw_message: body.raw_message,
    thread_id: body.thread_id,
  };

  if (ownerProfile?.id) {
    payload.owner_id = auth.user.id;
    payload.sender_id = auth.user.id;
    payload.sender_name = body.sender_name ?? auth.user.email ?? "Owner";
  } else {
    const resolved = await resolveAuthenticatedStakeholder(admin, auth.user);

    if (!resolved) {
      return NextResponse.json({ error: "Stakeholder record not found" }, { status: 404 });
    }
    const { stakeholder, role } = resolved;

    payload.owner_id = stakeholder.owner_id;
    payload.sender_id = stakeholderSenderExternalId(stakeholder, auth.user);
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
