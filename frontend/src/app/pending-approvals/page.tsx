import PendingApprovalsClient from "@/components/pending-approvals/pending-approvals-client";
import { getPendingApprovals } from "@/lib/api";

export default async function PendingApprovalsPage() {
  const approvals = await getPendingApprovals();

  return <PendingApprovalsClient initialData={approvals} />;
}
