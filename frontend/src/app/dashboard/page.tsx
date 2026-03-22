import SectionCard from "@/components/section-card";
import StatCard from "@/components/stat-card";
import { getDashboardStats, getDailyDigest, getPendingApprovals } from "@/lib/api";

export default async function DashboardPage() {
  const stats = await getDashboardStats();
  const approvals = await getPendingApprovals();
  const digest = await getDailyDigest();

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-semibold text-zinc-900">Dashboard</h1>
        <p className="mt-2 text-zinc-500">
          Overview of current system activity, approvals, and recent insights.
        </p>
      </div>

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
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
        <SectionCard
          title="Recent Pending Approvals"
          description="Latest proposals requiring owner review."
        >
          <div className="space-y-4">
            {approvals.slice(0, 2).map((item) => (
              <div
                key={item.id}
                className="rounded-xl bg-zinc-50 p-4 text-sm text-zinc-700"
              >
                <div className="font-semibold text-zinc-900">
                  {item.userId} · {item.role}
                </div>
                <div className="mt-1">{item.reason}</div>
              </div>
            ))}
          </div>
        </SectionCard>

        <SectionCard
          title="Daily Digest Highlights"
          description="Most important conversation summaries today."
        >
          <div className="space-y-4">
            {digest.slice(0, 3).map((item) => (
              <div
                key={item.id}
                className="rounded-xl bg-zinc-50 p-4 text-sm text-zinc-700"
              >
                <div className="font-semibold text-zinc-900">{item.title}</div>
                <div className="mt-1">{item.summary}</div>
              </div>
            ))}
          </div>
        </SectionCard>
      </div>
    </div>
  );
}