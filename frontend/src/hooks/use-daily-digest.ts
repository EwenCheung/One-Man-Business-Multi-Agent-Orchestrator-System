"use client";

import { useQuery } from "@tanstack/react-query";
import { fetchDailyDigest } from "@/lib/api-client";
import { queryKeys } from "@/lib/query-keys";
import type { DailyDigestPayload } from "@/lib/types";

export function useDailyDigest(initialData: DailyDigestPayload) {
  return useQuery({
    queryKey: queryKeys.dailyDigest.list(),
    queryFn: fetchDailyDigest,
    initialData,
    refetchInterval: 30_000,
  });
}
