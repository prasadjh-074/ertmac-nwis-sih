import { useQuery } from "@tanstack/react-query";
import { getHealth } from "@/api/health";

export function useHealth(refetchInterval: number | false = 30_000) {
  return useQuery({
    queryKey: ["health"],
    queryFn: getHealth,
    refetchInterval,
    staleTime: 10_000,
    retry: 0,
  });
}
