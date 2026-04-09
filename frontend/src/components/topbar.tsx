"use client";

const roleLabels: Record<string, { title: string; subtitle: string; badge: string }> = {
  owner: {
    title: "Owner Dashboard",
    subtitle: "Review updates, monitor roles, and manage approvals.",
    badge: "Owner View",
  },
  customer: {
    title: "Customer Dashboard",
    subtitle: "Track purchases and browse the store.",
    badge: "Customer View",
  },
  supplier: {
    title: "Supplier Dashboard",
    subtitle: "Track supply contracts and product fulfillment.",
    badge: "Supplier View",
  },
  partner: {
    title: "Partner Dashboard",
    subtitle: "Review partnership agreements and collaboration details.",
    badge: "Partner View",
  },
  investor: {
    title: "Investor Dashboard",
    subtitle: "Monitor business performance and investor-facing insights.",
    badge: "Investor View",
  },
};

export default function Topbar({ role = "owner" }: { role?: string }) {
  const content = roleLabels[role] || roleLabels.owner;

  return (
    <div className="flex items-center justify-between border-b border-zinc-200/80 bg-white/85 px-6 py-4 backdrop-blur">
      <div>
        <h1 className="text-lg font-semibold text-zinc-900">{content.title}</h1>
        <p className="text-sm text-zinc-500">
          {content.subtitle}
        </p>
      </div>

       <div className="rounded-full border border-emerald-200 bg-emerald-50 px-4 py-2 text-sm font-medium text-emerald-800 shadow-sm">
          {content.badge}
        </div>
      </div>
  );
}
