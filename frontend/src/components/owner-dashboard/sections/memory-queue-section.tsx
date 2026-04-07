"use client";

import SectionCard from "@/components/section-card";
import { useApprovalMutations } from "@/hooks/use-pending-approvals";
import type { ApprovalItem } from "@/lib/types";

export default function MemoryQueueSection({ items }: { items: ApprovalItem[] }) {
  const { approve, reject, loadingId, loadingAction, isPending } = useApprovalMutations();

  return (
    <SectionCard title="Memory Queue" description="Owner review for memory updates waiting to be applied.">
      <div className="space-y-3">
        {items.length === 0 ? (
          <p className="text-sm text-zinc-500">No memory updates are waiting for review.</p>
        ) : (
          items.map((item) => (
            <article key={item.id} className="rounded-2xl border border-zinc-200 p-4">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <h3 className="font-medium text-zinc-900">{item.title}</h3>
                  <p className="mt-2 text-sm leading-6 text-zinc-600">{item.preview ?? "No preview available."}</p>
                </div>
                <span className="rounded-full bg-zinc-100 px-3 py-1 text-xs font-medium text-zinc-700">
                  {item.risk_level ?? "low"}
                </span>
              </div>

              <div className="mt-4 flex flex-wrap gap-3">
                <button
                  onClick={() => approve(item)}
                  disabled={isPending && loadingId === item.id}
                  className="rounded-xl bg-zinc-900 px-4 py-2 text-sm text-white disabled:opacity-50"
                >
                  {isPending && loadingId === item.id && loadingAction === "approve" ? "Approving..." : "Approve update"}
                </button>
                <button
                  onClick={() => reject(item)}
                  disabled={isPending && loadingId === item.id}
                  className="rounded-xl border border-zinc-300 px-4 py-2 text-sm text-zinc-700 disabled:opacity-50"
                >
                  {isPending && loadingId === item.id && loadingAction === "reject" ? "Rejecting..." : "Reject update"}
                </button>
              </div>
            </article>
          ))
        )}
      </div>
    </SectionCard>
  );
}
