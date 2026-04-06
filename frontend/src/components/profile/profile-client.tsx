"use client";

import { useState } from "react";
import ConfirmActionDialog from "@/components/confirm-action-dialog";
import SectionCard from "@/components/section-card";
import { fetchOwnerProfile, updateOwnerProfile } from "@/lib/api-client";
import type { OwnerProfile, OwnerProfileInput } from "@/lib/types";
import Markdown from "react-markdown";

function ContextField({
  label,
  value,
  onChange,
  placeholder,
}: {
  label: string;
  value: string;
  onChange: (val: string) => void;
  placeholder: string;
}) {
  const [viewMode, setViewMode] = useState<"edit" | "preview">("edit");

  return (
    <div className="space-y-2 text-sm font-medium text-zinc-700">
      <div className="flex items-center justify-between">
        <span>{label}</span>
        <div className="flex gap-1 rounded-lg border border-zinc-200 bg-zinc-50 p-0.5">
          <button
            type="button"
            onClick={() => setViewMode("edit")}
            className={`rounded-md px-3 py-1.5 text-xs transition ${
              viewMode === "edit"
                ? "bg-white text-zinc-900 shadow-sm ring-1 ring-zinc-200"
                : "text-zinc-500 hover:text-zinc-700"
            }`}
          >
            Edit
          </button>
          <button
            type="button"
            onClick={() => setViewMode("preview")}
            className={`rounded-md px-3 py-1.5 text-xs transition ${
              viewMode === "preview"
                ? "bg-white text-zinc-900 shadow-sm ring-1 ring-zinc-200"
                : "text-zinc-500 hover:text-zinc-700"
            }`}
          >
            Preview
          </button>
        </div>
      </div>

      {viewMode === "edit" ? (
        <textarea
          value={value}
          onChange={(e) => onChange(e.target.value)}
          className="min-h-40 w-full rounded-xl border border-zinc-300 px-4 py-3 text-sm font-normal"
          placeholder={placeholder}
        />
      ) : (
        <div className="min-h-40 w-full rounded-xl border border-zinc-200 bg-white px-4 py-3 text-sm font-normal">
          {value.trim() ? (
            <div className="prose prose-sm prose-zinc max-w-none">
              <Markdown>{value}</Markdown>
            </div>
          ) : (
            <p className="text-zinc-400 italic">No content yet.</p>
          )}
        </div>
      )}
    </div>
  );
}

