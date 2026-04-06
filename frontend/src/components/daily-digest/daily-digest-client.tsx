"use client";

import DailyDigestSection from "@/components/owner-dashboard/sections/daily-digest-section";
import type { DailyDigestItem } from "@/lib/types";

export default function DailyDigestClient({ initialData }: { initialData: DailyDigestItem[] }) {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-semibold text-zinc-900">Daily Digest</h1>
        <p className="mt-2 text-zinc-500">Recent summaries, trend signals, and owner-visible highlights.</p>
      </div>

      <DailyDigestSection initialData={initialData} />
    </div>
  );
}
