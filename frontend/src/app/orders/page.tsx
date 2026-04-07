import { getOrders } from "@/lib/api";
import OrdersClient from "@/components/orders/orders-client";

export default async function OrdersPage() {
  const orders = await getOrders();

  return <OrdersClient initialData={orders} />;
}
