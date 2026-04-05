"use client";

import { useMemo, useState } from "react";
import ConfirmActionDialog from "@/components/confirm-action-dialog";
import { useMemoryMutations, useMemoryOverview } from "@/hooks/use-memory";
import { updateOwnerProfile } from "@/lib/api-client";
import type { DailyDigestItem, DailyDigestInput, MemoryOverviewPayload, OwnerMemoryRule } from "@/lib/types";

type ViewState =
  | { kind: "profile_memory" }
  | { kind: "rule"; rule: OwnerMemoryRule }
  | { kind: "digest"; digest: DailyDigestItem }
  | null;

export default function MemoryClient({ initialData }: { initialData: MemoryOverviewPayload }) {
  const { data, isLoading, isError } = useMemoryOverview(initialData);
  const { saveOwnerRule, saveDailyDigest, isSavingRule, isSavingDigest } = useMemoryMutations();
  const defaultView = useMemo<ViewState>(() => {
    if (initialData.ownerProfile) return { kind: "profile_memory" };
    if (initialData.ownerRules[0]) return { kind: "rule", rule: initialData.ownerRules[0] };
    if (initialData.dailyDigest[0]) return { kind: "digest", digest: initialData.dailyDigest[0] };
    return null;
  }, [initialData]);
  const [selectedView, setSelectedView] = useState<ViewState>(defaultView);
  const [editorValue, setEditorValue] = useState(
    defaultView?.kind === "profile_memory" 
      ? initialData.ownerProfile?.memory_context ?? "" 
      : defaultView?.kind === "rule" 
        ? defaultView.rule.content 
        : defaultView?.kind === "digest" 
          ? defaultView.digest.summary ?? "" 
          : ""
  );
  const [confirmSave, setConfirmSave] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isSavingProfileMemory, setIsSavingProfileMemory] = useState(false);

  function selectProfileMemory() {
    setSelectedView({ kind: "profile_memory" });
    setEditorValue(data.ownerProfile?.memory_context ?? "");
    setErrorMessage(null);
  }

  function selectRule(rule: OwnerMemoryRule) {
    setSelectedView({ kind: "rule", rule });
    setEditorValue(rule.content);
    setErrorMessage(null);
  }

  function selectDigest(digest: DailyDigestItem) {
    setSelectedView({ kind: "digest", digest });
    setEditorValue(digest.summary ?? "");
    setErrorMessage(null);
  }

  async function handleSave() {
    if (!selectedView) return;
    setErrorMessage(null);

    try {
      if (selectedView.kind === "profile_memory") {
        setIsSavingProfileMemory(true);
        await updateOwnerProfile({ memory_context: editorValue });
        setIsSavingProfileMemory(false);
      } else if (selectedView.kind === "rule") {
        await saveOwnerRule(selectedView.rule.id, editorValue);
      } else {
        const payload: DailyDigestInput = {
          title: selectedView.digest.title,
          summary: editorValue,
          risk: selectedView.digest.risk ?? "low",
        };
        await saveDailyDigest(selectedView.digest.id, payload);
      }
      setConfirmSave(false);
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Failed to save memory item.");
      setConfirmSave(false);
      setIsSavingProfileMemory(false);
    }
  }

  const highlights = data.entityMemories.slice(0, 6);

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-zinc-500">Mission Control / Memory Centre</p>
          <h1 className="mt-2 text-3xl font-semibold text-zinc-900">Memory Centre</h1>
          <p className="mt-2 text-zinc-500">Read long-term memory and daily notes in one owner control centre.</p>
        </div>
      </div>

      {isLoading ? <p className="text-sm text-zinc-500">Refreshing memory centre...</p> : null}
      {isError ? <p className="rounded-2xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">Failed to load memory centre.</p> : null}
      {errorMessage ? <p className="rounded-2xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">{errorMessage}</p> : null}

      <div className="grid gap-4 md:grid-cols-3">
        <div className="rounded-3xl border border-zinc-200 bg-white p-5 shadow-sm">
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-zinc-500">Daily files</p>
          <p className="mt-3 text-4xl font-semibold text-zinc-900">{data.dailyDigest.length}</p>
          <p className="mt-2 text-sm text-zinc-500">Latest daily note: {data.dailyDigest[0]?.created_at?.slice(0, 10) ?? "—"}</p>
        </div>
        <div className="rounded-3xl border border-zinc-200 bg-white p-5 shadow-sm">
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-zinc-500">Long-term highlights</p>
          <p className="mt-3 text-4xl font-semibold text-zinc-900">{data.ownerRules.length + data.entityMemories.length}</p>
          <p className="mt-2 text-sm text-zinc-500">Curated rules and entity memory linked to your operations.</p>
        </div>
        <div className="rounded-3xl border border-zinc-200 bg-white p-5 shadow-sm">
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-zinc-500">Selected view</p>
          <p className="mt-3 text-4xl font-semibold text-zinc-900">
            {selectedView?.kind === "profile_memory" ? "Long-term" : selectedView?.kind === "rule" ? "Rule" : selectedView?.kind === "digest" ? "Daily" : "—"}
          </p>
          <p className="mt-2 text-sm text-zinc-500">Switch between durable memory and daily summary below.</p>
        </div>
      </div>

      <div className="grid gap-4 xl:grid-cols-[220px_minmax(0,1fr)_220px]">
        <section className="rounded-3xl border border-zinc-200 bg-white p-4 shadow-sm">
          <p className="text-sm font-semibold text-zinc-900">Memory files</p>
          <div className="mt-4 space-y-2">
            <button
              type="button"
              onClick={() => selectProfileMemory()}
              className={`w-full rounded-2xl border px-3 py-3 text-left ${selectedView?.kind === "profile_memory" ? "border-sky-200 bg-sky-50" : "border-zinc-200 bg-zinc-50"}`}
            >
              <p className="font-medium text-zinc-900">Long-term memory</p>
              <p className="mt-1 text-xs text-zinc-500">Owner profile memory context</p>
            </button>
            {data.dailyDigest.map((digest) => (
              <button
                key={digest.id}
                type="button"
                onClick={() => selectDigest(digest)}
                className={`w-full rounded-2xl border px-3 py-3 text-left ${selectedView?.kind === "digest" && selectedView.digest.id === digest.id ? "border-sky-200 bg-sky-50" : "border-zinc-200 bg-zinc-50"}`}
              >
                <p className="font-medium text-zinc-900">{digest.created_at?.slice(0, 10) ?? digest.title}</p>
                <p className="mt-1 text-xs text-zinc-500 line-clamp-2">{digest.summary ?? "No summary"}</p>
              </button>
            ))}
          </div>
        </section>

        <section className="rounded-3xl border border-zinc-200 bg-white p-5 shadow-sm">
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-zinc-500">Viewer</p>
          <h2 className="mt-2 text-2xl font-semibold text-zinc-900">
            {selectedView?.kind === "profile_memory" ? "Long-term memory" : selectedView?.kind === "rule" ? "Owner Rule" : "Daily memory summary"}
          </h2>
          <div className="mt-6 rounded-3xl border border-zinc-200 bg-zinc-50 p-6">
            {selectedView?.kind === "profile_memory" ? (
              <>
                <div className="flex flex-wrap gap-2 text-xs font-medium text-zinc-500">
                  <span className="rounded-full bg-white px-3 py-1">Owner Profile</span>
                  <span className="rounded-full bg-white px-3 py-1">Memory Context</span>
                </div>
                <textarea
                  value={editorValue}
                  onChange={(event) => setEditorValue(event.target.value)}
                  className="mt-4 min-h-[420px] w-full rounded-2xl border border-zinc-200 bg-white px-4 py-4 text-sm leading-7 text-zinc-800"
                />
              </>
            ) : selectedView?.kind === "rule" ? (
              <>
                <div className="flex flex-wrap gap-2 text-xs font-medium text-zinc-500">
                  <span className="rounded-full bg-white px-3 py-1">{selectedView.rule.role}</span>
                  <span className="rounded-full bg-white px-3 py-1">{selectedView.rule.category}</span>
                </div>
                <textarea
                  value={editorValue}
                  onChange={(event) => setEditorValue(event.target.value)}
                  className="mt-4 min-h-[420px] w-full rounded-2xl border border-zinc-200 bg-white px-4 py-4 text-sm leading-7 text-zinc-800"
                />
              </>
            ) : selectedView?.kind === "digest" ? (
              <>
                <div className="flex flex-wrap gap-2 text-xs font-medium text-zinc-500">
                  <span className="rounded-full bg-white px-3 py-1">{selectedView.digest.risk ?? "low"}</span>
                  <span className="rounded-full bg-white px-3 py-1">{selectedView.digest.created_at?.slice(0, 10) ?? "Daily summary"}</span>
                </div>
                <textarea
                  value={editorValue}
                  onChange={(event) => setEditorValue(event.target.value)}
                  className="mt-4 min-h-[420px] w-full rounded-2xl border border-zinc-200 bg-white px-4 py-4 text-sm leading-7 text-zinc-800"
                />
              </>
            ) : (
              <p className="text-sm text-zinc-500">Select a memory item to review.</p>
            )}
          </div>

          {selectedView ? (
            <div className="mt-4 flex flex-wrap gap-3">
              <button
                type="button"
                onClick={() => setConfirmSave(true)}
                disabled={isSavingRule || isSavingDigest || isSavingProfileMemory}
                className="rounded-xl bg-zinc-900 px-4 py-3 text-sm font-medium text-white disabled:opacity-50"
              >
                Save changes
              </button>
              <button
                type="button"
                onClick={() => {
                  if (selectedView.kind === "profile_memory") setEditorValue(data.ownerProfile?.memory_context ?? "");
                  if (selectedView.kind === "rule") setEditorValue(selectedView.rule.content);
                  if (selectedView.kind === "digest") setEditorValue(selectedView.digest.summary ?? "");
                }}
                className="rounded-xl border border-zinc-300 px-4 py-3 text-sm font-medium text-zinc-700"
              >
                Cancel
              </button>
            </div>
          ) : null}
        </section>

        <section className="rounded-3xl border border-zinc-200 bg-white p-4 shadow-sm">
          <p className="text-sm font-semibold text-zinc-900">Highlights</p>
          <div className="mt-4 space-y-3">
            {highlights.length === 0 ? (
              <p className="text-sm text-zinc-500">No long-term highlights yet.</p>
            ) : (
              highlights.map((memory) => (
                <article key={memory.id} className="rounded-2xl bg-zinc-50 p-3 text-sm text-zinc-700">
                  <p className="font-medium text-zinc-900">{memory.entity_role}</p>
                  <p className="mt-2 line-clamp-5">{memory.summary ?? memory.content}</p>
                </article>
              ))
            )}
          </div>
        </section>
      </div>

      <ConfirmActionDialog
        open={confirmSave}
        title="Confirm memory update"
        description="Save these changes to the selected memory item now?"
        confirmLabel="Confirm save"
        loading={isSavingRule || isSavingDigest || isSavingProfileMemory}
        onCancelAction={() => setConfirmSave(false)}
        onConfirmAction={handleSave}
      />
    </div>
  );
}
