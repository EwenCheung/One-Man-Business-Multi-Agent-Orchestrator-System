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
  const [showDetails, setShowDetails] = useState(false);

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

  function openConversation() {
    const threadId = item.contextDetails?.conversationLinkThreadId;
    if (!threadId) return;
    router.push(`/messages?threadId=${encodeURIComponent(threadId)}`);
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

      {item.contextDetails && (
        <div className="mt-4">
          <button
            onClick={() => setShowDetails(!showDetails)}
            className="flex items-center gap-2 text-sm font-medium text-sky-600 hover:text-sky-700"
          >
            <span>{showDetails ? "Hide Details" : "View Details"}</span>
            <svg
              className={`h-4 w-4 transition-transform ${showDetails ? "rotate-180" : ""}`}
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
            </svg>
          </button>

          {showDetails && (
            <div className="mt-3 rounded-xl border border-zinc-200 bg-zinc-50 p-4">
              <div className="mb-4 rounded-xl bg-white p-4">
                <p className="text-xs font-semibold uppercase tracking-wider text-zinc-500">
                  What is happening
                </p>
                <p className="mt-2 text-sm text-zinc-700">
                  {item.contextDetails.explanation}
                </p>
                <p className="mt-3 text-sm text-zinc-700">
                  <span className="font-medium text-zinc-900">Why approval is needed:</span>{" "}
                  {item.contextDetails.approvalReason}
                </p>
                {item.contextDetails.conversationLinkThreadId ? (
                  <button
                    onClick={openConversation}
                    className="mt-4 rounded-lg border border-sky-200 bg-sky-50 px-3 py-2 text-sm font-medium text-sky-700 transition hover:bg-sky-100"
                  >
                    Open conversation in Messages
                  </button>
                ) : null}
              </div>

              {item.contextDetails.type === "reply" && (
                <div className="space-y-4">
                  <div>
                    <h4 className="text-xs font-semibold uppercase tracking-wider text-zinc-700">
                      Reply Context
                    </h4>
                    <div className="mt-2 space-y-2">
                      {item.contextDetails.threadContext && (
                        <div className="text-sm text-zinc-600">
                          <span className="font-medium">Sender:</span>{" "}
                          {item.contextDetails.threadContext.sender_name || "Unknown"} (
                          {item.contextDetails.threadContext.sender_role || "N/A"})
                          {item.contextDetails.threadContext.sender_channel && (
                            <span className="ml-2 text-xs text-zinc-500">
                              via {item.contextDetails.threadContext.sender_channel}
                            </span>
                          )}
                        </div>
                      )}
                      <div className="rounded-lg bg-white p-3 text-sm text-zinc-800">
                        <span className="font-medium text-zinc-700">Proposed Reply:</span>
                        <p className="mt-1 whitespace-pre-wrap">
                          {item.contextDetails.heldReply.reply_text}
                        </p>
                      </div>
                      {item.contextDetails.heldReply.risk_flags && 
                       item.contextDetails.heldReply.risk_flags.length > 0 && (
                        <div className="text-sm">
                          <span className="font-medium text-zinc-700">Risk Flags:</span>
                          <div className="mt-1 flex flex-wrap gap-1">
                            {item.contextDetails.heldReply.risk_flags.map((flag, idx) => (
                              <span
                                key={idx}
                                className="rounded-full bg-amber-100 px-2 py-0.5 text-xs text-amber-800"
                              >
                                {flag}
                              </span>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  </div>

                  {item.contextDetails.recentMessages.length > 0 && (
                    <div>
                      <h4 className="text-xs font-semibold uppercase tracking-wider text-zinc-700">
                        Recent Conversation
                      </h4>
                      <div className="mt-2 space-y-2">
                        {item.contextDetails.recentMessages
                          .slice()
                          .reverse()
                          .map((msg, idx) => (
                            <div
                              key={idx}
                              className={`rounded-lg p-2 text-sm ${
                                msg.direction === "inbound"
                                  ? "bg-zinc-100 text-zinc-800"
                                  : "bg-sky-50 text-sky-900"
                              }`}
                            >
                              <div className="flex items-baseline gap-2 text-xs text-zinc-500">
                                <span className="font-medium">
                                  {msg.sender_name || (msg.direction === "inbound" ? "Sender" : "You")}
                                </span>
                                {msg.created_at && (
                                  <span>{new Date(msg.created_at).toLocaleString()}</span>
                                )}
                              </div>
                              <p className="mt-1 line-clamp-2">{msg.content}</p>
                            </div>
                          ))}
                      </div>
                    </div>
                  )}
                </div>
              )}

              {item.contextDetails.type === "memory" && (
                <div className="space-y-3">
                  <h4 className="text-xs font-semibold uppercase tracking-wider text-zinc-700">
                    Memory Update Details
                  </h4>
                  <div className="space-y-2 text-sm text-zinc-600">
                    <div>
                      <span className="font-medium">Target:</span>{" "}
                      {item.contextDetails.proposal.target_table}
                    </div>
                    {item.contextDetails.proposal.reason && (
                      <div>
                        <span className="font-medium">Reason:</span>{" "}
                        {item.contextDetails.proposal.reason}
                      </div>
                    )}
                    <div className="rounded-lg bg-white p-3">
                      <span className="font-medium text-zinc-700">Proposed Content:</span>
                      <div className="mt-2 space-y-2 text-sm text-zinc-800">
                        {Array.isArray(item.contextDetails.proposal.proposed_content)
                          ? item.contextDetails.proposal.proposed_content.map((entry, idx) => (
                              <div key={idx} className="rounded-lg border border-zinc-200 bg-zinc-50 p-3">
                                {typeof entry === "object" && entry !== null ? (
                                  <div className="space-y-1">
                                    {Object.entries(entry as Record<string, unknown>).map(([key, value]) => (
                                      <p key={key}>
                                        <span className="font-medium text-zinc-700">{key}:</span>{" "}
                                        <span>{typeof value === "string" ? value : JSON.stringify(value)}</span>
                                      </p>
                                    ))}
                                  </div>
                                ) : (
                                  <p>{String(entry)}</p>
                                )}
                              </div>
                            ))
                          : <p>{JSON.stringify(item.contextDetails.proposal.proposed_content)}</p>}
                      </div>
                    </div>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      )}

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
