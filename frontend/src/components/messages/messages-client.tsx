"use client";

import { useEffect, useState } from "react";
import { fetchMessageThreads, fetchMessageThread } from "@/lib/api-client";
import type { 
  MessageSenderRole, 
  MessageThreadPreview, 
  MessageThreadDetailResponse 
} from "@/lib/types";

export default function MessagesClient({ initialThreadId = null }: { initialThreadId?: string | null }) {
  const [threads, setThreads] = useState<MessageThreadPreview[]>([]);
  const [selectedThread, setSelectedThread] = useState<MessageThreadDetailResponse | null>(null);
  const [selectedThreadId, setSelectedThreadId] = useState<string | null>(null);
  const [showSummary, setShowSummary] = useState(false);
  const [roleFilter, setRoleFilter] = useState<MessageSenderRole | "all">("all");
  const [loading, setLoading] = useState(true);
  const [threadLoading, setThreadLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadThreads();
  }, [roleFilter]);

  useEffect(() => {
    if (initialThreadId) {
      void loadThread(initialThreadId);
    }
  }, [initialThreadId]);

  async function loadThreads() {
    try {
      setLoading(true);
      setError(null);
      const data = await fetchMessageThreads(roleFilter === "all" ? undefined : roleFilter);
      setThreads(data.threads);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load threads");
    } finally {
      setLoading(false);
    }
  }

  async function loadThread(threadId: string) {
    try {
      setThreadLoading(true);
      setSelectedThreadId(threadId);
      setShowSummary(false);
      const data = await fetchMessageThread(threadId);
      setSelectedThread(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load thread");
    } finally {
      setThreadLoading(false);
    }
  }

  const roleOptions: Array<{ value: MessageSenderRole | "all"; label: string }> = [
    { value: "all", label: "All Senders" },
    { value: "customer", label: "Customers" },
    { value: "supplier", label: "Suppliers" },
    { value: "partner", label: "Partners" },
    { value: "investor", label: "Investors" },
  ];

  return (
    <div className="flex h-screen flex-col">
      <div className="border-b border-zinc-200/80 bg-white px-8 py-6">
        <h1 className="text-2xl font-semibold text-zinc-900">Messages</h1>
        <p className="mt-1 text-sm text-zinc-500">
          External sender conversations with customers, suppliers, partners, and investors
        </p>
      </div>

      <div className="flex flex-1 overflow-hidden">
        <div className="flex w-96 flex-col border-r border-zinc-200/70 bg-zinc-50/50">
          <div className="border-b border-zinc-200/70 bg-white p-4">
            <label htmlFor="role-filter" className="block text-xs font-medium uppercase tracking-wider text-zinc-500">
              Filter by Role
            </label>
            <select
              id="role-filter"
              value={roleFilter}
              onChange={(e) => setRoleFilter(e.target.value as MessageSenderRole | "all")}
              className="mt-2 block w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm text-zinc-900 shadow-sm transition focus:border-sky-500 focus:outline-none focus:ring-1 focus:ring-sky-500"
            >
              {roleOptions.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </div>

          <div className="flex-1 overflow-y-auto">
            {loading ? (
              <div className="p-8 text-center text-sm text-zinc-500">Loading threads...</div>
            ) : error ? (
              <div className="p-8 text-center text-sm text-red-600">{error}</div>
            ) : threads.length === 0 ? (
              <div className="p-8 text-center text-sm text-zinc-500">
                No message threads found
              </div>
            ) : (
              <div className="space-y-1 p-2">
                {threads.map((thread) => (
                  <button
                    key={thread.thread_id}
                    onClick={() => loadThread(thread.thread_id)}
                    className={`w-full rounded-lg p-4 text-left transition ${
                      selectedThreadId === thread.thread_id
                        ? "bg-sky-50 shadow-sm ring-1 ring-sky-200"
                        : "bg-white hover:bg-zinc-50 hover:shadow-sm"
                    }`}
                  >
                    <div className="flex items-start justify-between">
                      <div className="min-w-0 flex-1">
                        <div className="flex items-baseline gap-2">
                          <p className="truncate font-medium text-zinc-900">
                            {thread.sender.name || "Unknown"}
                          </p>
                          {thread.sender.role && (
                            <span className="shrink-0 rounded-full bg-zinc-100 px-2 py-0.5 text-xs font-medium capitalize text-zinc-600">
                              {thread.sender.role}
                            </span>
                          )}
                        </div>
                        {thread.preview && (
                          <p className="mt-1 line-clamp-2 text-sm text-zinc-600">
                            {thread.preview}
                          </p>
                        )}
                        {thread.last_message_at && (
                          <p className="mt-2 text-xs text-zinc-400">
                            {new Date(thread.last_message_at).toLocaleString()}
                          </p>
                        )}
                      </div>
                      {thread.message_count > 0 && (
                        <div className="ml-3 flex shrink-0 items-center gap-1 text-xs text-zinc-500">
                          <span>{thread.message_count}</span>
                          <span>msg</span>
                        </div>
                      )}
                    </div>
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>

        <div className="flex flex-1 flex-col bg-white">
          {!selectedThread && !threadLoading ? (
            <div className="flex flex-1 items-center justify-center">
              <div className="text-center">
                <p className="text-lg font-medium text-zinc-900">Select a conversation</p>
                <p className="mt-1 text-sm text-zinc-500">
                  Choose a thread from the list to view messages
                </p>
              </div>
            </div>
          ) : threadLoading ? (
            <div className="flex flex-1 items-center justify-center">
              <p className="text-sm text-zinc-500">Loading conversation...</p>
            </div>
          ) : selectedThread ? (
            <>
              <div className="border-b border-zinc-200/80 bg-zinc-50/50 px-8 py-6">
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <h2 className="text-xl font-semibold text-zinc-900">
                      {selectedThread.thread.sender.name || "Unknown"}
                    </h2>
                    <div className="mt-2 flex flex-wrap gap-3 text-sm text-zinc-600">
                      {selectedThread.thread.sender.role && (
                        <span className="inline-flex items-center gap-1.5">
                          <span className="font-medium capitalize text-zinc-700">
                            {selectedThread.thread.sender.role}
                          </span>
                        </span>
                      )}
                      {selectedThread.thread.sender.external_id && (
                        <span className="inline-flex items-center gap-1.5">
                          <span className="text-zinc-400">•</span>
                          <span className="text-xs text-zinc-500">
                            ID: {selectedThread.thread.sender.external_id}
                          </span>
                        </span>
                      )}
                      {selectedThread.thread.sender.channel && (
                        <span className="inline-flex items-center gap-1.5">
                          <span className="text-zinc-400">•</span>
                          <span className="text-xs text-zinc-500">
                            {selectedThread.thread.sender.channel}
                          </span>
                        </span>
                      )}
                    </div>
                  </div>
                  <button
                    onClick={() => setShowSummary((current) => !current)}
                    className="rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm font-medium text-zinc-700 transition hover:bg-zinc-50"
                  >
                    {showSummary ? "Hide message summary" : "Show message summary"}
                  </button>
                </div>
                {showSummary ? (
                  <div className="mt-4 rounded-lg bg-sky-50 p-3">
                    <p className="text-xs font-medium uppercase tracking-wider text-sky-700">
                      Message Summary
                    </p>
                    <p className="mt-1 text-sm text-zinc-700">
                      {selectedThread.sender_summary.summary ??
                        "A message summary has not been generated for this conversation yet. Once the system has enough history, this summary will appear here and will also be used as sender context for future replies."}
                    </p>
                    {selectedThread.sender_summary.last_summarized_at ? (
                      <p className="mt-2 text-xs text-zinc-500">
                        Last updated: {new Date(selectedThread.sender_summary.last_summarized_at).toLocaleString()}
                      </p>
                    ) : null}
                  </div>
                ) : null}
              </div>

              <div className="flex-1 overflow-y-auto px-8 py-6">
                <div className="space-y-6">
                  {selectedThread.messages.map((message) => {
                    const isInbound = message.direction === "inbound";
                    const isOwner = message.sender_role?.toLowerCase() === "owner";

                    return (
                      <div
                        key={message.id}
                        className={`flex ${isInbound ? "justify-start" : "justify-end"}`}
                      >
                        <div
                          className={`max-w-2xl rounded-2xl px-5 py-3.5 ${
                            isInbound
                              ? "bg-zinc-100 text-zinc-900"
                              : isOwner
                                ? "bg-emerald-500 text-white"
                                : "bg-sky-500 text-white"
                          }`}
                        >
                          <div className="mb-1.5 flex items-baseline gap-2">
                            <span className="text-xs font-medium opacity-70">
                              {message.sender_name || 
                                (isInbound ? selectedThread.thread.sender.name : "Agent")}
                            </span>
                            {message.created_at && (
                              <span className="text-xs opacity-50">
                                {new Date(message.created_at).toLocaleString()}
                              </span>
                            )}
                          </div>
                          <p className="whitespace-pre-wrap text-sm leading-relaxed">
                            {message.content}
                          </p>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            </>
          ) : null}
        </div>
      </div>
    </div>
  );
}
