"use client";

import { useQuery } from "@tanstack/react-query";
import { fetchOwnerDashboard } from "@/lib/api-client";
import { queryKeys } from "@/lib/query-keys";
import type { DashboardPayload } from "@/lib/types";

export function useOwnerDashboard(initialData: DashboardPayload) {
  return useQuery({
    queryKey: queryKeys.ownerDashboard.summary(),
    queryFn: fetchOwnerDashboard,
    initialData,
    refetchInterval: 30_000,
  });
}
