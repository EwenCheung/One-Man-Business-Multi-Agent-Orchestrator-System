import { redirect } from "next/navigation";
import { createClient } from "@/lib/supabase/server";

async function getAuthenticatedClient() {
  const supabase = await createClient();

  const {
    data: { user },
    error,
  } = await supabase.auth.getUser();

  if (error || !user) {
    redirect("/login");
  }

  return { supabase, user };
}

export async function getCustomers() {
  const { supabase, user } = await getAuthenticatedClient();

  const { data, error } = await supabase
    .from("customers")
    .select("*")
    .eq("owner_id", user.id)
    .order("created_at", { ascending: false });

  if (error) throw error;
  return data ?? [];
}

export async function getSuppliers() {
  const { supabase, user } = await getAuthenticatedClient();

  const { data, error } = await supabase
    .from("suppliers")
    .select("*")
    .eq("owner_id", user.id)
    .order("created_at", { ascending: false });

  if (error) throw error;
  return data ?? [];
}

export async function getInvestors() {
  const { supabase, user } = await getAuthenticatedClient();

  const { data, error } = await supabase
    .from("investors")
    .select("*")
    .eq("owner_id", user.id)
    .order("created_at", { ascending: false });

  if (error) throw error;
  return data ?? [];
}

export async function getPartners() {
  const { supabase, user } = await getAuthenticatedClient();

  const { data, error } = await supabase
    .from("partners")
    .select("*")
    .eq("owner_id", user.id)
    .order("created_at", { ascending: false });

  if (error) throw error;
  return data ?? [];
}

import { redirect } from "next/navigation";
import { createClient } from "@/lib/supabase/server";

async function getAuthenticatedClient() {
  const supabase = await createClient();

  const {
    data: { user },
    error,
  } = await supabase.auth.getUser();

  if (error || !user) {
    redirect("/login");
  }

  return { supabase, user };
}

export async function getPendingApprovals() {
  const { supabase, user } = await getAuthenticatedClient();

  const { data, error } = await supabase
    .from("pending_approvals")
    .select("id, title, sender, preview, proposal_type, risk_level, status, proposal_id")
    .eq("owner_id", user.id)
    .eq("status", "pending")
    .order("created_at", { ascending: false });

  if (error) throw error;
  return data ?? [];
}

export async function getDailyDigest() {
  const { supabase, user } = await getAuthenticatedClient();

  const { data, error } = await supabase
    .from("daily_digest")
    .select("*")
    .eq("owner_id", user.id)
    .order("created_at", { ascending: false });

  if (error) throw error;
  return data ?? [];
}

export async function getOwnerMemoryRules() {
  const { supabase, user } = await getAuthenticatedClient();

  const { data, error } = await supabase
    .from("owner_memory_rules")
    .select("*")
    .eq("owner_id", user.id)
    .order("updated_at", { ascending: false });

  if (error) throw error;
  return data ?? [];
}

export async function getEntityMemories() {
  const { supabase, user } = await getAuthenticatedClient();

  const { data, error } = await supabase
    .from("entity_memories")
    .select("*")
    .eq("owner_id", user.id)
    .order("updated_at", { ascending: false });

  if (error) throw error;
  return data ?? [];
}

export async function getDashboardStats() {
  const { supabase, user } = await getAuthenticatedClient();

  const [
    customersResult,
    suppliersResult,
    investorsResult,
    partnersResult,
    pendingResult,
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
  ];
}