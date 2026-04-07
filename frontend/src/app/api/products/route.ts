import { getAuthenticatedClient, getProducts } from "@/lib/api";
import type { ProductInput } from "@/lib/types";
import { NextResponse } from "next/server";

export async function GET() {
  const auth = await getAuthenticatedClient({ redirectOnFail: false });

  if (!auth) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const products = await getProducts();
  return NextResponse.json(products);
}

export async function POST(request: Request) {
  const auth = await getAuthenticatedClient({ redirectOnFail: false });

  if (!auth) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const payload = (await request.json()) as ProductInput;

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
    .insert({
      id: crypto.randomUUID(),
      owner_id: auth.user.id,
      name: payload.name.trim(),
      description: payload.description ?? null,
      selling_price: payload.selling_price,
      cost_price: payload.cost_price,
      stock_number: payload.stock_number,
      product_link: payload.product_link ?? null,
      category: payload.category.trim(),
    })
    .select("id, name, description, selling_price, cost_price, stock_number, product_link, category, created_at, updated_at")
    .single();

  if (error) {
    return NextResponse.json({ error: error.message }, { status: 400 });
  }

  return NextResponse.json(data, { status: 201 });
}
