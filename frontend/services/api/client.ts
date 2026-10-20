import { getStoredTokens, persistTokens, type AuthTokens } from "@/stores/auth";

const API_ROOT = process.env.NEXT_PUBLIC_API_ROOT ?? "/api/v1";

export class ApiClientError extends Error {
  constructor(public code: string, message: string, public status: number) { super(message); }
}

let refreshing: Promise<AuthTokens | null> | null = null;

export async function authenticatedFetch(path: string, init?: RequestInit): Promise<Response> {
  const tokens = getStoredTokens();
  const request = (accessToken?: string) => {
    const headers = new Headers(init?.headers);
    if (!(init?.body instanceof FormData) && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");
    if (accessToken) headers.set("Authorization", `Bearer ${accessToken}`);
    return fetch(`${API_ROOT}${path}`, { ...init, headers });
  };
  let response = await request(tokens?.access_token);
  if (response.status === 401 && tokens?.refresh_token && !path.startsWith("/auth/")) {
    if (!refreshing) refreshing = (async () => {
      const refreshed = await fetch(`${API_ROOT}/auth/refresh`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh_token: tokens.refresh_token }),
      });
      const next = refreshed.ok ? (await refreshed.json()).data as AuthTokens : null;
      if (getStoredTokens()?.refresh_token !== tokens.refresh_token) return null;
      persistTokens(next);
      return next;
    })().finally(() => { refreshing = null; });
    const next = await refreshing;
    if (next && getStoredTokens()?.access_token === next.access_token) response = await request(next.access_token);
  }
  return response;
}

export async function apiClient<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await authenticatedFetch(path, init);
  const payload = await response.json().catch(() => ({}));
  if (!response.ok || payload.success === false) throw new ApiClientError(payload.error?.code ?? "HTTP_ERROR", payload.error?.message ?? `HTTP ${response.status}`, response.status);
  return payload.data as T;
}

export async function downloadFile(path: string, filename: string) {
  const response = await authenticatedFetch(path);
  if (!response.ok) throw new ApiClientError("DOWNLOAD_FAILED", `HTTP ${response.status}`, response.status);
  const url = URL.createObjectURL(await response.blob());
  const link = document.createElement("a");
  link.href = url; link.download = filename; link.click();
  URL.revokeObjectURL(url);
}

export { API_ROOT };
