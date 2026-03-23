import { pendingApprovals } from "@/lib/mock-data";
import { NextResponse } from "next/server";

export async function GET() {
  return NextResponse.json(pendingApprovals);
}

export async function POST(request: Request) {
  const { id, action } = await request.json();
  const index = pendingApprovals.findIndex((item) => item.id === id);
  if (index === -1) {
    return new NextResponse("Not found", { status: 404 });
  }
  pendingApprovals[index].status = action === "approve" ? "approved" : "rejected";
  return NextResponse.json(pendingApprovals[index]);
}
