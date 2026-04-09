"use client";

import type { ReactNode } from "react";

import { usePathname } from "next/navigation";

import AppShell from "@/components/app-shell";

const AUTH_ROUTES = new Set(["/login", "/signup", "/verify-email"]);

export default function ShellBoundary({ children, role }: { children: ReactNode; role: string }) {
  const pathname = usePathname();

  if (AUTH_ROUTES.has(pathname)) {
    return <>{children}</>;
  }

  return <AppShell role={role}>{children}</AppShell>;
}
