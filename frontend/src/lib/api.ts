import { redirect } from "next/navigation";
import { createClient } from "@/lib/supabase/server";
import type { ApprovalItem, ProductRow } from "@/lib/types";

export async function getAuthenticatedClient(options?: { redirectOnFail?: boolean }) {
  const supabase = await createClient();

  const {
    data: { user },
    error,
  } = await supabase.auth.getUser();

  if (error || !user) {
    if (options?.redirectOnFail === false) {
      return null;
    }

    redirect("/login");
  }

  return { supabase, user };
}

async function requireAuthenticatedClient() {
  const auth = await getAuthenticatedClient();

  if (!auth) {
    throw new Error("Authentication state unavailable.");
  }

  return auth;
}

function isMemoryApproval(item: ApprovalItem) {
  return !(item.proposal_type ?? "").toLowerCase().includes("reply") && Boolean(item.proposal_id);
}

export async function getCustomers() {
  const { supabase, user } = await requireAuthenticatedClient();

  const { data, error } = await supabase
    .from("customers")
    .select("*")
    .eq("owner_id", user.id)
    .order("created_at", { ascending: false });

  if (error) throw error;
  return data ?? [];
}

export async function getSuppliers() {
  const { supabase, user } = await requireAuthenticatedClient();

  const { data, error } = await supabase
    .from("suppliers")
    .select("*")
    .eq("owner_id", user.id)
    .order("created_at", { ascending: false });

  if (error) throw error;
  return data ?? [];
}

export async function getInvestors() {
  const { supabase, user } = await requireAuthenticatedClient();

  const { data, error } = await supabase
    .from("investors")
    .select("*")
    .eq("owner_id", user.id)
    .order("created_at", { ascending: false });

  if (error) throw error;
  return data ?? [];
}

export async function getPartners() {
  const { supabase, user } = await requireAuthenticatedClient();

  const { data, error } = await supabase
    .from("partners")
    .select("*")
    .eq("owner_id", user.id)
    .order("created_at", { ascending: false });

  if (error) throw error;
  return data ?? [];
}

export async function getProducts(): Promise<ProductRow[]> {
  const { supabase, user } = await requireAuthenticatedClient();

  const { data, error } = await supabase
    .from("products")
    .select("id, name, description, selling_price, cost_price, stock_number, product_link, category, created_at, updated_at")
    .eq("owner_id", user.id)
    .order("created_at", { ascending: false });

  if (error) throw error;
  return (data ?? []) as ProductRow[];
}


export async function getPendingApprovals() {
  const { supabase, user } = await requireAuthenticatedClient();

  const { data, error } = await supabase
    .from("pending_approvals")
    .select("id, title, sender, preview, proposal_type, risk_level, status, proposal_id, held_reply_id")
    .eq("owner_id", user.id)
    .eq("status", "pending")
    .order("created_at", { ascending: false });

  if (error) throw error;
  return data ?? [];
}

export async function getPendingMemoryApprovals() {
  const approvals = await getPendingApprovals();
  return approvals.filter((item: ApprovalItem) => isMemoryApproval(item));
}

export async function getDailyDigest() {
  const { supabase, user } = await requireAuthenticatedClient();

  const { data, error } = await supabase
    .from("daily_digest")
    .select("*")
    .eq("owner_id", user.id)
    .order("created_at", { ascending: false });

  if (error) throw error;
  return data ?? [];
}

export async function getOwnerMemoryRules() {
  const { supabase, user } = await requireAuthenticatedClient();

  const { data, error } = await supabase
    .from("owner_memory_rules")
    .select("*")
    .eq("owner_id", user.id)
    .order("updated_at", { ascending: false });

  if (error) throw error;
  return data ?? [];
}

export async function getEntityMemories() {
  const { supabase, user } = await requireAuthenticatedClient();

  const { data, error } = await supabase
    .from("entity_memories")
    .select("*")
    .eq("owner_id", user.id)
    .order("updated_at", { ascending: false });

  if (error) throw error;
  return data ?? [];
}

export async function getDashboardPayload() {
  const [stats, pendingApprovals, dailyDigest, memoryQueue] = await Promise.all([
    getDashboardStats(),
    getPendingApprovals(),
    getDailyDigest(),
    getPendingMemoryApprovals(),
  ]);

  return {
    stats,
    pendingApprovals,
    dailyDigest,
    memoryQueue,
  };
}

export async function getMemoryOverview() {
  const [pendingUpdates, ownerRules, entityMemories, dailyDigest] = await Promise.all([
    getPendingMemoryApprovals(),
    getOwnerMemoryRules(),
    getEntityMemories(),
    getDailyDigest(),
  ]);

  return {
    pendingUpdates,
    ownerRules,
    entityMemories,
    dailyDigest,
  };
}

export async function getDashboardStats() {
  const { supabase, user } = await requireAuthenticatedClient();

  const [
    customersResult,
    suppliersResult,
    investorsResult,
    partnersResult,
    pendingResult,
    productsResult,
    lowStockResult,
  ] = await Promise.all([
    supabase
      .from("customers")
      .select("*", { count: "exact", head: true })
      .eq("owner_id", user.id),

    supabase
      .from("suppliers")
      .select("*", { count: "exact", head: true })
      .eq("owner_id", user.id),

    supabase
      .from("investors")
      .select("*", { count: "exact", head: true })
      .eq("owner_id", user.id),

    supabase
      .from("partners")
      .select("*", { count: "exact", head: true })
      .eq("owner_id", user.id),

    supabase
      .from("pending_approvals")
      .select("*", { count: "exact", head: true })
      .eq("owner_id", user.id),

    supabase
      .from("products")
      .select("*", { count: "exact", head: true })
      .eq("owner_id", user.id),

    supabase
      .from("products")
      .select("*", { count: "exact", head: true })
      .eq("owner_id", user.id)
      .lt("stock_number", 20),
  ]);

  return [
    {
      title: "Customers",
      value: String(customersResult.count ?? 0),
      description: "Total customer records",
    },
    {
      title: "Suppliers",
      value: String(suppliersResult.count ?? 0),
      description: "Total supplier records",
    },
    {
      title: "Investors",
      value: String(investorsResult.count ?? 0),
      description: "Total investor records",
    },
    {
      title: "Partners",
      value: String(partnersResult.count ?? 0),
      description: "Total partner records",
    },
    {
      title: "Pending Approvals",
      value: String(pendingResult.count ?? 0),
      description: "Items waiting for review",
    },
    {
      title: "Products",
      value: String(productsResult.count ?? 0),
      description: "Catalog items you actively manage",
    },
    {
      title: "Low Stock",
      value: String(lowStockResult.count ?? 0),
      description: "Products below the inventory threshold",
    },
  ];
}
