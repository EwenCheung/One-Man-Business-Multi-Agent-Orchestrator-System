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

  const orderDate = new Date().toISOString().split("T")[0];
  const orderId = randomUUID();
  const { data: purchaseResult, error: purchaseError } = await admin.rpc("purchase_product_atomic", {
    p_owner_id: product.owner_id,
    p_customer_id: customerId,
    p_product_id: productId,
    p_quantity: quantity,
    p_order_id: orderId,
    p_order_date: orderDate,
    p_channel: "website",
  });

  if (purchaseError) {
    const message = purchaseError.message || "Failed to create order";
    if (message.includes("OUT_OF_STOCK_OR_PRODUCT_NOT_FOUND")) {
      return NextResponse.json({ error: "Out of stock" }, { status: 400 });
    }
    if (message.includes("CUSTOMER_NOT_FOUND")) {
      return NextResponse.json({ error: "Customer not found" }, { status: 404 });
    }
    if (message.includes("INVALID_QUANTITY")) {
      return NextResponse.json({ error: "Invalid purchase request" }, { status: 400 });
    }
    return NextResponse.json({ error: message }, { status: 500 });
  }

  return NextResponse.json({ success: true, orderId, purchase: purchaseResult });
}
