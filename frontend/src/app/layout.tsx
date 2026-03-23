import "./globals.css";
import AppShell from "@/components/app-shell";
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
        <AppShell>{children}</AppShell>
      </body>
    </html>
  );
}