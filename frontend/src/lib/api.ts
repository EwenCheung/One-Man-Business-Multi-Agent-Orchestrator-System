import { redirect } from "next/navigation";
import { createClient } from "@/lib/supabase/server";
import type { ApprovalItem, OrderDetail, OrderRow, OwnerProfile, OwnerProfileInput, ProductRow } from "@/lib/types";

const OWNER_PROFILE_SELECT =
  "id, full_name, business_name, business_description, business_industry, business_timezone, preferred_language, default_reply_tone, sender_summary_threshold, notifications_email, notifications_enabled, memory_context, soul_context, rule_context, telegram_bot_token, telegram_webhook_secret, created_at, updated_at";

function buildReplyApprovalReason(riskFlags: string[] | null | undefined) {
  if (!riskFlags || riskFlags.length === 0) {
    return "This draft reply was paused because the system detected something sensitive and wants owner confirmation before sending it.";
  }

  return `This draft reply was paused because the system detected: ${riskFlags.join(", ")}.`;
}

function buildMemoryApprovalReason(reason: string | null | undefined) {
  if (!reason) {
    return "This memory update needs approval before the system saves it for future conversations.";
  }

  return `This memory update needs approval because ${reason}.`;
}

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
    .neq("status", "inactive")
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
    .neq("status", "inactive")
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
    .neq("status", "inactive")
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
    .neq("status", "inactive")
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

export async function getOrders(): Promise<OrderRow[]> {
  const { supabase, user } = await requireAuthenticatedClient();

  const { data, error } = await supabase
    .from("orders")
    .select(`
      id,
      customer_id,
      product_id,
      quantity,
      total_price,
      order_date,
      status,
      channel,
      created_at,
      customers(name, email),
      products(name)
    `)
    .eq("owner_id", user.id)
    .order("order_date", { ascending: false });

  if (error) throw error;

  const rows = (data ?? []) as Array<{
    id: string;
    customer_id: string;
    product_id: string;
    quantity: number;
    total_price: number | null;
    order_date: string | null;
    status: string | null;
    channel: string | null;
    created_at?: string | null;
    customers?: { name: string | null; email: string | null } | { name: string | null; email: string | null }[] | null;
    products?: { name: string | null } | { name: string | null }[] | null;
  }>;

  const customerEmails = new Map<string, string>();
  rows.forEach((row) => {
    const customer = Array.isArray(row.customers) ? row.customers[0] : row.customers;
    if (row.customer_id && customer?.email) {
      customerEmails.set(row.customer_id, customer.email);
    }
  });

  const threadMap = new Map<string, string>();
  const senderEmails = [...new Set(Array.from(customerEmails.values()))];
  if (senderEmails.length > 0) {
    const { data: threads } = await supabase
      .from("conversation_threads")
      .select("id, sender_external_id")
      .eq("owner_id", user.id)
      .eq("thread_type", "external_sender")
      .in("sender_external_id", senderEmails);

    const threadBySender = new Map((threads ?? []).map((thread) => [thread.sender_external_id, thread.id]));
    customerEmails.forEach((email, customerId) => {
      const threadId = threadBySender.get(email);
      if (threadId) {
        threadMap.set(customerId, threadId);
      }
    });
  }

  return rows.map((row) => {
    const customer = Array.isArray(row.customers) ? row.customers[0] : row.customers;
    const product = Array.isArray(row.products) ? row.products[0] : row.products;

    return {
      id: row.id,
      customer_id: row.customer_id,
      product_id: row.product_id,
      quantity: row.quantity,
      total_price: row.total_price,
      order_date: row.order_date,
      status: row.status,
      channel: row.channel,
      created_at: row.created_at ?? null,
      customer_name: customer?.name ?? null,
      customer_email: customer?.email ?? null,
      product_name: product?.name ?? null,
      message_thread_id: threadMap.get(row.customer_id) ?? null,
    } satisfies OrderRow;
  });
}

