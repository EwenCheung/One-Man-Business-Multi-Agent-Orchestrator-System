"use client";

import PendingApprovalsSection from "@/components/owner-dashboard/sections/pending-approvals-section";
import { usePendingApprovals } from "@/hooks/use-pending-approvals";
import type { ApprovalItem } from "@/lib/types";

export default function PendingApprovalsClient({ initialData }: { initialData: ApprovalItem[] }) {
  const { data, isLoading, isError } = usePendingApprovals(initialData);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-semibold text-zinc-900">Pending Approvals</h1>
        <p className="mt-2 text-zinc-500">Review owner decisions that are ready now, and see clearly where backend support is still pending.</p>
      </div>

      {isLoading ? <p className="text-sm text-zinc-500">Refreshing approvals...</p> : null}
      {isError ? <p className="rounded-2xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">Failed to load pending approvals.</p> : null}

      <PendingApprovalsSection approvals={data} />
    </div>
  );
}
