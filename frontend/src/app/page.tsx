import Link from "next/link";

const items = [
  { href: "/dashboard", label: "Dashboard" },
  { href: "/pending-approvals", label: "Pending Approvals" },
  { href: "/daily-digest", label: "Daily Digest" },
  { href: "/roles/customers", label: "Customers" },
  { href: "/roles/suppliers", label: "Suppliers" },
  { href: "/roles/investors", label: "Investors" },
  { href: "/roles/partners", label: "Partners" },
];

export default function HomePage() {
  return (
    <div className="mx-auto max-w-5xl">
      <div className="rounded-3xl border border-zinc-200 bg-white p-8 shadow-sm">
        <p className="text-sm font-medium uppercase tracking-[0.2em] text-zinc-500">
          Frontend Ready
        </p>
        <h1 className="mt-3 text-4xl font-semibold text-zinc-900">
          One-Man Business Multi-Agent Orchestrator
        </h1>
        <p className="mt-3 max-w-2xl text-zinc-600">
          This frontend provides the owner-facing control panel for dashboard
          summaries, pending approvals, daily digest, and role-based data views.
        </p>

        <div className="mt-8 grid gap-4 md:grid-cols-2">
          {items.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className="rounded-2xl border border-zinc-200 bg-zinc-50 p-5 transition hover:border-zinc-900 hover:bg-white"
            >
              <div className="text-lg font-semibold text-zinc-900">
                {item.label}
              </div>
              <div className="mt-2 text-sm text-zinc-500">{item.href}</div>
            </Link>
          ))}
        </div>
      </div>
    </div>
  );
}