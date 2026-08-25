import { apiClient } from "./client";
import type { MarketPoint, MarketSummary, SourceMetadata, TechnicalSnapshot } from "@/types/api";
export const marketApi = {
  summary: () => apiClient<MarketSummary>("/market/summary"),
  history: (limit = 500) => apiClient<{ points: MarketPoint[]; metadata: SourceMetadata }>(`/market/history?limit=${limit}`),
  indicators: () => apiClient<TechnicalSnapshot>("/market/indicators"),
  refresh: () => apiClient<{ status: string }>("/market/refresh", { method: "POST" }),
};
