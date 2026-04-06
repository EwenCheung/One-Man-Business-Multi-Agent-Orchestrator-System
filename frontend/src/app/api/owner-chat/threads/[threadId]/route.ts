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

type RouteContext = {
  params: Promise<{ threadId: string }>;
};

export async function DELETE(_request: NextRequest, context: RouteContext) {
  const auth = await getAuthenticatedClient({ redirectOnFail: false });

  if (!auth) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const { threadId } = await context.params;

  const backendUrl = `${getBackendBaseUrl()}/api/v1/owner-chat/threads/${threadId}`;

  const response = await fetch(backendUrl, {
    method: "DELETE",
    headers: {
      "Content-Type": "application/json",
    },
  });

  if (!response.ok) {
    const text = await response.text();
    return NextResponse.json(
      { error: text || "Failed to delete thread" },
      { status: response.status }
    );
  }

  const data = await response.json();
  return NextResponse.json(data);
}
