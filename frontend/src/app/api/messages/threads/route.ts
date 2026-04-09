import { getAuthenticatedClient } from "@/lib/api";
import { getBackendBaseUrl } from "@/lib/backend";
import { NextRequest, NextResponse } from "next/server";

export async function GET(request: NextRequest) {
  const auth = await getAuthenticatedClient({ redirectOnFail: false });

  if (!auth) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const searchParams = request.nextUrl.searchParams;
  const senderRoles = searchParams.get("sender_roles");
  const limit = searchParams.get("limit") || "100";

  const queryString = new URLSearchParams();
  if (senderRoles) {
    queryString.set("sender_roles", senderRoles);
  }
  queryString.set("limit", limit);

  const backendUrl = `${getBackendBaseUrl()}/api/v1/messages/threads?${queryString.toString()}`;

  const response = await fetch(backendUrl, {
    method: "GET",
    headers: {
      "Content-Type": "application/json",
    },
    cache: "no-store",
  });

  if (!response.ok) {
    const text = await response.text();
    return NextResponse.json(
      { error: text || "Failed to fetch message threads" },
      { status: response.status }
    );
  }

  const data = await response.json();
  return NextResponse.json(data);
}
