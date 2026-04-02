"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import type { ApprovalItem } from "@/lib/types";

function badgeClass(risk: string) {
  if (risk === "high") return "bg-red-100 text-red-700";
  if (risk === "medium") return "bg-amber-100 text-amber-700";
  return "bg-emerald-100 text-emerald-700";
}

export default function ApprovalCard({
  item,
  onApprove,
  onReject,
  blockedReason,
  loading,
}: {
  item: ApprovalItem;
  onApprove?: () => Promise<void>;
  onReject?: () => Promise<void>;
  blockedReason?: string | null;
  loading?: "approve" | "reject" | null;
}) {
  const router = useRouter();
  const [submitting, setSubmitting] = useState(false);

  const proposalType = (item.proposal_type ?? "unknown").replace(/-/g, " ");
  const riskLevel = item.risk_level ?? "low";
  const pending = Boolean(loading) || submitting;

  async function handleApprove() {
    try {
      setSubmitting(true);

      if (onApprove) {
        await onApprove();
        return;
      }

      const res = await fetch("/api/approvals", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          action: "approve",
          item,
        }),
      });

      if (!res.ok) {
        throw new Error("Failed to approve proposal");
      }

      router.refresh();
    } catch (err) {
      console.error(err);
      alert("Failed to approve proposal");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleReject() {
    try {
      setSubmitting(true);

      if (onReject) {
        await onReject();
        return;
      }

      const res = await fetch("/api/approvals", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          action: "reject",
          item,
        }),
      });

      if (!res.ok) {
        throw new Error("Failed to reject proposal");
      }

      router.refresh();
    } catch (err) {
      console.error(err);
      alert("Failed to reject proposal");
    } finally {
      setSubmitting(false);
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

      {blockedReason ? (
        <p className="mt-3 rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800">
          {blockedReason}
        </p>
      ) : null}

      <div className="mt-4 flex gap-3">
        <button
          onClick={handleApprove}
          disabled={pending || Boolean(blockedReason)}
          className="rounded-xl bg-zinc-900 px-4 py-2 text-sm text-white disabled:opacity-50"
        >
          {loading === "approve" || (!loading && submitting) ? "Working..." : "Approve"}
        </button>

        <button
          onClick={handleReject}
          disabled={pending || Boolean(blockedReason)}
          className="rounded-xl border border-zinc-300 px-4 py-2 text-sm text-zinc-700 disabled:opacity-50"
        >
          {loading === "reject" ? "Working..." : "Reject"}
        </button>
      </div>
    </div>
  );
}
