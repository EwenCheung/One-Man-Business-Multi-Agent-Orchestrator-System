"use client";

import type {
  ApprovalItem,
  DailyDigestItem,
  DailyDigestInput,
  DashboardPayload,
  MemoryOverviewPayload,
  MessageSenderRole,
  MessageThreadDetailResponse,
  MessageThreadsResponse,
  OwnerChatThreadsResponse,
  OwnerProfile,
  OwnerProfileInput,
  OrderDetail,
  OrderRow,
  ProductInput,
  ProductRow,
  StakeholderInput,
  StakeholderRole,
  StakeholderRow,
  StakeholderSwitchInput,
} from "@/lib/types";

async function readJson<T>(response: Response): Promise<T> {
  if (!response.ok) {
    let message = "Request failed";

    try {
      const payload = (await response.json()) as { error?: string };
      if (payload.error) {
        message = payload.error;
      }
    } catch {}

    throw new Error(message);
  }

  return response.json() as Promise<T>;
}

export async function fetchOwnerDashboard(): Promise<DashboardPayload> {
  const response = await fetch("/api/dashboard", {
    credentials: "include",
  });

  return readJson<DashboardPayload>(response);
}

export async function fetchPendingApprovals(): Promise<ApprovalItem[]> {
  const response = await fetch("/api/approvals", {
    credentials: "include",
  });

  return readJson<ApprovalItem[]>(response);
}

export async function fetchDailyDigest(): Promise<DailyDigestItem[]> {
  const response = await fetch("/api/daily-digest", {
    credentials: "include",
  });

  return readJson<DailyDigestItem[]>(response);
}

export async function fetchMemoryOverview(): Promise<MemoryOverviewPayload> {
  const response = await fetch("/api/memory", {
    credentials: "include",
  });

  return readJson<MemoryOverviewPayload>(response);
}

export async function fetchOwnerProfile(): Promise<OwnerProfile | null> {
  const response = await fetch("/api/profile", {
    credentials: "include",
  });

  return readJson<OwnerProfile | null>(response);
}

export async function updateOwnerProfile(payload: OwnerProfileInput): Promise<OwnerProfile> {
  const response = await fetch("/api/profile", {
    method: "PATCH",
    headers: {
      "Content-Type": "application/json",
    },
    credentials: "include",
    body: JSON.stringify(payload),
  });

  return readJson<OwnerProfile>(response);
}

export async function fetchOrders(): Promise<OrderRow[]> {
  const response = await fetch("/api/orders", {
    credentials: "include",
  });

  return readJson<OrderRow[]>(response);
}

export async function fetchOrder(orderId: string): Promise<OrderDetail> {
  const response = await fetch(`/api/orders/${orderId}`, {
    credentials: "include",
  });

  return readJson<OrderDetail>(response);
}

export async function submitApprovalAction(params: {
  action: "approve" | "reject";
  item: ApprovalItem;
}) {
  const response = await fetch("/api/approvals", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    credentials: "include",
    body: JSON.stringify(params),
  });

  return readJson<{ ok?: boolean; error?: string }>(response);
}

export async function fetchProducts(): Promise<ProductRow[]> {
  const response = await fetch("/api/products", {
    credentials: "include",
  });

  return readJson<ProductRow[]>(response);
}

export async function createProduct(payload: ProductInput): Promise<ProductRow> {
  const response = await fetch("/api/products", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    credentials: "include",
    body: JSON.stringify(payload),
  });

  return readJson<ProductRow>(response);
}

export async function updateProduct(productId: string, payload: ProductInput): Promise<ProductRow> {
  const response = await fetch(`/api/products/${productId}`, {
    method: "PATCH",
    headers: {
      "Content-Type": "application/json",
    },
    credentials: "include",
    body: JSON.stringify(payload),
  });

  return readJson<ProductRow>(response);
}

export async function deleteProduct(productId: string): Promise<{ ok: true }> {
  const response = await fetch(`/api/products/${productId}`, {
    method: "DELETE",
    credentials: "include",
  });

  return readJson<{ ok: true }>(response);
}

export async function adjustProductStock(productId: string, delta: number, reason: string): Promise<ProductRow> {
  const response = await fetch(`/api/products/${productId}/stock`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    credentials: "include",
    body: JSON.stringify({ delta, reason }),
  });

  return readJson<ProductRow>(response);
}

export async function fetchStakeholders(role: StakeholderRole): Promise<StakeholderRow[]> {
  const response = await fetch(`/api/roles/${role}`, {
    credentials: "include",
  });

  return readJson<StakeholderRow[]>(response);
}

export async function createStakeholder(role: StakeholderRole, payload: StakeholderInput): Promise<StakeholderRow> {
  const response = await fetch(`/api/roles/${role}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    credentials: "include",
    body: JSON.stringify(payload),
  });

  return readJson<StakeholderRow>(response);
}

export async function updateStakeholder(
  role: StakeholderRole,
  stakeholderId: string,
  payload: StakeholderInput
): Promise<StakeholderRow> {
  const response = await fetch(`/api/roles/${role}/${stakeholderId}`, {
    method: "PATCH",
    headers: {
      "Content-Type": "application/json",
    },
    credentials: "include",
    body: JSON.stringify(payload),
  });

  return readJson<StakeholderRow>(response);
}

export async function deleteStakeholder(role: StakeholderRole, stakeholderId: string): Promise<{ ok: true }> {
  const response = await fetch(`/api/roles/${role}/${stakeholderId}`, {
    method: "DELETE",
    credentials: "include",
  });

  return readJson<{ ok: true }>(response);
}

export async function switchStakeholderRole(payload: StakeholderSwitchInput): Promise<StakeholderRow> {
  const response = await fetch("/api/roles/switch", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    credentials: "include",
    body: JSON.stringify(payload),
  });

  return readJson<StakeholderRow>(response);
}

export async function updateOwnerMemoryRule(ruleId: string, content: string) {
  const response = await fetch(`/api/memory/owner-rules/${ruleId}`, {
    method: "PATCH",
    headers: {
      "Content-Type": "application/json",
    },
    credentials: "include",
    body: JSON.stringify({ content }),
  });

  return readJson<{ ok: true }>(response);
}

export async function updateDailyDigestItem(digestId: string, payload: DailyDigestInput) {
  const response = await fetch(`/api/daily-digest/${digestId}`, {
    method: "PATCH",
    headers: {
      "Content-Type": "application/json",
    },
    credentials: "include",
    body: JSON.stringify(payload),
  });

  return readJson<{ ok: true }>(response);
}

export async function fetchMessageThreads(role?: MessageSenderRole): Promise<MessageThreadsResponse> {
  const url = role 
    ? `/api/messages/threads?sender_roles=${role}`
    : "/api/messages/threads";

  const response = await fetch(url, {
    credentials: "include",
  });

  return readJson<MessageThreadsResponse>(response);
}

export async function fetchMessageThread(threadId: string): Promise<MessageThreadDetailResponse> {
  const response = await fetch(`/api/messages/threads/${threadId}`, {
    credentials: "include",
  });

  return readJson<MessageThreadDetailResponse>(response);
}

export async function fetchOwnerChatThreads(): Promise<OwnerChatThreadsResponse> {
  const response = await fetch("/api/owner-chat/threads", {
    credentials: "include",
  });

  return readJson<OwnerChatThreadsResponse>(response);
}

export async function deleteOwnerChatThread(threadId: string): Promise<{ ok: true }> {
  const response = await fetch(`/api/owner-chat/threads/${threadId}`, {
    method: "DELETE",
    credentials: "include",
  });

  return readJson<{ ok: true }>(response);
}
