import { getAuthenticatedClient, getOrders } from "@/lib/api";
import { NextResponse } from "next/server";

export async function GET() {
  const auth = await getAuthenticatedClient({ redirectOnFail: false });

  if (!auth) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const orders = await getOrders();
  return NextResponse.json(orders);
}
