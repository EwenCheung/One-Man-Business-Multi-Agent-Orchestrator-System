"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const links = [
  { href: "/dashboard", label: "Dashboard" },
  { href: "/pending-approvals", label: "Pending Approvals" },
  { href: "/daily-digest", label: "Daily Digest" },
  { href: "/roles/customers", label: "Customers" },
  { href: "/roles/suppliers", label: "Suppliers" },
  { href: "/roles/investors", label: "Investors" },
  { href: "/roles/partners", label: "Partners" },
];

export default function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="hidden w-72 shrink-0 border-r border-zinc-200 bg-white lg:flex lg:flex-col">
      <div className="border-b border-zinc-200 px-6 py-5">
        <div className="text-xs font-medium uppercase tracking-[0.2em] text-zinc-500">
          Owner Panel
        </div>
        <div className="mt-2 text-xl font-semibold text-zinc-900">
          Business Orchestrator
        </div>
      </div>

      <nav className="flex-1 space-y-1 p-4">
        {links.map((link) => {
          const active = pathname === link.href;
          return (
            <Link
              key={link.href}
              href={link.href}
              className={`block rounded-xl px-4 py-3 text-sm font-medium transition ${
                active
                  ? "bg-zinc-300 text-white"
                  : "text-zinc-700 hover:bg-zinc-100"
              }`}
            >
              {link.label}
            </Link>
          );
        })}
      </nav>
    </aside>
  );
}