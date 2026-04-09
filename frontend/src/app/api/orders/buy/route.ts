import { NextResponse } from "next/server";
import { getAuthenticatedClient } from "@/lib/api";
import { createAdminClient } from "@/lib/supabase/admin";
import { randomUUID } from "crypto";

export async function POST(req: Request) {
  const auth = await getAuthenticatedClient();
  if (!auth) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  const { user } = auth;
  if (user.user_metadata?.role !== "customer") {
    return NextResponse.json({ error: "Only customers can buy" }, { status: 403 });
  }

  const admin = createAdminClient();

  const { productId, customerId, quantity } = await req.json();

  if (!productId || !customerId || !quantity || quantity < 1) {
    return NextResponse.json({ error: "Invalid purchase request" }, { status: 400 });
  }

  const { data: customer, error: customerError } = await admin
    .from("customers")
    .select("id, owner_id, email, phone, telegram_username")
    .eq("id", customerId)
    .single();

  if (customerError || !customer) {
    return NextResponse.json({ error: "Customer not found" }, { status: 404 });
  }

  const sessionEmail = user.email?.toLowerCase() || null;
  const sessionPhone = user.phone || null;
  const sessionTelegramUsername = sessionEmail?.endsWith("@telegram.local")
    ? sessionEmail.slice(0, -"@telegram.local".length)
    : null;

  const matchesCustomer =
    (sessionEmail && customer.email?.toLowerCase() === sessionEmail) ||
    (sessionPhone && customer.phone === sessionPhone) ||
    (sessionTelegramUsername && customer.telegram_username?.toLowerCase() === sessionTelegramUsername);

  if (!matchesCustomer) {
    return NextResponse.json({ error: "Customer mismatch" }, { status: 403 });
  }

  const { data: product, error: fetchError } = await admin
    .from("products")
    .select("selling_price, stock_number, owner_id")
    .eq("id", productId)
    .eq("owner_id", customer.owner_id)
    .single();

  if (fetchError || !product) {
    return NextResponse.json({ error: "Product not found" }, { status: 404 });
  }

  if (product.stock_number < quantity) {
    return NextResponse.json({ error: "Out of stock" }, { status: 400 });
  }

  const { error: updateError } = await admin
    .from("products")
    .update({ stock_number: product.stock_number - quantity })
    .eq("id", productId);

  if (updateError) {
    return NextResponse.json({ error: "Failed to update stock" }, { status: 500 });
  }

  const totalPrice = product.selling_price * quantity;
  const orderDate = new Date().toISOString().split("T")[0];
  const { error: insertError } = await admin
    .from("orders")
    .insert({
      id: randomUUID(),
      owner_id: product.owner_id,
      customer_id: customerId,
      product_id: productId,
      quantity,
      total_price: totalPrice,
      order_date: orderDate,
      status: "paid",
      channel: "website"
    });

  if (insertError) {
    return NextResponse.json({ error: insertError.message || "Failed to create order" }, { status: 500 });
  }

  return NextResponse.json({ success: true });
}
