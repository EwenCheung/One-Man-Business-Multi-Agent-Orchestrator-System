"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import LogoutButton from "@/components/logout-button";

const ownerLinks = [
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

export default function Sidebar({ role = "owner" }: { role?: string }) {
  const pathname = usePathname();

  let links = ownerLinks;
  let panelTitle = "Owner Panel";
  
  if (role === "customer") {
    links = [{ href: "/dashboards/customer", label: "Customer Dashboard" }, { href: "/chat", label: "Contact Support" }];
    panelTitle = "Customer Portal";
  } else if (role === "investor") {
    links = [{ href: "/dashboards/investor", label: "Investor Dashboard" }];
    panelTitle = "Investor Portal";
  } else if (role === "supplier") {
    links = [{ href: "/dashboards/supplier", label: "Supplier Dashboard" }, { href: "/chat", label: "Contact Support" }];
    panelTitle = "Supplier Portal";
  } else if (role === "partner") {
    links = [{ href: "/dashboards/partner", label: "Partner Dashboard" }, { href: "/chat", label: "Contact Support" }];
    panelTitle = "Partner Portal";
  }

  return (
    <aside className="hidden w-72 shrink-0 border-r border-zinc-200/70 bg-[linear-gradient(180deg,rgba(255,255,255,0.98),rgba(244,244,245,0.92))] lg:flex lg:flex-col">
      <div className="border-b border-zinc-200/80 px-6 py-5">
        <div className="text-xs font-medium uppercase tracking-[0.2em] text-zinc-500">
          {panelTitle}
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
          const active = pathname === link.href;
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

      <div className="border-t border-zinc-200/80 p-4">
        <LogoutButton />
      </div>
    </aside>
  );
}
