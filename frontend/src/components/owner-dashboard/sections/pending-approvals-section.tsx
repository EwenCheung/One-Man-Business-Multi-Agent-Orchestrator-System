"use client";

import ApprovalCard from "@/components/approval-card";
import SectionCard from "@/components/section-card";
import { getApprovalBlockReason, useApprovalMutations } from "@/hooks/use-pending-approvals";
import type { ApprovalItem } from "@/lib/types";

export default function PendingApprovalsSection({
  approvals,
  title = "Pending Approvals",
  description,
}: {
  approvals: ApprovalItem[];
  title?: string;
  description?: string;
}) {
  const { approve, reject, loadingId, loadingAction, isPending } = useApprovalMutations();

  return (
    <SectionCard title={title} description={description}>
      <div className="space-y-4">
        {approvals.length === 0 ? (
          <p className="text-sm text-zinc-500">No pending approvals right now.</p>
        ) : (
          approvals.map((item) => (
            <ApprovalCard
              key={item.id}
              item={item}
              blockedReason={getApprovalBlockReason(item)}
              onApprove={() => approve(item)}
              onReject={() => reject(item)}
              loading={isPending && loadingId === item.id ? loadingAction : null}
            />
          ))
        )}
      </div>
    </SectionCard>
  );
}
