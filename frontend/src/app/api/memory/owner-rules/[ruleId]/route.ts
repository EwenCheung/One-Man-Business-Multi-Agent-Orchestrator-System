import { getAuthenticatedClient } from "@/lib/api";
import { NextResponse } from "next/server";

export async function PATCH(
  request: Request,
  { params }: { params: Promise<{ ruleId: string }> }
) {
  const auth = await getAuthenticatedClient({ redirectOnFail: false });

  if (!auth) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const { ruleId } = await params;
  const { content } = (await request.json()) as { content?: string };

  if (!content?.trim()) {
    return NextResponse.json({ error: "Content is required." }, { status: 400 });
  }

  const { error } = await auth.supabase
    .from("owner_memory_rules")
    .update({
      content: content.trim(),
      updated_at: new Date().toISOString(),
    })
    .eq("owner_id", auth.user.id)
    .eq("id", ruleId);

  if (error) {
    return NextResponse.json({ error: error.message }, { status: 400 });
  }

  return NextResponse.json({ ok: true });
}
