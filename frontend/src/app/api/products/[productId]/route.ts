import { getAuthenticatedClient } from "@/lib/api";
import type { ProductInput } from "@/lib/types";
import { NextResponse } from "next/server";

export async function PATCH(
  request: Request,
  { params }: { params: Promise<{ productId: string }> }
) {
  const auth = await getAuthenticatedClient({ redirectOnFail: false });

  if (!auth) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const payload = (await request.json()) as ProductInput;
  const { productId } = await params;

  if (!payload.name?.trim()) {
    return NextResponse.json({ error: "Product name is required." }, { status: 400 });
  }

  if (!payload.category?.trim()) {
    return NextResponse.json({ error: "Product category is required." }, { status: 400 });
  }

  if (payload.selling_price === null || payload.selling_price === undefined || payload.selling_price <= 0) {
    return NextResponse.json({ error: "Selling price must be greater than 0." }, { status: 400 });
  }

  if (payload.cost_price === null || payload.cost_price === undefined || payload.cost_price < 0) {
    return NextResponse.json({ error: "Cost price must be 0 or greater." }, { status: 400 });
  }

  if (payload.stock_number === null || payload.stock_number === undefined || payload.stock_number < 0) {
    return NextResponse.json({ error: "Stock number must be 0 or greater." }, { status: 400 });
  }

  const { data, error } = await auth.supabase
    .from("products")
    .update({
      name: payload.name?.trim(),
      description: payload.description ?? null,
      selling_price: payload.selling_price,
      cost_price: payload.cost_price,
      stock_number: payload.stock_number,
      product_link: payload.product_link ?? null,
      category: payload.category.trim(),
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

export async function DELETE(
  request: Request,
  { params }: { params: Promise<{ productId: string }> }
) {
  void request;
  const auth = await getAuthenticatedClient({ redirectOnFail: false });

  if (!auth) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const { productId } = await params;
  const { error } = await auth.supabase
    .from("products")
    .delete()
    .eq("owner_id", auth.user.id)
    .eq("id", productId);

  if (error) {
    return NextResponse.json({ error: error.message }, { status: 400 });
  }

  return NextResponse.json({ ok: true });
}
