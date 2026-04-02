import { getAuthenticatedClient } from "@/lib/api";
import { NextResponse } from "next/server";

export async function POST(
  request: Request,
  { params }: { params: Promise<{ productId: string }> }
) {
  const auth = await getAuthenticatedClient({ redirectOnFail: false });

  if (!auth) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const { delta } = (await request.json()) as { delta?: number; reason?: string };
  const { productId } = await params;

  if (typeof delta !== "number" || Number.isNaN(delta) || delta === 0) {
    return NextResponse.json({ error: "A non-zero stock delta is required." }, { status: 400 });
  }

  const { data: current, error: currentError } = await auth.supabase
    .from("products")
    .select("id, stock_number")
    .eq("owner_id", auth.user.id)
    .eq("id", productId)
    .single();

  if (currentError || !current) {
    return NextResponse.json({ error: currentError?.message ?? "Product not found." }, { status: 404 });
  }

  const nextStock = (current.stock_number ?? 0) + delta;

  if (nextStock < 0) {
    return NextResponse.json({ error: "Stock cannot drop below zero." }, { status: 400 });
  }

  const { data, error } = await auth.supabase
    .from("products")
    .update({
      stock_number: nextStock,
      updated_at: new Date().toISOString(),
    })
    .eq("owner_id", auth.user.id)
    .eq("id", productId)
    .select("id, name, description, selling_price, cost_price, stock_number, product_link, category, created_at, updated_at")
    .single();

  if (error) {
    return NextResponse.json({ error: error.message }, { status: 400 });
  }

  return NextResponse.json(data);
}
