import { useQuery } from "@tanstack/react-query";
import { apiGet } from "@/shared/services/client";
import type { HealthResponse } from "@/shared/types/api";

export function useHealth() {
  return useQuery({ queryKey: ["health"], queryFn: ({ signal }) => apiGet<HealthResponse>("/health", signal) });
}
