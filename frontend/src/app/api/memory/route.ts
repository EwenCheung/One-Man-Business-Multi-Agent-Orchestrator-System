import { getAuthenticatedClient, getMemoryOverview } from "@/lib/api";
import { NextResponse } from "next/server";

export async function GET() {
  const auth = await getAuthenticatedClient({ redirectOnFail: false });

  if (!auth) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const memory = await getMemoryOverview();
  return NextResponse.json(memory);
}
