"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { fetchMemoryOverview, updateDailyDigestItem, updateOwnerMemoryRule } from "@/lib/api-client";
import { queryKeys } from "@/lib/query-keys";
import type { DailyDigestInput, MemoryOverviewPayload } from "@/lib/types";

export function useMemoryOverview(initialData: MemoryOverviewPayload) {
  return useQuery({
    queryKey: queryKeys.memory.overview(),
    queryFn: fetchMemoryOverview,
    initialData,
    refetchInterval: 30_000,
  });
}

export function useMemoryMutations() {
  const queryClient = useQueryClient();

  const ruleMutation = useMutation({
    mutationFn: ({ ruleId, content }: { ruleId: string; content: string }) => updateOwnerMemoryRule(ruleId, content),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: queryKeys.memory.overview() });
    },
  });

  const digestMutation = useMutation({
    mutationFn: ({ digestId, payload }: { digestId: string; payload: DailyDigestInput }) =>
      updateDailyDigestItem(digestId, payload),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: queryKeys.memory.overview() });
      await queryClient.invalidateQueries({ queryKey: queryKeys.dailyDigest.list() });
    },
  });

  return {
    saveOwnerRule: async (ruleId: string, content: string) => {
      await ruleMutation.mutateAsync({ ruleId, content });
    },
    saveDailyDigest: async (digestId: string, payload: DailyDigestInput) => {
      await digestMutation.mutateAsync({ digestId, payload });
    },
    isSavingRule: ruleMutation.isPending,
    isSavingDigest: digestMutation.isPending,
  };
}
