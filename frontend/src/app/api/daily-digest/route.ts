import { getAuthenticatedClient, getDailyDigestPayload } from "@/lib/api";
import type { DailyDigestInput } from "@/lib/types";
import { NextResponse } from "next/server";

export async function GET() {
  const auth = await getAuthenticatedClient({ redirectOnFail: false });

  if (!auth) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const digest = await getDailyDigestPayload();
  return NextResponse.json(digest);
}

export async function POST(request: Request) {
  const auth = await getAuthenticatedClient({ redirectOnFail: false });

  if (!auth) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const payload = (await request.json()) as DailyDigestInput;

  if (!payload.title?.trim() || !payload.summary?.trim()) {
    return NextResponse.json({ error: "Title and summary are required." }, { status: 400 });
  }

  const { error } = await auth.supabase.from("daily_digest").insert({
    id: crypto.randomUUID(),
    owner_id: auth.user.id,
    title: payload.title.trim(),
    summary: payload.summary.trim(),
    risk: payload.risk || "low",
  });

  if (error) {
    return NextResponse.json({ error: error.message }, { status: 400 });
  }

  return NextResponse.json({ ok: true }, { status: 201 });
}
