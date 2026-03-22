import ApprovalCard from "@/components/approval-card";
import { getPendingApprovals } from "@/lib/api";

export default async function PendingApprovalsPage() {
  const approvals = await getPendingApprovals();

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-semibold text-zinc-900">
          Pending Approvals
        </h1>
        <p className="mt-2 text-zinc-500">
          Review proposed updates before writing to memory or database.
        </p>
      </div>

      <div className="space-y-4">
        {approvals.map((item) => (
          <ApprovalCard key={item.id} item={item} />
        ))}
      </div>
    </div>
  );
}