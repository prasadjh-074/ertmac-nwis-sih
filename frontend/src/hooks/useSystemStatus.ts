import { useQuery } from "@tanstack/react-query";
import { apiGet } from "@/lib/api";
import type { RootStatus, StatusCheck } from "@/api/types";

export function useApiRootStatus(enabled: boolean) {
  return useQuery({
    queryKey: ["api-root-status"],
    queryFn: () => apiGet<RootStatus>("/"),
    enabled,
    retry: false,
    staleTime: 30_000,
  });
}

export function useStatusChecks(enabled: boolean) {
  return useQuery({
    queryKey: ["status-checks"],
    queryFn: () => apiGet<StatusCheck[]>("/status"),
    enabled,
    retry: false,
    staleTime: 30_000,
  });
}