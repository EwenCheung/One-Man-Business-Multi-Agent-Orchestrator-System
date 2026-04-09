import { getAuthenticatedClient } from "@/lib/api";
import { createAdminClient } from "@/lib/supabase/admin";
import { redirect } from "next/navigation";
import ChatClient from "@/app/chat/chat-client";

type InvestorProductRow = {
  name: string;
  selling_price: number | null;
  cost_price: number | null;
  stock_number: number | null;
};

export default async function InvestorDashboardPage() {
  const auth = await getAuthenticatedClient();
  if (!auth) redirect("/login");
  
  if (auth.user.user_metadata?.role !== "investor") {
    return <p className="p-8 text-red-600">Unauthorized. You are not an investor.</p>;
  }

  const admin = createAdminClient();
  const { user } = auth;
  const { data: investorData } = await admin
    .from("investors")
    .select("id, owner_id")
    .or([user.email ? `email.eq.${user.email}` : null, user.phone ? `phone.eq.${user.phone}` : null].filter(Boolean).join(","))
    .single();
  const { data } = await admin
    .from("products")
    .select("name, selling_price, cost_price, stock_number")
    .eq("owner_id", investorData?.owner_id || "");
  const products: InvestorProductRow[] = data || [];

  const totalStock = products.reduce((sum, p) => sum + (p.stock_number || 0), 0);
  const avgMargin = products.reduce((sum, p) => sum + ((p.selling_price || 0) - (p.cost_price || 0)), 0) / (products.length || 1);

  return (
    <div className="space-y-6 max-w-5xl mx-auto py-8 px-4">
      <div>
        <h1 className="text-3xl font-semibold text-zinc-900">Investor Dashboard</h1>
        <p className="mt-2 text-zinc-500">Live statistics and AI Chatbot oversight.</p>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <div className="rounded-2xl border border-zinc-200 bg-white p-6">
          <h3 className="text-sm font-medium text-zinc-500">Total Products</h3>
          <p className="mt-2 text-3xl font-semibold text-zinc-900">{products.length}</p>
        </div>
        <div className="rounded-2xl border border-zinc-200 bg-white p-6">
          <h3 className="text-sm font-medium text-zinc-500">Total Stock</h3>
          <p className="mt-2 text-3xl font-semibold text-zinc-900">{totalStock}</p>
        </div>
        <div className="rounded-2xl border border-zinc-200 bg-white p-6">
          <h3 className="text-sm font-medium text-zinc-500">Average Margin</h3>
          <p className="mt-2 text-3xl font-semibold text-zinc-900">${avgMargin.toFixed(2)}</p>
        </div>
      </div>

      <div className="mt-8">
        <h2 className="text-2xl font-semibold text-zinc-900 mb-4">Investor Assistant</h2>
        <div className="h-[500px] border border-zinc-200 rounded-xl overflow-hidden bg-white">
          <ChatClient
            showThreads={false}
            panelTitle="Investor Assistant"
            panelDescription="Ask investor-level questions about the business metrics shown here."
            welcomeTitle="Welcome to Investor Assistant"
            welcomeDescription="Ask about product performance, stock movement, and business trends from the investor view."
            inputPlaceholder="Ask about business performance..."
          />
        </div>
      </div>
    </div>
  );
}
