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

export async function GET(request: NextRequest) {
  const auth = await getAuthenticatedClient({ redirectOnFail: false });

  if (!auth) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const searchParams = request.nextUrl.searchParams;
  const limit = searchParams.get("limit") || "100";
  const ownerId = auth.user.id;
  const backendUrl = `${getBackendBaseUrl()}/api/v1/owner-chat/threads?limit=${limit}&owner_id=${ownerId}`;

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
      { error: text || "Failed to fetch owner chat threads" },
      { status: response.status }
    );
  }

  const data = await response.json();
  return NextResponse.json(data);
}
