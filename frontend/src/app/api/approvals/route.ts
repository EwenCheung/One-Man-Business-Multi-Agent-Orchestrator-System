import { getAuthenticatedClient, getPendingApprovals } from "@/lib/api";
import { getBackendBaseUrl, getInternalBackendHeaders } from "@/lib/backend";
import { NextResponse } from "next/server";

type ApprovalListItem = {
  id: string;
  proposal_id?: string | null;
  held_reply_id?: string | null;
  proposal_type?: string | null;
};

type ApprovalAction = "approve" | "reject";

type ApprovalPayload = {
  id: string;
  held_reply_id?: string | null;
  proposal_id?: string | null;
  proposal_type?: string | null;
};

function getApprovalPath(action: ApprovalAction, item: ApprovalPayload) {
  const proposalType = (item.proposal_type ?? "").toLowerCase();
  const targetId = proposalType.includes("reply")
    ? item.held_reply_id
    : item.proposal_id ?? item.id;

  if (!targetId) {
    return null;
  }

  if (proposalType.includes("reply")) {
    return `/api/v1/replies/${action}/${targetId}`;
  }

  return `/api/v1/memory/${action}/${targetId}`;
}

export async function GET() {
  const auth = await getAuthenticatedClient({ redirectOnFail: false });

  if (!auth) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const approvals = await getPendingApprovals();
  return NextResponse.json(approvals satisfies ApprovalListItem[]);
}

export async function POST(request: Request) {
  const auth = await getAuthenticatedClient({ redirectOnFail: false });

  if (!auth) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const body = (await request.json()) as {
    action?: ApprovalAction;
    item?: ApprovalPayload;
  };

  if (!body.action || !body.item) {
    return NextResponse.json({ error: "Missing approval action payload" }, { status: 400 });
  }

  const path = getApprovalPath(body.action, body.item);

  if (!path) {
    return NextResponse.json({ error: "This approval action is blocked until the backend exposes a held reply id." }, { status: 409 });
  }

  const response = await fetch(`${getBackendBaseUrl()}${path}`, {
    method: "POST",
    headers: getInternalBackendHeaders({
      "Content-Type": "application/json",
    }),
    cache: "no-store",
  });

  const text = await response.text();

  if (!response.ok) {
    return NextResponse.json(
      {
        error: text || "Backend approval request failed",
      },
      { status: response.status }
    );
  }

  try {
    return NextResponse.json(JSON.parse(text));
  } catch {
    return NextResponse.json({ ok: true });
  }
}
