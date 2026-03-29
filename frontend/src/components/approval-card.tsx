"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

type ApprovalItem = {
  id: string;
  title: string;
  sender: string | null;
  preview: string | null;
  proposal_type: string | null;
  risk_level: string | null;
  status?: string | null;
  proposal_id?: string | null;
};

function badgeClass(risk: string) {
  if (risk === "high") return "bg-red-100 text-red-700";
  if (risk === "medium") return "bg-amber-100 text-amber-700";
  return "bg-emerald-100 text-emerald-700";
}

export default function ApprovalCard({ item }: { item: ApprovalItem }) {
  const router = useRouter();
  const [loading, setLoading] = useState(false);

  const proposalType = (item.proposal_type ?? "unknown").replace(/-/g, " ");
  const riskLevel = item.risk_level ?? "low";

  async function handleApprove() {
    try {
      setLoading(true);

      const targetId = item.proposal_id ?? item.id;

      const res = await fetch(`http://localhost:8000/memory/approve/${targetId}`, {
        method: "POST",
      });

      if (!res.ok) {
        throw new Error("Failed to approve proposal");
      }

      router.refresh();
    } catch (err) {
      console.error(err);
      alert("Failed to approve proposal");
    } finally {
      setLoading(false);
    }
  }

  async function handleReject() {
    try {
      setLoading(true);

      const targetId = item.proposal_id ?? item.id;

      const res = await fetch(`http://localhost:8000/memory/reject/${targetId}`, {
        method: "POST",
      });

      if (!res.ok) {
        throw new Error("Failed to reject proposal");
      }

      router.refresh();
    } catch (err) {
      console.error(err);
      alert("Failed to reject proposal");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="rounded-2xl border border-zinc-200 bg-white p-5 shadow-sm">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h3 className="text-base font-semibold text-zinc-900">{item.title}</h3>
          <p className="mt-1 text-sm text-zinc-500">
            From: {item.sender ?? "Memory Agent"}
          </p>
        </div>

        <div className="flex items-center gap-2">
          <span className="rounded-full bg-zinc-100 px-3 py-1 text-xs font-medium uppercase text-zinc-700">
            {proposalType}
          </span>
          <span
            className={`rounded-full px-3 py-1 text-xs font-medium ${badgeClass(riskLevel)}`}
          >
            {riskLevel}
          </span>
        </div>
      </div>

      <p className="mt-4 text-sm text-zinc-600">
        {item.preview ?? "No preview available."}
      </p>

      <div className="mt-4 flex gap-3">
        <button
          onClick={handleApprove}
          disabled={loading}
          className="rounded-xl bg-zinc-900 px-4 py-2 text-sm text-white disabled:opacity-50"
        >
          {loading ? "Working..." : "Approve"}
        </button>

        <button
          onClick={handleReject}
          disabled={loading}
          className="rounded-xl border border-zinc-300 px-4 py-2 text-sm text-zinc-700 disabled:opacity-50"
        >
          Reject
        </button>
      </div>
    </div>
  );
}