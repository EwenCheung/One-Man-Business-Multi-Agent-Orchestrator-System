import ChatClient from "./chat-client";
import { getAuthenticatedClient } from "@/lib/api";
import { resolveAuthenticatedStakeholder, type StakeholderRole } from "@/lib/stakeholder-auth";
import { createAdminClient } from "@/lib/supabase/admin";

export default async function ChatPage() {
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

  if (role === "customer") {
    return (
      <ChatClient
        showThreads={false}
        useStakeholderThread
        panelTitle="Customer Support"
        panelDescription="Ask questions about products, orders, or support here."
        welcomeTitle="Welcome to Customer Support"
        welcomeDescription="Ask about products, orders, stock, or any help you need from the store."
        inputPlaceholder="Ask about products or your order..."
      />
    );
  }

  if (role === "supplier") {
    return (
      <ChatClient
        showThreads={false}
        useStakeholderThread
        panelTitle="Supplier Support"
        panelDescription="Discuss supply topics and business coordination here."
        welcomeTitle="Welcome to Supplier Support"
        welcomeDescription="Ask about supply requests, contracts, or coordination details here."
        inputPlaceholder="Ask about supply coordination..."
      />
    );
  }

  if (role === "partner") {
    return (
      <ChatClient
        showThreads={false}
        useStakeholderThread
        panelTitle="Partner Support"
        panelDescription="Discuss partnership topics and collaboration here."
        welcomeTitle="Welcome to Partner Support"
        welcomeDescription="Ask about partnership details, campaigns, or collaboration topics here."
        inputPlaceholder="Ask about partnership collaboration..."
      />
    );
  }

  if (role === "investor") {
    return (
      <ChatClient
        showThreads={false}
        useStakeholderThread
        panelTitle="Investor Assistant"
        panelDescription="Ask investor-level questions about the business here."
        welcomeTitle="Welcome to Investor Assistant"
        welcomeDescription="Ask about business performance, metrics, and investor-facing insights here."
        inputPlaceholder="Ask about business performance..."
      />
    );
  }

  return <ChatClient />;
}
