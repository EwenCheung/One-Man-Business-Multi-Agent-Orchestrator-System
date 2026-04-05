"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";

const links = [
  { href: "/dashboard", label: "Dashboard" },
  { href: "/chat", label: "Chat to Agent" },
  { href: "/messages", label: "Messages" },
  { href: "/pending-approvals", label: "Pending Approvals" },
  { href: "/daily-digest", label: "Daily Digest" },
  { href: "/memory", label: "Memory Centre" },
  { href: "/operations/products", label: "Products" },
  { href: "/orders", label: "Orders" },
  { href: "/roles/customers", label: "Customers" },
  { href: "/roles/suppliers", label: "Suppliers" },
  { href: "/roles/investors", label: "Investors" },
  { href: "/roles/partners", label: "Partners" },
  { href: "/profile", label: "Profile" },
];

export default function Sidebar() {
  const pathname = usePathname();
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  return (
    <aside className="hidden w-72 shrink-0 border-r border-zinc-200/70 bg-[linear-gradient(180deg,rgba(255,255,255,0.98),rgba(244,244,245,0.92))] lg:flex lg:flex-col">
      <div className="border-b border-zinc-200/80 px-6 py-5">
        <div className="text-xs font-medium uppercase tracking-[0.2em] text-zinc-500">
          Owner Panel
        </div>
        <div className="mt-2 text-xl font-semibold text-zinc-900">
          Business Orchestrator
        </div>
        <p className="mt-3 max-w-[15rem] text-sm leading-6 text-zinc-500">
          Track decisions, stock, and relationships from one control surface.
        </p>
      </div>

      <nav className="flex-1 space-y-1 p-4">
        {links.map((link) => {
          const active = mounted && pathname === link.href;
          return (
            <Link
              key={link.href}
              href={link.href}
              className={`block rounded-xl px-4 py-3 text-sm font-medium transition ${
                active
                  ? "border border-sky-200 bg-sky-50 text-sky-900 shadow-sm"
                  : "text-zinc-700 hover:bg-white hover:text-zinc-900"
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
