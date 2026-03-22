import { dailyDigest } from "@/lib/mock-data";
import { NextResponse } from "next/server";

export async function GET() {
  return NextResponse.json(dailyDigest);
}
