import { getDashboardPayload, getAuthenticatedClient } from "@/lib/api";
import { NextResponse } from "next/server";

export async function GET() {
  const auth = await getAuthenticatedClient({ redirectOnFail: false });

  if (!auth) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const payload = await getDashboardPayload();
  return NextResponse.json(payload);
}
