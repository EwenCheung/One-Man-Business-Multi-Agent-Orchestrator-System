"use client";

import SectionCard from "@/components/section-card";
import { useDailyDigest } from "@/hooks/use-daily-digest";
import type { DailyDigestPayload } from "@/lib/types";

function riskBadge(risk: string | null) {
  if (risk === "high") return "bg-red-100 text-red-700";
  if (risk === "medium") return "bg-amber-100 text-amber-700";
  return "bg-emerald-100 text-emerald-700";
}

export default function DailyDigestSection({
  initialData,
  title = "Statistics & Daily Digest",
  compact = false,
}: {
  initialData: DailyDigestPayload;
  title?: string;
  compact?: boolean;
}) {
  const { data, isLoading, isError } = useDailyDigest(initialData);
  const items = compact ? data.items.slice(0, 5) : data.items;

  return (
    <SectionCard title={title} description="Monthly sales statistics and recent system signals.">
      <div className="mb-6 grid grid-cols-2 gap-4 xl:grid-cols-4">
        <div className="rounded-xl border border-zinc-200 bg-zinc-50 p-4">
          <p className="text-xs font-medium text-zinc-500 uppercase tracking-wider">Contacts Today</p>
          <p className="mt-1 text-2xl font-bold text-zinc-900">{data.metrics.contactsToday}</p>
          <p className="text-xs text-zinc-500 mt-1">People the agent replied to today.</p>
        </div>
        <div className="rounded-xl border border-zinc-200 bg-zinc-50 p-4">
          <p className="text-xs font-medium text-zinc-500 uppercase tracking-wider">New Orders Today</p>
          <p className="mt-1 text-2xl font-bold text-zinc-900">{data.metrics.newOrdersToday}</p>
          <p className="text-xs text-zinc-500 mt-1">Counted using order_date.</p>
        </div>
        <div className="rounded-xl border border-zinc-200 bg-zinc-50 p-4">
          <p className="text-xs font-medium text-zinc-500 uppercase tracking-wider">Paid Sales Today</p>
          <p className="mt-1 text-2xl font-bold text-zinc-900">${data.metrics.paidSalesToday.toFixed(2)}</p>
          <p className="text-xs text-zinc-500 mt-1">Sum of today&apos;s paid orders.</p>
        </div>
        <div className="rounded-xl border border-zinc-200 bg-zinc-50 p-4">
          <p className="text-xs font-medium text-zinc-500 uppercase tracking-wider">Memory Updates Today</p>
          <p className="mt-1 text-2xl font-bold text-zinc-900">{data.metrics.memoryUpdatesToday}</p>
          <p className="text-xs text-zinc-500 mt-1">Saved memory + proposals created today.</p>
        </div>
      </div>

      <div className="mb-6 grid gap-6 xl:grid-cols-[1.25fr_1fr]">
        <div>
          <h4 className="font-medium text-zinc-900 mb-3 text-sm">Monthly Orders & Sales</h4>
          <div className="space-y-2">
            {data.monthly.map((month) => (
              <div key={month.month} className="rounded-2xl border border-zinc-200 bg-white px-4 py-3 text-sm">
                <div className="flex items-center justify-between gap-4">
                  <span className="font-medium text-zinc-900">{month.month}</span>
                  <div className="flex gap-6 text-zinc-600">
                    <span>Orders: <span className="font-medium text-zinc-900">{month.orders}</span></span>
                    <span>Sales: <span className="font-medium text-zinc-900">${month.paidSales.toFixed(2)}</span></span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>

        <div>
          <h4 className="font-medium text-zinc-900 mb-3 text-sm">Today&apos;s Activity</h4>
          <div className="space-y-2">
            {data.activities.length === 0 ? (
              <p className="rounded-2xl border border-zinc-200 bg-white px-4 py-3 text-sm text-zinc-500">No owner-visible activity recorded yet today.</p>
            ) : (
              data.activities.map((activity) => (
                <div key={`${activity.title}-${activity.detail}`} className="rounded-2xl border border-zinc-200 bg-white px-4 py-3 text-sm">
                  <p className="font-medium text-zinc-900">{activity.title}</p>
                  <p className="mt-1 text-zinc-600">{activity.detail}</p>
                </div>
              ))
            )}
          </div>
        </div>
      </div>

      <h4 className="font-medium text-zinc-900 mb-3 text-sm">Recent Daily Digests</h4>

      {isLoading ? <p className="text-sm text-zinc-500">Loading digest...</p> : null}
      {isError ? <p className="text-sm text-red-600">Failed to load the daily digest.</p> : null}

      {!isLoading && !isError ? (
        <div className="space-y-3">
          {items.length === 0 ? (
            <p className="text-sm text-zinc-500">No digest entries are available yet.</p>
          ) : (
            items.map((item) => (
              <article key={item.id} className="rounded-2xl border border-zinc-200 p-4">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <h3 className="font-medium text-zinc-900">{item.title}</h3>
                    <p className="mt-2 text-sm leading-6 text-zinc-600">{item.summary ?? "No summary available."}</p>
                  </div>
                  <span className={`rounded-full px-3 py-1 text-xs font-medium ${riskBadge(item.risk)}`}>
                    {item.risk ?? "low"}
                  </span>
                </div>
              </article>
            ))
          )}
        </div>
      ) : null}
    </SectionCard>
  );
}
