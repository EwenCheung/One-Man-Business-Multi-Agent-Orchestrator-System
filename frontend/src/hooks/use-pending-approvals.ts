"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { fetchPendingApprovals, submitApprovalAction } from "@/lib/api-client";
import { queryKeys } from "@/lib/query-keys";
import type { ApprovalItem } from "@/lib/types";

function isBlockedReply(item: ApprovalItem) {
  return (item.proposal_type ?? "").toLowerCase().includes("reply") && !item.held_reply_id;
}

export function usePendingApprovals(initialData: ApprovalItem[]) {
  return useQuery({
    queryKey: queryKeys.approvals.pending(),
    queryFn: fetchPendingApprovals,
    initialData,
    refetchInterval: 10_000,
  });
}

export function useApprovalMutations() {
  const queryClient = useQueryClient();

  const mutateAction = useMutation({
    mutationFn: async ({ action, item }: { action: "approve" | "reject"; item: ApprovalItem }) => {
      if (isBlockedReply(item)) {
        throw new Error("Reply approvals are blocked until the backend exposes a held reply id.");
      }

      return submitApprovalAction({ action, item });
    },
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: queryKeys.approvals.pending() }),
        queryClient.invalidateQueries({ queryKey: queryKeys.ownerDashboard.summary() }),
        queryClient.invalidateQueries({ queryKey: queryKeys.memory.overview() }),
      ]);
    },
  });

  return {
    approve: async (item: ApprovalItem) => {
      await mutateAction.mutateAsync({ action: "approve", item });
    },
    reject: async (item: ApprovalItem) => {
      await mutateAction.mutateAsync({ action: "reject", item });
    },
    loadingId: mutateAction.variables?.item.id ?? null,
    loadingAction: mutateAction.variables?.action ?? null,
    isPending: mutateAction.isPending,
  };
}

export function getApprovalBlockReason(item: ApprovalItem) {
  if (isBlockedReply(item)) {
    return "Reply actions are waiting on backend support for held reply IDs.";
  }

  return null;
}
