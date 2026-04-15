import "./globals.css";
import ShellBoundary from "@/components/shell-boundary";
import { getAuthenticatedClient } from "@/lib/api";
import { resolveAuthenticatedStakeholder, type StakeholderRole } from "@/lib/stakeholder-auth";
import { createAdminClient } from "@/lib/supabase/admin";
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
  let role: StakeholderRole | "owner" = "owner";

  if (auth?.user) {
    const admin = createAdminClient();
    const { data: ownerProfile } = await admin
      .from("profiles")
      .select("id")
      .eq("id", auth.user.id)
      .maybeSingle();

    if (!ownerProfile?.id) {
      const resolved = await resolveAuthenticatedStakeholder(admin, auth.user);
      if (resolved) {
        role = resolved.role;
      }
    }
  }

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
