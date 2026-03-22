import { PendingApproval } from "@/lib/types";

function badgeClass(riskLevel: PendingApproval["riskLevel"]) {
  if (riskLevel === "high") return "bg-red-100 text-red-700";
  if (riskLevel === "medium") return "bg-amber-100 text-amber-700";
  return "bg-emerald-100 text-emerald-700";
}

export default function ApprovalCard({ item }: { item: PendingApproval }) {
  return (
    <div className="rounded-2xl border border-zinc-200 bg-white p-5 shadow-sm">
      <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <span className="rounded-full bg-zinc-100 px-3 py-1 text-xs font-medium uppercase text-zinc-700">
              {item.role}
            </span>
            <span className="rounded-full bg-zinc-100 px-3 py-1 text-xs font-medium uppercase text-zinc-700">
              {item.proposalType.replace("_", " ")}
            </span>
            <span
              className={`rounded-full px-3 py-1 text-xs font-medium ${badgeClass(item.riskLevel)}`}
            >
              {item.riskLevel} risk
            </span>
          </div>

          <h3 className="mt-3 text-lg font-semibold text-zinc-900">
            Proposal for {item.userId}
          </h3>
          <p className="mt-2 text-sm text-zinc-600">{item.reason}</p>
        </div>

        <div className="rounded-full bg-zinc-100 px-3 py-1 text-xs font-medium text-zinc-700">
          {item.status}
        </div>
      </div>

      <div className="mt-5 grid gap-4 md:grid-cols-2">
        <div className="rounded-xl bg-zinc-50 p-4">
          <p className="text-xs font-medium uppercase tracking-wide text-zinc-500">
            Old value
          </p>
          <p className="mt-2 text-sm text-zinc-800">{item.oldValue}</p>
        </div>
        <div className="rounded-xl bg-zinc-50 p-4">
          <p className="text-xs font-medium uppercase tracking-wide text-zinc-500">
            Proposed value
          </p>
          <p className="mt-2 text-sm text-zinc-800">{item.newValue}</p>
        </div>
      </div>

      <div className="mt-5 flex gap-3">
        <button className="rounded-xl bg-zinc-900 px-4 py-2 text-sm font-medium text-white transition hover:bg-zinc-700">
          Approve
        </button>
        <button className="rounded-xl border border-zinc-300 bg-white px-4 py-2 text-sm font-medium text-zinc-700 transition hover:bg-zinc-50">
          Reject
        </button>
      </div>
    </div>
  );
}