export async function getOrder(orderId: string): Promise<OrderDetail> {
  const { supabase, user } = await requireAuthenticatedClient();

  const { data, error } = await supabase
    .from("orders")
    .select(`
      id,
      customer_id,
      product_id,
      quantity,
      total_price,
      order_date,
      status,
      channel,
      created_at,
      customers(name, email, phone, company, preference, notes),
      products(name, description, category, product_link, selling_price, cost_price, stock_number)
    `)
    .eq("owner_id", user.id)
    .eq("id", orderId)
    .single();

  if (error) throw error;

  const customer = Array.isArray(data.customers) ? data.customers[0] : data.customers;
  const product = Array.isArray(data.products) ? data.products[0] : data.products;

  let messageThreadId: string | null = null;
  if (customer?.email) {
    const { data: thread } = await supabase
      .from("conversation_threads")
      .select("id")
      .eq("owner_id", user.id)
      .eq("thread_type", "external_sender")
      .eq("sender_external_id", customer.email)
      .maybeSingle();

    messageThreadId = thread?.id ?? null;
  }

  return {
    id: data.id,
    customer_id: data.customer_id,
    product_id: data.product_id,
    quantity: data.quantity,
    total_price: data.total_price,
    order_date: data.order_date,
    status: data.status,
    channel: data.channel,
    created_at: data.created_at ?? null,
    customer_name: customer?.name ?? null,
    customer_email: customer?.email ?? null,
    customer_phone: customer?.phone ?? null,
    customer_company: customer?.company ?? null,
    customer_preference: customer?.preference ?? null,
    customer_notes: customer?.notes ?? null,
    product_name: product?.name ?? null,
    product_description: product?.description ?? null,
    product_category: product?.category ?? null,
    product_link: product?.product_link ?? null,
    selling_price: product?.selling_price ?? null,
    cost_price: product?.cost_price ?? null,
    stock_number: product?.stock_number ?? null,
    message_thread_id: messageThreadId,
  } satisfies OrderDetail;
}


export async function getPendingApprovals() {
  const { supabase, user } = await requireAuthenticatedClient();

  const { data, error } = await supabase
    .from("pending_approvals")
    .select(`
      id, 
      title, 
      sender, 
      preview, 
      proposal_type, 
      risk_level, 
      status, 
      proposal_id, 
      held_reply_id,
      created_at
    `)
    .eq("owner_id", user.id)
    .eq("status", "pending")
    .order("created_at", { ascending: false });

  if (error) throw error;
  
  const approvals = data ?? [];
  
  const enrichedApprovals = await Promise.all(
    approvals.map(async (approval) => {
      let contextDetails: import("@/lib/types").ApprovalContextDetails | null = null;
      
      if (approval.held_reply_id) {
        const { data: heldReply } = await supabase
          .from("held_replies")
          .select("thread_id, sender_id, sender_name, sender_role, reply_text, risk_flags")
          .eq("id", approval.held_reply_id)
          .single();
        
        if (heldReply) {
          let threadContext: {
            sender_external_id: string | null;
            sender_name: string | null;
            sender_role: string | null;
            sender_channel: string | null;
          } | null = null;
          
          if (heldReply.thread_id) {
            const { data: thread } = await supabase
              .from("conversation_threads")
              .select("sender_external_id, sender_name, sender_role, sender_channel")
              .eq("id", heldReply.thread_id)
              .single();
            
            threadContext = thread;
          }
          
          let recentMessages: Array<{
            direction: string;
            content: string;
            sender_name: string | null;
            created_at: string | null;
          }> = [];
          
          if (heldReply.thread_id) {
            const { data: messages } = await supabase
              .from("messages")
              .select("direction, content, sender_name, created_at")
              .eq("conversation_thread_id", heldReply.thread_id)
              .order("created_at", { ascending: false })
              .limit(3);
            
            recentMessages = messages ?? [];
          }
          
          contextDetails = {
            type: "reply" as const,
            explanation:
              "The assistant prepared a reply for this sender, but it was held back so you can review the situation first.",
            approvalReason: buildReplyApprovalReason(heldReply.risk_flags as string[] | null),
            conversationLinkThreadId: heldReply.thread_id,
            heldReply: {
              thread_id: heldReply.thread_id,
              sender_id: heldReply.sender_id,
              sender_name: heldReply.sender_name,
              sender_role: heldReply.sender_role,
              reply_text: heldReply.reply_text,
              risk_flags: heldReply.risk_flags as string[] | null,
            },
            threadContext,
            recentMessages,
          };
        }
      }
      
      if (approval.proposal_id) {
        const { data: proposal } = await supabase
          .from("memory_update_proposals")
          .select("target_table, target_id, proposed_content, reason, risk_level")
          .eq("id", approval.proposal_id)
          .single();
        
        if (proposal) {
          const proposedItems = Array.isArray(proposal.proposed_content)
            ? proposal.proposed_content
            : [];
          const firstRecord = proposedItems[0] as { sender_id?: string | null } | undefined;
          let conversationLinkThreadId: string | null = null;

          if (firstRecord?.sender_id) {
            const { data: linkedThread } = await supabase
              .from("conversation_threads")
              .select("id")
              .eq("owner_id", user.id)
              .eq("sender_external_id", firstRecord.sender_id)
              .eq("thread_type", "external_sender")
              .order("updated_at", { ascending: false })
              .limit(1)
              .maybeSingle();

            conversationLinkThreadId = linkedThread?.id ?? null;
          }

          contextDetails = {
            type: "memory" as const,
            explanation:
              "The assistant wants to save something important it learned from this sender so future replies stay accurate.",
            approvalReason: buildMemoryApprovalReason(proposal.reason),
            conversationLinkThreadId,
            proposal: {
              target_table: proposal.target_table,
              target_id: proposal.target_id,
              proposed_content: proposal.proposed_content,
              reason: proposal.reason,
              risk_level: proposal.risk_level,
            },
          };
        }
      }
      
      return {
        ...approval,
        contextDetails,
      };
    })
  );
  
  return enrichedApprovals;
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

function startOfUtcToday() {
  const now = new Date();
  return new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate()));
}

