import { getAuthenticatedClient } from "@/lib/api";
import type { DailyDigestInput } from "@/lib/types";
import { NextResponse } from "next/server";

export async function PATCH(
  request: Request,
  { params }: { params: Promise<{ digestId: string }> }
) {
  const auth = await getAuthenticatedClient({ redirectOnFail: false });

  if (!auth) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const { digestId } = await params;
  const payload = (await request.json()) as DailyDigestInput;

  const { error } = await auth.supabase
    .from("daily_digest")
    .update({
      title: payload.title.trim(),
      summary: payload.summary.trim(),
      risk: payload.risk,
    })
    .eq("owner_id", auth.user.id)
    .eq("id", digestId);

  if (error) {
    return NextResponse.json({ error: error.message }, { status: 400 });
  }

  return NextResponse.json({ ok: true });
}
