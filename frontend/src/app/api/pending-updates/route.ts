import { NextResponse } from "next/server";
import { getPendingApprovals } from "@/lib/api";

export async function GET() {
  try {
    const approvals = await getPendingApprovals();
    return NextResponse.json(approvals);
  } catch (error) {
    return new NextResponse("Internal Server Error", { status: 500 });
  }
}
