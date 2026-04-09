"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

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

export default function CustomerClient({ customerId, initialOrders, products }: { customerId?: string, initialOrders: CustomerOrderRow[], products: CustomerProductRow[] }) {
  const router = useRouter();
  const [activeTab, setActiveTab] = useState("orders");
  const [buying, setBuying] = useState<string | null>(null);

  async function handleBuy(productId: string, productName: string) {
    if (!customerId) return alert("Customer record not found.");
    const confirmed = window.confirm(`Confirm purchase for ${productName}? This will place the order and deduct stock immediately.`);
    if (!confirmed) return;
    setBuying(productId);
    
    try {
      const res = await fetch("/api/orders/buy", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ productId, customerId, quantity: 1 })
      });
      const payload = await res.json().catch(() => null);
      if (!res.ok) throw new Error(payload?.error || "Purchase failed");
      alert("Purchase successful! Your order has been placed.");
      router.refresh();
      setActiveTab("orders");
    } catch (err) {
      alert(err instanceof Error ? err.message : "Purchase failed");
    } finally {
      setBuying(null);
    }
  }

  return (
    <div className="space-y-6 max-w-5xl mx-auto py-8 px-4">
      <div>
        <h1 className="text-3xl font-semibold text-zinc-900">Customer Dashboard</h1>
        <p className="mt-2 text-zinc-500">Manage your orders and browse the store.</p>
      </div>

      <div className="border-b border-zinc-200">
        <nav className="-mb-px flex space-x-8">
          <button
            onClick={() => setActiveTab("orders")}
            className={`whitespace-nowrap border-b-2 py-4 px-1 text-sm font-medium ${
              activeTab === "orders" ? "border-zinc-900 text-zinc-900" : "border-transparent text-zinc-500 hover:border-zinc-300 hover:text-zinc-700"
            }`}
          >
            My Orders
          </button>
          <button
            onClick={() => setActiveTab("store")}
            className={`whitespace-nowrap border-b-2 py-4 px-1 text-sm font-medium ${
              activeTab === "store" ? "border-zinc-900 text-zinc-900" : "border-transparent text-zinc-500 hover:border-zinc-300 hover:text-zinc-700"
            }`}
          >
            Store Catalog
          </button>
        </nav>
      </div>

      {activeTab === "orders" && (
        <div className="overflow-hidden rounded-2xl border border-zinc-200 bg-white">
          <table className="w-full text-left text-sm text-zinc-600">
            <thead className="bg-zinc-50 font-medium text-zinc-900">
              <tr>
                <th className="px-6 py-4">Product Name</th>
                <th className="px-6 py-4">Quantity</th>
                <th className="px-6 py-4">Total Price</th>
                <th className="px-6 py-4">Status</th>
                <th className="px-6 py-4">Date</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-100">
              {initialOrders.map((o, i) => {
                const product = Array.isArray(o.products) ? o.products[0] : o.products;
                return (
                  <tr key={i} className="hover:bg-zinc-50/50">
                    <td className="px-6 py-4 font-medium text-zinc-900">{product?.name || "Unknown"}</td>
                    <td className="px-6 py-4">{o.quantity}</td>
                    <td className="px-6 py-4">${o.total_price}</td>
                    <td className="px-6 py-4">
                      <span className="inline-flex items-center rounded-full bg-blue-50 px-2 py-1 text-xs font-medium text-blue-700 ring-1 ring-inset ring-blue-600/20">
                        {o.status}
                      </span>
                    </td>
                    <td className="px-6 py-4">{o.order_date?.split("T")[0]}</td>
                  </tr>
                )
              })}
              {initialOrders.length === 0 && (
                <tr>
                  <td colSpan={5} className="px-6 py-8 text-center text-zinc-500">No orders placed yet.</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      {activeTab === "store" && (
        <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
          {products.map((p, i) => (
            <div key={i} className="rounded-2xl border border-zinc-200 bg-white p-6 flex flex-col">
              <h3 className="text-lg font-medium text-zinc-900">{p.name}</h3>
              <p className="mt-1 text-sm text-zinc-500 flex-grow">{p.description}</p>
              <div className="mt-4 flex items-center justify-between">
                <div>
                  <span className="text-lg font-bold text-zinc-900">${p.selling_price}</span>
                  <span className="ml-2 text-xs text-zinc-500">{p.stock_number} in stock</span>
                </div>
                <button 
                  onClick={() => handleBuy(p.id, p.name)}
                  disabled={buying === p.id}
                  className="rounded-lg bg-zinc-900 px-3 py-1.5 text-sm font-medium text-white hover:bg-zinc-800 disabled:opacity-50"
                >
                  {buying === p.id ? "Buying..." : "Buy"}
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
