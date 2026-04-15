import { getAuthenticatedClient } from "@/lib/api";
import { resolveAuthenticatedStakeholder } from "@/lib/stakeholder-auth";
import { createAdminClient } from "@/lib/supabase/admin";
import { redirect } from "next/navigation";
import CustomerClient from "./customer-client";

type CustomerOrderRow = {
  id: string;
  quantity: number;
  total_price: number;
  order_date: string | null;
  status: string;
  products: { name: string } | { name: string }[] | null;
};

type CustomerProductRow = {
  id: string;
  name: string;
  description: string | null;
  selling_price: number;
  stock_number: number;
  category: string | null;
};

export default async function CustomerDashboardPage() {
  const auth = await getAuthenticatedClient();
  if (!auth) redirect("/login");

  const { user } = auth;
  const admin = createAdminClient();
  const resolved = await resolveAuthenticatedStakeholder(admin, user);
  if (!resolved || resolved.role !== "customer") {
    return <p className="p-8 text-red-600">Unauthorized. You are not a customer.</p>;
  }
  const customerData = resolved?.stakeholder ?? null;

  let orders: CustomerOrderRow[] = [];
  if (customerData) {
    const { data: ordersData } = await admin
      .from("orders")
      .select("id, quantity, total_price, order_date, status, products(name)")
      .eq("customer_id", customerData.id)
      .order("order_date", { ascending: false });
    orders = ordersData || [];
  }

  const { data: productsData } = await admin
    .from("products")
    .select("id, name, description, selling_price, stock_number, category")
    .eq("owner_id", customerData?.owner_id || "")
    .gt("stock_number", 0)
    .order("created_at", { ascending: false });

  const products: CustomerProductRow[] = productsData || [];

  return <CustomerClient customerId={customerData?.id} initialOrders={orders} products={products} />;
}
