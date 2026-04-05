import { getAuthenticatedClient, getOwnerProfile, upsertOwnerProfile } from "@/lib/api";
import type { OwnerProfileInput } from "@/lib/types";
import { NextResponse } from "next/server";

export async function GET() {
  const auth = await getAuthenticatedClient({ redirectOnFail: false });

  if (!auth) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const profile = await getOwnerProfile();
  return NextResponse.json(profile);
}

export async function PATCH(request: Request) {
  const auth = await getAuthenticatedClient({ redirectOnFail: false });

  if (!auth) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const payload = (await request.json()) as OwnerProfileInput;
  const profile = await upsertOwnerProfile(payload);
  return NextResponse.json(profile);
}
