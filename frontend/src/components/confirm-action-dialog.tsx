"use client";

type Props = {
  open: boolean;
  title: string;
  description: string;
  confirmLabel: string;
  cancelLabel?: string;
  loading?: boolean;
  onConfirmAction: () => void;
  onCancelAction: () => void;
};

export default function ConfirmActionDialog({
  open,
  title,
  description,
  confirmLabel,
  cancelLabel = "Cancel",
  loading,
  onConfirmAction,
  onCancelAction,
}: Props) {
  if (!open) {
    return null;
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-zinc-950/40 p-4">
      <div className="w-full max-w-lg rounded-2xl border border-zinc-200 bg-white p-6 shadow-xl">
        <h2 className="text-xl font-semibold text-zinc-900">{title}</h2>
        <p className="mt-3 text-sm leading-6 text-zinc-600">{description}</p>
        <div className="mt-6 flex flex-wrap gap-3">
          <button
            type="button"
            onClick={onConfirmAction}
            disabled={loading}
            className="rounded-xl bg-zinc-900 px-4 py-3 text-sm font-medium text-white disabled:opacity-50"
          >
            {loading ? "Working..." : confirmLabel}
          </button>
          <button
            type="button"
            onClick={onCancelAction}
            disabled={loading}
            className="rounded-xl border border-zinc-300 px-4 py-3 text-sm font-medium text-zinc-700 disabled:opacity-50"
          >
            {cancelLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