function monthKey(dateValue: string) {
  const date = new Date(dateValue);
  return `${date.getUTCFullYear()}-${String(date.getUTCMonth() + 1).padStart(2, "0")}`;
}

function monthLabel(monthKeyValue: string) {
  const [year, month] = monthKeyValue.split("-").map(Number);
  return new Date(Date.UTC(year, month - 1, 1)).toLocaleString("en-US", {
    month: "long",
    year: "numeric",
    timeZone: "UTC",
  });
}

export async function getDailyDigestPayload() {
  const { supabase, user } = await requireAuthenticatedClient();
  const items = await getDailyDigest();

  const today = startOfUtcToday();
  const todayIsoDate = today.toISOString().slice(0, 10);
  const todayIso = today.toISOString();

  const months: { key: string; label: string }[] = [];
  for (let offset = 11; offset >= 0; offset -= 1) {
    const date = new Date(Date.UTC(today.getUTCFullYear(), today.getUTCMonth() - offset, 1));
    const key = `${date.getUTCFullYear()}-${String(date.getUTCMonth() + 1).padStart(2, "0")}`;
    months.push({ key, label: monthLabel(key) });
  }
  const monthKeys = new Set(months.map((month) => month.key));

  const [ordersResult, outboundMessagesResult, memoryEntriesResult, memoryProposalsResult] = await Promise.all([
    supabase
      .from("orders")
      .select("order_date, total_price, status")
      .eq("owner_id", user.id),
    supabase
      .from("messages")
      .select("sender_name, sender_role, content, created_at")
      .eq("owner_id", user.id)
      .eq("direction", "outbound")
      .gte("created_at", todayIso)
      .order("created_at", { ascending: false }),
    supabase
      .from("memory_entries")
      .select("created_at")
      .eq("owner_id", user.id)
      .gte("created_at", todayIso),
    supabase
      .from("memory_update_proposals")
      .select("created_at")
      .eq("owner_id", user.id)
      .gte("created_at", todayIso),
  ]);

  if (ordersResult.error) throw ordersResult.error;
  if (outboundMessagesResult.error) throw outboundMessagesResult.error;
  if (memoryEntriesResult.error) throw memoryEntriesResult.error;
  if (memoryProposalsResult.error) throw memoryProposalsResult.error;

  const orders = ordersResult.data ?? [];
  const outboundMessages = outboundMessagesResult.data ?? [];
  const memoryEntries = memoryEntriesResult.data ?? [];
  const memoryProposals = memoryProposalsResult.data ?? [];

  const todayOrders = orders.filter((order) => order.order_date === todayIsoDate);
  const paidSalesToday = todayOrders
    .filter((order) => (order.status || "").toLowerCase() === "paid")
    .reduce((sum, order) => sum + Number(order.total_price || 0), 0);

  const contactMap = new Map<string, { name: string; role: string; count: number; latest: string }>();
  for (const message of outboundMessages) {
    const name = message.sender_name || "Unknown";
    const role = message.sender_role || "unknown";
    const key = `${role}:${name}`;
    const current = contactMap.get(key);

    if (current) {
      current.count += 1;
      if (!current.latest) current.latest = message.content || "";
    } else {
      contactMap.set(key, {
        name,
        role,
        count: 1,
        latest: message.content || "",
      });
    }
  }

  const activities = [
    ...Array.from(contactMap.values()).slice(0, 6).map((entry) => ({
      title: `Replied to ${entry.name}`,
      detail: `${entry.count} reply${entry.count === 1 ? "" : "ies"} sent today for this ${entry.role}. Latest action: ${(entry.latest || "No preview available.").slice(0, 140)}${(entry.latest || "").length > 140 ? "…" : ""}`,
    })),
    ...(memoryEntries.length > 0
      ? [{ title: "Memory saved", detail: `${memoryEntries.length} durable memory update${memoryEntries.length === 1 ? "" : "s"} saved today.` }]
      : []),
    ...(memoryProposals.length > 0
      ? [{ title: "Memory awaiting review", detail: `${memoryProposals.length} memory proposal${memoryProposals.length === 1 ? "" : "s"} created for owner review today.` }]
      : []),
  ].slice(0, 8);

  const monthlyAccumulator = new Map<string, { orders: number; paidSales: number }>();
  for (const month of months) {
    monthlyAccumulator.set(month.key, { orders: 0, paidSales: 0 });
  }

  for (const order of orders) {
    if (!order.order_date) continue;
    const key = monthKey(order.order_date);
    if (!monthKeys.has(key)) continue;
    const bucket = monthlyAccumulator.get(key);
    if (!bucket) continue;
    bucket.orders += 1;
    if ((order.status || "").toLowerCase() === "paid") {
      bucket.paidSales += Number(order.total_price || 0);
    }
  }

  return {
    items,
    metrics: {
      contactsToday: contactMap.size,
      newOrdersToday: todayOrders.length,
      paidSalesToday,
      memoryUpdatesToday: memoryEntries.length + memoryProposals.length,
    },
    monthly: months.map((month) => ({
      month: month.label,
      orders: monthlyAccumulator.get(month.key)?.orders || 0,
      paidSales: monthlyAccumulator.get(month.key)?.paidSales || 0,
    })),
    activities,
  };
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

export async function getOwnerProfile(): Promise<OwnerProfile | null> {
  const { supabase, user } = await requireAuthenticatedClient();

  const { data, error } = await supabase
    .from("profiles")
    .select(OWNER_PROFILE_SELECT)
    .eq("id", user.id)
    .maybeSingle();

  if (error) throw error;
  return (data as OwnerProfile | null) ?? null;
}

export async function upsertOwnerProfile(payload: OwnerProfileInput): Promise<OwnerProfile> {
  const { supabase, user } = await requireAuthenticatedClient();

  const updatePayload = {
    id: user.id,
    ...payload,
    updated_at: new Date().toISOString(),
  };

  const { data, error } = await supabase
    .from("profiles")
    .upsert(updatePayload)
    .select(OWNER_PROFILE_SELECT)
    .single();

  if (error) throw error;
  return data as OwnerProfile;
}

export async function getDashboardPayload() {
  const [stats, pendingApprovals, dailyDigest, memoryQueue] = await Promise.all([
    getDashboardStats(),
    getPendingApprovals(),
    getDailyDigestPayload(),
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
  const [pendingUpdates, ownerRules, entityMemories, dailyDigest, ownerProfile] = await Promise.all([
    getPendingMemoryApprovals(),
    getOwnerMemoryRules(),
    getEntityMemories(),
    getDailyDigest(),
    getOwnerProfile(),
  ]);

  return {
    pendingUpdates,
    ownerRules,
    entityMemories,
    dailyDigest,
    ownerProfile,
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
