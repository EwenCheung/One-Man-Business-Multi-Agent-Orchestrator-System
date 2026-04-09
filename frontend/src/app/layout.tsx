import "./globals.css";
import ShellBoundary from "@/components/shell-boundary";
import { getAuthenticatedClient } from "@/lib/api";
import { QueryProvider } from "@/providers/query-provider";
import type { ReactNode } from "react";

export const metadata = {
  title: "Business Orchestrator",
  description: "Owner dashboard for approvals, digest, and role management",
};

export default async function RootLayout({
  children,
}: {
  children: ReactNode;
}) {
  const auth = await getAuthenticatedClient({ redirectOnFail: false });
  const role = auth?.user?.user_metadata?.role || "owner";

  return (
    <html lang="en">
      <body>
        <QueryProvider>
          <ShellBoundary role={role}>{children}</ShellBoundary>
        </QueryProvider>
      </body>
    </html>
  );
}
