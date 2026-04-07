"use client";

import type { ReactNode } from "react";

type Props = {
  open: boolean;
  title: string;
  description?: string;
  children: ReactNode;
  onCloseAction: () => void;
};

export default function ActionOverlay({ open, title, description, children, onCloseAction }: Props) {
  if (!open) {
    return null;
  }

  return (
    <div className="fixed inset-0 z-40 flex items-center justify-center bg-zinc-950/35 p-4">
      <div className="max-h-[90vh] w-full max-w-5xl overflow-y-auto rounded-[2rem] border border-zinc-200 bg-white p-6 shadow-[0_40px_120px_-36px_rgba(15,23,42,0.45)]">
        <div className="flex items-start justify-between gap-4 border-b border-zinc-100 pb-4">
          <div>
            <h2 className="text-3xl font-semibold text-zinc-900">{title}</h2>
            {description ? <p className="mt-2 text-sm leading-6 text-zinc-500">{description}</p> : null}
          </div>
          <button
            type="button"
            onClick={onCloseAction}
            className="rounded-xl border border-zinc-300 px-4 py-2 text-sm font-medium text-zinc-700"
          >
            Close
          </button>
        </div>
        <div className="pt-6">{children}</div>
      </div>
    </div>
  );
}
