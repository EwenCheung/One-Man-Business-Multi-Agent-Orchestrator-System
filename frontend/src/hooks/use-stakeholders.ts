"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  createStakeholder,
  deleteStakeholder,
  fetchStakeholders,
  switchStakeholderRole,
  updateStakeholder,
} from "@/lib/api-client";
import { queryKeys } from "@/lib/query-keys";
import type { StakeholderInput, StakeholderRole, StakeholderRow, StakeholderSwitchInput } from "@/lib/types";

export function useStakeholders(role: StakeholderRole, initialData: StakeholderRow[]) {
  return useQuery({
    queryKey: queryKeys.stakeholders.byRole(role),
    queryFn: () => fetchStakeholders(role),
    initialData,
    refetchInterval: 30_000,
  });
}

export function useStakeholderMutations(role: StakeholderRole) {
  const queryClient = useQueryClient();

  async function invalidate(roleToRefresh?: StakeholderRole) {
    await queryClient.invalidateQueries({ queryKey: queryKeys.stakeholders.byRole(role) });
    if (roleToRefresh && roleToRefresh !== role) {
      await queryClient.invalidateQueries({ queryKey: queryKeys.stakeholders.byRole(roleToRefresh) });
    }
    await queryClient.invalidateQueries({ queryKey: queryKeys.ownerDashboard.summary() });
  }

  const createMutation = useMutation({
    mutationFn: (payload: StakeholderInput) => createStakeholder(role, payload),
    onSuccess: async () => invalidate(),
  });

  const updateMutation = useMutation({
    mutationFn: ({ stakeholderId, payload }: { stakeholderId: string; payload: StakeholderInput }) =>
      updateStakeholder(role, stakeholderId, payload),
    onSuccess: async () => invalidate(),
  });

  const deleteMutation = useMutation({
    mutationFn: (stakeholderId: string) => deleteStakeholder(role, stakeholderId),
    onSuccess: async () => invalidate(),
  });

  const switchMutation = useMutation({
    mutationFn: (payload: StakeholderSwitchInput) => switchStakeholderRole(payload),
    onSuccess: async (_, variables) => invalidate(variables.targetRole),
  });

  return {
    createStakeholder: async (payload: StakeholderInput) => createMutation.mutateAsync(payload),
    updateStakeholder: async (stakeholderId: string, payload: StakeholderInput) =>
      updateMutation.mutateAsync({ stakeholderId, payload }),
    deleteStakeholder: async (stakeholderId: string) => deleteMutation.mutateAsync(stakeholderId),
    switchStakeholder: async (payload: StakeholderSwitchInput) => switchMutation.mutateAsync(payload),
    isCreating: createMutation.isPending,
    isUpdating: updateMutation.isPending,
    isDeleting: deleteMutation.isPending,
    isSwitching: switchMutation.isPending,
  };
}
