"use client";

import LogoutButton from "@/components/logout-button";
import StatCard from "@/components/stat-card";
import DailyDigestSection from "@/components/owner-dashboard/sections/daily-digest-section";
import MemoryQueueSection from "@/components/owner-dashboard/sections/memory-queue-section";
import PendingApprovalsSection from "@/components/owner-dashboard/sections/pending-approvals-section";
import { useOwnerDashboard } from "@/hooks/use-owner-dashboard";
import type { DashboardPayload } from "@/lib/types";

export default function DashboardClient({ initialData }: { initialData: DashboardPayload }) {
  const { data, isLoading, isError } = useOwnerDashboard(initialData);

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-3xl font-semibold text-zinc-900">Dashboard</h1>
          <p className="mt-2 text-zinc-500">
            Live oversight for approvals, memory updates, and operating signals.
          </p>
        </div>
        <LogoutButton />
      </div>

      {isError ? <p className="rounded-2xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">Failed to refresh dashboard data.</p> : null}

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-5">
        {data.stats.map((stat) => (
          <StatCard key={stat.title} title={stat.title} value={stat.value} description={stat.description} />
        ))}
      </div>

      {isLoading ? <p className="text-sm text-zinc-500">Refreshing dashboard...</p> : null}

      <div className="grid gap-6 xl:grid-cols-2">
        <PendingApprovalsSection
          approvals={data.pendingApprovals.slice(0, 6)}
          description="Items that still need owner review before action is taken."
        />
        <DailyDigestSection initialData={data.dailyDigest} title="Statistics" compact />
      </div>

      <MemoryQueueSection items={data.memoryQueue} />
    </div>
  );
}
