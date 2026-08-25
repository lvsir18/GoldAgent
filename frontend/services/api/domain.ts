import { apiClient } from "./client";

export const forecastApi = {
  create: (body: { symbol: string; horizon: number; model: string; lookback?: number }) => apiClient<any>("/forecasts", { method: "POST", body: JSON.stringify(body) }),
  get: (id: string) => apiClient<any>(`/forecasts/${id}`),
};
export const backtestApi = {
  create: (body: Record<string, unknown>) => apiClient<{ id: string; status: string }>("/backtests", { method: "POST", body: JSON.stringify(body) }),
  list: () => apiClient<any[]>("/backtests"),
  get: (id: string) => apiClient<any>(`/backtests/${id}`),
};
export const portfolioApi = {
  get: () => apiClient<any>("/portfolio"),
  update: (body: Record<string, unknown>) => apiClient<any>("/portfolio", { method: "PUT", body: JSON.stringify(body) }),
  analysis: (price: number) => apiClient<any>(`/portfolio/analysis?current_price=${price}`),
};
export const newsApi = { list: (query: string) => apiClient<any>(`/news?query=${encodeURIComponent(query)}`) };
export const reportsApi = {
  list: () => apiClient<any[]>("/reports"),
  create: (body: Record<string, unknown>) => apiClient<any>("/reports", { method: "POST", body: JSON.stringify(body) }),
  remove: (id: string) => apiClient<any>(`/reports/${id}`, { method: "DELETE" }),
};
export const userApi = {
  me: () => apiClient<any>("/users/me"),
  updateProfile: (body: Record<string, unknown>) => apiClient<any>("/users/me/profile", { method: "PUT", body: JSON.stringify(body) }),
  updateRisk: (body: Record<string, unknown>) => apiClient<any>("/users/me/risk-profile", { method: "PUT", body: JSON.stringify(body) }),
};
export const knowledgeApi = {
  list: () => apiClient<any[]>("/knowledge/documents"),
  upload: async (file: File) => {
    const form = new FormData(); form.append("file", file);
    const response = await fetch(`${process.env.NEXT_PUBLIC_API_ROOT ?? "/api/v1"}/knowledge/documents`, { method: "POST", body: form });
    const payload = await response.json(); if (!response.ok || payload.success === false) throw new Error(payload.error?.message ?? "Upload failed"); return payload.data;
  },
  search: (query: string, top_k = 5) => apiClient<any[]>("/knowledge/search", { method: "POST", body: JSON.stringify({ query, top_k }) }),
  remove: (id: string) => apiClient<any>(`/knowledge/documents/${id}`, { method: "DELETE" }),
};
