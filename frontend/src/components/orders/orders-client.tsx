"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import DataTable from "@/components/data-table";
import SectionCard from "@/components/section-card";
import ActionOverlay from "@/components/action-overlay";
import { fetchOrder } from "@/lib/api-client";
import type { OrderRow, OrderDetail, TableColumn } from "@/lib/types";

function formatCurrency(value: number | null) {
  if (value === null || value === undefined) return "—";
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(value);
}

function formatDate(value: string | null) {
  if (!value) return "—";
  return new Date(value).toLocaleDateString();
}

function statusBadge(status: string | null) {
  const statusLower = (status ?? "").toLowerCase();
  if (statusLower === "completed") return "bg-emerald-100 text-emerald-700";
  if (statusLower === "pending") return "bg-amber-100 text-amber-700";
  if (statusLower === "cancelled") return "bg-red-100 text-red-700";
  return "bg-zinc-100 text-zinc-700";
}

export default function OrdersClient({ initialData }: { initialData: OrderRow[] }) {
  const router = useRouter();
  const [orders] = useState<OrderRow[]>(initialData);
  const [selectedOrder, setSelectedOrder] = useState<OrderDetail | null>(null);
  const [showDetailPanel, setShowDetailPanel] = useState(false);
  const [detailLoading, setDetailLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const columns: TableColumn<OrderRow>[] = [
    { key: "customer_name", label: "Customer" },
    { key: "product_name", label: "Product" },
    { key: "quantity", label: "Quantity" },
    { key: "total_price", label: "Total", render: (value) => formatCurrency(value as number | null) },
    { key: "order_date", label: "Order Date", render: (value) => formatDate(value as string | null) },
    {
      key: "status",
      label: "Status",
      render: (value) => (
        <span className={`rounded-full px-3 py-1 text-xs font-medium ${statusBadge(value as string | null)}`}>
          {(value as string | null) ?? "Unknown"}
        </span>
      ),
    },
    { key: "channel", label: "Channel" },
    {
      key: "actions",
      label: "Actions",
      render: (_, row) => (
        <button
          onClick={() => handleRowClick(row.id)}
          className="rounded-lg border border-zinc-300 px-3 py-1 text-xs font-medium text-zinc-700"
        >
          View Details
        </button>
      ),
    },
  ];

  async function handleRowClick(orderId: string) {
    setErrorMessage(null);
    setDetailLoading(true);
    setShowDetailPanel(true);

    try {
      const detail = await fetchOrder(orderId);
      setSelectedOrder(detail);
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Failed to load order details.");
    } finally {
      setDetailLoading(false);
    }
  }

  function handleMessageCustomer() {
    if (!selectedOrder?.message_thread_id) {
      setErrorMessage("No message thread available for this customer.");
      return;
    }

    router.push(`/messages?threadId=${selectedOrder.message_thread_id}`);
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-semibold text-zinc-900">Orders</h1>
        <p className="mt-2 text-zinc-500">View all customer orders with details, status, and linked conversations.</p>
      </div>

      {errorMessage ? <p className="rounded-2xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">{errorMessage}</p> : null}

      <SectionCard title="All Orders" description="Browse customer orders and view detailed information.">
        <DataTable columns={columns} data={orders} />
      </SectionCard>

      <ActionOverlay
        open={showDetailPanel && Boolean(selectedOrder)}
        title={selectedOrder ? `Order #${selectedOrder.id.slice(0, 8)}` : "Order Details"}
        description="Complete order information including customer and product details."
        onCloseAction={() => {
          setShowDetailPanel(false);
          setSelectedOrder(null);
          setErrorMessage(null);
        }}
      >
        {detailLoading ? (
          <p className="text-sm text-zinc-500">Loading order details...</p>
        ) : selectedOrder ? (
          <div className="space-y-6">
            <section className="rounded-2xl border border-zinc-200 bg-zinc-50 p-5">
              <h3 className="text-sm font-semibold uppercase tracking-[0.18em] text-zinc-500">Order Information</h3>
              <div className="mt-4 grid gap-3 text-sm">
                <div className="flex justify-between">
                  <span className="font-medium text-zinc-700">Order ID</span>
                  <span className="text-zinc-900">{selectedOrder.id}</span>
                </div>
                <div className="flex justify-between">
                  <span className="font-medium text-zinc-700">Quantity</span>
                  <span className="text-zinc-900">{selectedOrder.quantity}</span>
                </div>
                <div className="flex justify-between">
                  <span className="font-medium text-zinc-700">Total Price</span>
                  <span className="text-zinc-900">{formatCurrency(selectedOrder.total_price)}</span>
                </div>
                <div className="flex justify-between">
                  <span className="font-medium text-zinc-700">Order Date</span>
                  <span className="text-zinc-900">{formatDate(selectedOrder.order_date)}</span>
                </div>
                <div className="flex justify-between">
                  <span className="font-medium text-zinc-700">Status</span>
                  <span className={`rounded-full px-3 py-1 text-xs font-medium ${statusBadge(selectedOrder.status)}`}>
                    {selectedOrder.status ?? "Unknown"}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="font-medium text-zinc-700">Channel</span>
                  <span className="text-zinc-900">{selectedOrder.channel ?? "—"}</span>
                </div>
              </div>
            </section>

            <section className="rounded-2xl border border-zinc-200 bg-zinc-50 p-5">
              <h3 className="text-sm font-semibold uppercase tracking-[0.18em] text-zinc-500">Customer Information</h3>
              <div className="mt-4 grid gap-3 text-sm">
                <div className="flex justify-between">
                  <span className="font-medium text-zinc-700">Name</span>
                  <span className="text-zinc-900">{selectedOrder.customer_name ?? "—"}</span>
                </div>
                <div className="flex justify-between">
                  <span className="font-medium text-zinc-700">Email</span>
                  <span className="text-zinc-900">{selectedOrder.customer_email ?? "—"}</span>
                </div>
                <div className="flex justify-between">
                  <span className="font-medium text-zinc-700">Phone</span>
                  <span className="text-zinc-900">{selectedOrder.customer_phone ?? "—"}</span>
                </div>
                <div className="flex justify-between">
                  <span className="font-medium text-zinc-700">Company</span>
                  <span className="text-zinc-900">{selectedOrder.customer_company ?? "—"}</span>
                </div>
                {selectedOrder.customer_preference ? (
                  <div className="flex justify-between">
                    <span className="font-medium text-zinc-700">Preference</span>
                    <span className="text-zinc-900">{selectedOrder.customer_preference}</span>
                  </div>
                ) : null}
                {selectedOrder.customer_notes ? (
                  <div className="mt-2">
                    <p className="font-medium text-zinc-700">Notes</p>
                    <p className="mt-1 text-zinc-900">{selectedOrder.customer_notes}</p>
                  </div>
                ) : null}
              </div>
            </section>

            <section className="rounded-2xl border border-zinc-200 bg-zinc-50 p-5">
              <h3 className="text-sm font-semibold uppercase tracking-[0.18em] text-zinc-500">Product Information</h3>
              <div className="mt-4 grid gap-3 text-sm">
                <div className="flex justify-between">
                  <span className="font-medium text-zinc-700">Name</span>
                  <span className="text-zinc-900">{selectedOrder.product_name ?? "—"}</span>
                </div>
                {selectedOrder.product_description ? (
                  <div className="mt-2">
                    <p className="font-medium text-zinc-700">Description</p>
                    <p className="mt-1 text-zinc-900">{selectedOrder.product_description}</p>
                  </div>
                ) : null}
                <div className="flex justify-between">
                  <span className="font-medium text-zinc-700">Category</span>
                  <span className="text-zinc-900">{selectedOrder.product_category ?? "—"}</span>
                </div>
                <div className="flex justify-between">
                  <span className="font-medium text-zinc-700">Selling Price</span>
                  <span className="text-zinc-900">{formatCurrency(selectedOrder.selling_price)}</span>
                </div>
                <div className="flex justify-between">
                  <span className="font-medium text-zinc-700">Cost Price</span>
                  <span className="text-zinc-900">{formatCurrency(selectedOrder.cost_price)}</span>
                </div>
                <div className="flex justify-between">
                  <span className="font-medium text-zinc-700">Stock Available</span>
                  <span className="text-zinc-900">{selectedOrder.stock_number ?? 0}</span>
                </div>
                {selectedOrder.product_link ? (
                  <div className="flex justify-between">
                    <span className="font-medium text-zinc-700">Product Link</span>
                    <a
                      href={selectedOrder.product_link}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-sky-600 hover:underline"
                    >
                      View Product
                    </a>
                  </div>
                ) : null}
              </div>
            </section>

            <div className="flex flex-wrap gap-3">
              <button
                type="button"
                onClick={handleMessageCustomer}
                disabled={!selectedOrder.message_thread_id}
                className="rounded-xl bg-zinc-900 px-4 py-3 text-sm font-medium text-white disabled:opacity-50"
              >
                Message Customer
              </button>
              <button
                type="button"
                onClick={() => {
                  setShowDetailPanel(false);
                  setSelectedOrder(null);
                  setErrorMessage(null);
                }}
                className="rounded-xl border border-zinc-300 px-4 py-3 text-sm font-medium text-zinc-700"
              >
                Close
              </button>
            </div>
          </div>
        ) : null}
      </ActionOverlay>
    </div>
  );
}
