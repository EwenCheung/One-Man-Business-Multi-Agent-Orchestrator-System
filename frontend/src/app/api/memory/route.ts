import { NextResponse } from "next/server";

const data = {
  long: [{ id: "m1", title: "Owner rules", content: "Only answer policy-safe." }],
  grep: [{ id: "m2", title: "Customer preference", content: "Discount preference" }],
  short: [{ id: "m3", title: "Recent chat", content: "Latest intent was supply query" }],
};

export async function GET(request: Request) {
  const url = new URL(request.url);
  const layer = url.searchParams.get("layer") || "long";
  return NextResponse.json(data[layer as keyof typeof data] || []);
}
