import { NextResponse } from "next/server";
import { getAuthenticatedClient } from "@/lib/api";
import { getBackendBaseUrl, getInternalBackendHeaders } from "@/lib/backend";
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
  const response = await fetch(`${getBackendBaseUrl()}/api/v1/orders/purchase`, {
    method: "POST",
    headers: getInternalBackendHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify({
      owner_id: product.owner_id,
      customer_id: customerId,
      product_id: productId,
      quantity,
      order_id: orderId,
      order_date: orderDate,
      channel: "website",
    }),
  });

  const payload = await response.json().catch(() => null);

  if (!response.ok) {
    const message = payload?.error || payload?.detail || "Failed to create order";
    if (message.includes("Out of stock")) {
      return NextResponse.json({ error: "Out of stock" }, { status: 400 });
    }
    if (message.includes("Customer not found")) {
      return NextResponse.json({ error: "Customer not found" }, { status: 404 });
    }
    if (message.includes("Invalid purchase request")) {
      return NextResponse.json({ error: "Invalid purchase request" }, { status: 400 });
    }
    return NextResponse.json({ error: message }, { status: 500 });
  }

  return NextResponse.json({ success: true, orderId, purchase: payload?.purchase ?? null });
}
