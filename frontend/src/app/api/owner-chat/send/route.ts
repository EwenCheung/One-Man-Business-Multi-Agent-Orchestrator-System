import { getAuthenticatedClient } from "@/lib/api";
import { NextRequest, NextResponse } from "next/server";

function getBackendBaseUrl() {
  return (
    process.env.BACKEND_URL ??
    process.env.NEXT_PUBLIC_API_URL ??
    process.env.NEXT_PUBLIC_BACKEND_URL ??
    "http://localhost:8000"
  );
}

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

  // Use the authenticated user's Supabase ID as sender_id so that identity
  // resolution in the backend can verify ownership via UUID match — the client
  // must never supply sender_role directly.
  const payload = {
    raw_message: body.raw_message,
    sender_id: auth.user.id,
    sender_name: body.sender_name ?? auth.user.email ?? "Owner",
    thread_id: body.thread_id,
  };

  const response = await fetch(`${getBackendBaseUrl()}/api/v1/messages/incoming`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
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
