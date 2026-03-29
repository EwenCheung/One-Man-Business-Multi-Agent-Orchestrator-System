import SectionCard from "@/components/section-card";
import StatCard from "@/components/stat-card";
import LogoutButton from "@/components/logout-button";
import {
  getDashboardStats,
  getDailyDigest,
  getPendingApprovals,
} from "@/lib/api";

export default async function DashboardPage() {
  const [stats, approvals, digest] = await Promise.all([
    getDashboardStats(),
    getPendingApprovals(),
    getDailyDigest(),
  ]);

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-3xl font-semibold text-zinc-900">Dashboard</h1>
          <p className="mt-2 text-zinc-500">
            Overview of current system activity, approvals, and recent insights.
          </p>
        </div>
        <LogoutButton />
      </div>

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-5">
        {stats.map((stat) => (
          <StatCard
            key={stat.title}
            title={stat.title}
            value={stat.value}
            description={stat.description}
          />
        ))}
      </div>

      <div className="grid gap-6 xl:grid-cols-2">
        <SectionCard title="Pending Approvals">
          <div className="space-y-3">
            {approvals.length === 0 ? (
              <p className="text-sm text-zinc-500">No pending approvals.</p>
            ) : (
              approvals.map((item) => (
                <div
                  key={item.id}
                  className="rounded-2xl border border-zinc-200 p-4"
                >
                  <div className="flex items-center justify-between gap-3">
                    <h3 className="font-medium text-zinc-900">{item.title}</h3>
                    <span className="rounded-full bg-zinc-100 px-3 py-1 text-xs font-medium text-zinc-700">
                      {item.risk_level ?? "low"}
                    </span>
                  </div>
                  <p className="mt-2 text-sm text-zinc-600">
                    {item.preview ?? "No preview available."}
                  </p>
                </div>
              ))
            )}
          </div>
        </SectionCard>

        <SectionCard title="Daily Digest">
          <div className="space-y-3">
            {digest.length === 0 ? (
              <p className="text-sm text-zinc-500">No digest items yet.</p>
            ) : (
              digest.map((item) => (
                <div
                  key={item.id}
                  className="rounded-2xl border border-zinc-200 p-4"
                >
                  <div className="flex items-center justify-between gap-3">
                    <h3 className="font-medium text-zinc-900">{item.title}</h3>
                    <span className="rounded-full bg-zinc-100 px-3 py-1 text-xs font-medium text-zinc-700">
                      {item.risk ?? "low"}
                    </span>
                  </div>
                  <p className="mt-2 text-sm text-zinc-600">
                    {item.summary ?? "No summary available."}
                  </p>
                </div>
              ))
            )}
          </div>
        </SectionCard>
      </div>
    </div>
  );
}