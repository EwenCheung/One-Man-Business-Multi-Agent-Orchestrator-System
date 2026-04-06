import "./globals.css";
import AppShell from "@/components/app-shell";
import { QueryProvider } from "@/providers/query-provider";
import type { ReactNode } from "react";

export const metadata = {
  title: "Business Orchestrator",
  description: "Owner dashboard for approvals, digest, and role management",
};

export default function RootLayout({
  children,
}: {
  children: ReactNode;
}) {
  return (
    <html lang="en">
      <body>
        <QueryProvider>
          <AppShell>{children}</AppShell>
        </QueryProvider>
      </body>
    </html>
  );
}
