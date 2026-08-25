import { getStoredTokens, persistTokens, type AuthTokens } from "@/stores/auth";

const API_ROOT = process.env.NEXT_PUBLIC_API_ROOT ?? "/api/v1";

export class ApiClientError extends Error {
  constructor(public code: string, message: string, public status: number) { super(message); }
}

export async function apiClient<T>(path: string, init?: RequestInit): Promise<T> {
  const tokens = getStoredTokens();
  const request = (accessToken?: string) => fetch(`${API_ROOT}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}), ...(init?.headers ?? {}) },
  });
  let response = await request(tokens?.access_token);
  if (response.status === 401 && tokens?.refresh_token && !path.startsWith("/auth/")) {
    const refreshed = await fetch(`${API_ROOT}/auth/refresh`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: tokens.refresh_token }),
    });
    if (refreshed.ok) {
      const body = await refreshed.json();
      const nextTokens = body.data as AuthTokens;
      persistTokens(nextTokens);
      response = await request(nextTokens.access_token);
    } else {
      persistTokens(null);
    }
  }
  const payload = await response.json().catch(() => ({}));
  if (!response.ok || payload.success === false) throw new ApiClientError(payload.error?.code ?? "HTTP_ERROR", payload.error?.message ?? `HTTP ${response.status}`, response.status);
  return payload.data as T;
}

export { API_ROOT };
