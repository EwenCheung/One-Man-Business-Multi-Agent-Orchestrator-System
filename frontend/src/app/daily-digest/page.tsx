import SectionCard from "@/components/section-card";
import { getDailyDigest } from "@/lib/api";

function riskBadge(risk: "low" | "medium" | "high") {
  if (risk === "high") return "bg-red-100 text-red-700";
  if (risk === "medium") return "bg-amber-100 text-amber-700";
  return "bg-emerald-100 text-emerald-700";
}

export default async function DailyDigestPage() {
  const digest = await getDailyDigest();

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-semibold text-zinc-900">Daily Digest</h1>
        <p className="mt-2 text-zinc-500">
          Summaries of important conversations, signals, and review items.
        </p>
      </div>

      <div className="space-y-4">
        {digest.map((item) => (
          <SectionCard key={item.id} title={item.title} description={item.timestamp}>
            <div className="flex flex-wrap items-center gap-3">
              <span className="rounded-full bg-zinc-100 px-3 py-1 text-xs font-medium text-zinc-700">
                {item.category}
              </span>
              <span
                className={`rounded-full px-3 py-1 text-xs font-medium ${riskBadge(item.riskLevel)}`}
              >
                {item.riskLevel} risk
              </span>
            </div>
            <p className="mt-4 text-sm leading-6 text-zinc-700">{item.summary}</p>
          </SectionCard>
        ))}
      </div>
    </div>
  );
}