export default function ProfileClient({ initialData }: { initialData: OwnerProfile | null }) {
  const [profile, setProfile] = useState<OwnerProfile | null>(initialData);
  const [form, setForm] = useState<OwnerProfileInput>({
    full_name: initialData?.full_name ?? "",
    business_name: initialData?.business_name ?? "",
    business_description: initialData?.business_description ?? "",
    business_industry: initialData?.business_industry ?? "",
    business_timezone: initialData?.business_timezone ?? "",
    preferred_language: initialData?.preferred_language ?? "",
    default_reply_tone: initialData?.default_reply_tone ?? "",
    sender_summary_threshold: initialData?.sender_summary_threshold ?? 10,
    notifications_email: initialData?.notifications_email ?? "",
    notifications_enabled: initialData?.notifications_enabled ?? true,
    memory_context: initialData?.memory_context ?? "",
    soul_context: initialData?.soul_context ?? "",
    rule_context: initialData?.rule_context ?? "",
  });
  const [confirmSave, setConfirmSave] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  async function handleSave() {
    setErrorMessage(null);
    setIsSaving(true);

    try {
      const updated = await updateOwnerProfile(form);
      setProfile(updated);
      setForm({
        full_name: updated.full_name ?? "",
        business_name: updated.business_name ?? "",
        business_description: updated.business_description ?? "",
        business_industry: updated.business_industry ?? "",
        business_timezone: updated.business_timezone ?? "",
        preferred_language: updated.preferred_language ?? "",
        default_reply_tone: updated.default_reply_tone ?? "",
        sender_summary_threshold: updated.sender_summary_threshold ?? 10,
        notifications_email: updated.notifications_email ?? "",
        notifications_enabled: updated.notifications_enabled ?? true,
        memory_context: updated.memory_context ?? "",
        soul_context: updated.soul_context ?? "",
        rule_context: updated.rule_context ?? "",
      });
      setConfirmSave(false);

      setIsLoading(true);
      const refreshed = await fetchOwnerProfile();
      setProfile(refreshed);
      setIsLoading(false);
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Failed to save profile.");
      setConfirmSave(false);
    } finally {
      setIsSaving(false);
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-zinc-500">Settings / Profile</p>
          <h1 className="mt-2 text-3xl font-semibold text-zinc-900">Profile Settings</h1>
          <p className="mt-2 text-zinc-500">Manage your business profile and system preferences.</p>
        </div>
      </div>

      {isLoading ? <p className="text-sm text-zinc-500">Refreshing profile...</p> : null}
      {errorMessage ? <p className="rounded-2xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">{errorMessage}</p> : null}

      <SectionCard title="Basic Information" description="Your name and business details.">
        <div className="grid gap-4 md:grid-cols-2">
          <label className="space-y-2 text-sm font-medium text-zinc-700">
            <span>Full Name</span>
            <input
              value={form.full_name ?? ""}
              onChange={(event) => setForm((current) => ({ ...current, full_name: event.target.value }))}
              className="w-full rounded-xl border border-zinc-300 px-4 py-3 text-sm font-normal"
              placeholder="Your full name"
            />
          </label>

          <label className="space-y-2 text-sm font-medium text-zinc-700">
            <span>Business Name</span>
            <input
              value={form.business_name ?? ""}
              onChange={(event) => setForm((current) => ({ ...current, business_name: event.target.value }))}
              className="w-full rounded-xl border border-zinc-300 px-4 py-3 text-sm font-normal"
              placeholder="Your business name"
            />
          </label>

          <label className="md:col-span-2 space-y-2 text-sm font-medium text-zinc-700">
            <span>Business Description</span>
            <textarea
              value={form.business_description ?? ""}
              onChange={(event) => setForm((current) => ({ ...current, business_description: event.target.value }))}
              className="min-h-24 w-full rounded-xl border border-zinc-300 px-4 py-3 text-sm font-normal"
              placeholder="Describe your business"
            />
          </label>

          <label className="space-y-2 text-sm font-medium text-zinc-700">
            <span>Industry</span>
            <input
              value={form.business_industry ?? ""}
              onChange={(event) => setForm((current) => ({ ...current, business_industry: event.target.value }))}
              className="w-full rounded-xl border border-zinc-300 px-4 py-3 text-sm font-normal"
              placeholder="E.g., Retail, SaaS, Consulting"
            />
          </label>

          <label className="space-y-2 text-sm font-medium text-zinc-700">
            <span>Timezone</span>
            <input
              value={form.business_timezone ?? ""}
              onChange={(event) => setForm((current) => ({ ...current, business_timezone: event.target.value }))}
              className="w-full rounded-xl border border-zinc-300 px-4 py-3 text-sm font-normal"
              placeholder="E.g., America/New_York"
            />
          </label>
        </div>
      </SectionCard>

      <SectionCard title="System Preferences" description="Language, tone, and notification settings.">
        <div className="grid gap-4 md:grid-cols-2">
          <label className="space-y-2 text-sm font-medium text-zinc-700">
            <span>Preferred Language</span>
            <input
              value={form.preferred_language ?? ""}
              onChange={(event) => setForm((current) => ({ ...current, preferred_language: event.target.value }))}
              className="w-full rounded-xl border border-zinc-300 px-4 py-3 text-sm font-normal"
              placeholder="E.g., English"
            />
          </label>

          <label className="space-y-2 text-sm font-medium text-zinc-700">
            <span>Default Reply Tone</span>
            <input
              value={form.default_reply_tone ?? ""}
              onChange={(event) => setForm((current) => ({ ...current, default_reply_tone: event.target.value }))}
              className="w-full rounded-xl border border-zinc-300 px-4 py-3 text-sm font-normal"
              placeholder="E.g., professional, friendly"
            />
          </label>

          <label className="space-y-2 text-sm font-medium text-zinc-700">
            <span>Sender Summary Threshold</span>
            <input
              value={form.sender_summary_threshold ?? 10}
              onChange={(event) => setForm((current) => ({ ...current, sender_summary_threshold: Number(event.target.value) }))}
              className="w-full rounded-xl border border-zinc-300 px-4 py-3 text-sm font-normal"
              type="number"
              min="1"
            />
          </label>

          <label className="space-y-2 text-sm font-medium text-zinc-700">
            <span>Notifications Email</span>
            <input
              value={form.notifications_email ?? ""}
              onChange={(event) => setForm((current) => ({ ...current, notifications_email: event.target.value }))}
              className="w-full rounded-xl border border-zinc-300 px-4 py-3 text-sm font-normal"
              placeholder="email@example.com"
              type="email"
            />
          </label>

          <label className="flex items-center gap-3 space-y-2 text-sm font-medium text-zinc-700">
            <input
              type="checkbox"
              checked={form.notifications_enabled ?? true}
              onChange={(event) => setForm((current) => ({ ...current, notifications_enabled: event.target.checked }))}
              className="h-5 w-5 rounded border-zinc-300"
            />
            <span>Enable Notifications</span>
          </label>
        </div>
      </SectionCard>

      <SectionCard title="Context Fields" description="Large text fields for memory, soul, and rule contexts.">
        <div className="space-y-6">
          <ContextField
            label="Memory Context"
            value={form.memory_context ?? ""}
            onChange={(val) => setForm((current) => ({ ...current, memory_context: val }))}
            placeholder="Long-term memory context for the system..."
          />

          <ContextField
            label="Soul Context"
            value={form.soul_context ?? ""}
            onChange={(val) => setForm((current) => ({ ...current, soul_context: val }))}
            placeholder="Soul context: personality, values, voice..."
          />

          <ContextField
            label="Rule Context"
            value={form.rule_context ?? ""}
            onChange={(val) => setForm((current) => ({ ...current, rule_context: val }))}
            placeholder="Rules and guidelines for the system..."
          />
        </div>
      </SectionCard>

      <div className="flex flex-wrap gap-3">
        <button
          type="button"
          onClick={() => setConfirmSave(true)}
          disabled={isSaving}
          className="rounded-xl bg-zinc-900 px-4 py-3 text-sm font-medium text-white disabled:opacity-50"
        >
          Save Profile
        </button>
        <button
          type="button"
          onClick={() => {
            if (profile) {
              setForm({
                full_name: profile.full_name ?? "",
                business_name: profile.business_name ?? "",
                business_description: profile.business_description ?? "",
                business_industry: profile.business_industry ?? "",
                business_timezone: profile.business_timezone ?? "",
                preferred_language: profile.preferred_language ?? "",
                default_reply_tone: profile.default_reply_tone ?? "",
                sender_summary_threshold: profile.sender_summary_threshold ?? 10,
                notifications_email: profile.notifications_email ?? "",
                notifications_enabled: profile.notifications_enabled ?? true,
                memory_context: profile.memory_context ?? "",
                soul_context: profile.soul_context ?? "",
                rule_context: profile.rule_context ?? "",
              });
              setErrorMessage(null);
            }
          }}
          className="rounded-xl border border-zinc-300 px-4 py-3 text-sm font-medium text-zinc-700"
        >
          Reset Changes
        </button>
      </div>

      <ConfirmActionDialog
        open={confirmSave}
        title="Confirm profile update"
        description="Save these changes to your profile now?"
        confirmLabel="Confirm save"
        loading={isSaving}
        onCancelAction={() => setConfirmSave(false)}
        onConfirmAction={handleSave}
      />
    </div>
  );
}
