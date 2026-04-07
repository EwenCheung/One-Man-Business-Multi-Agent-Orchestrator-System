"use client";

import SectionCard from "@/components/section-card";
import { useDailyDigest } from "@/hooks/use-daily-digest";
import type { DailyDigestItem } from "@/lib/types";

function riskBadge(risk: string | null) {
  if (risk === "high") return "bg-red-100 text-red-700";
  if (risk === "medium") return "bg-amber-100 text-amber-700";
  return "bg-emerald-100 text-emerald-700";
}

export default function DailyDigestSection({
  initialData,
  title = "Daily Digest",
  compact = false,
}: {
  initialData: DailyDigestItem[];
  title?: string;
  compact?: boolean;
}) {
  const { data, isLoading, isError } = useDailyDigest(initialData);
  const items = compact ? data.slice(0, 5) : data;

  return (
    <SectionCard title={title} description="Recent summaries and system signals.">
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
