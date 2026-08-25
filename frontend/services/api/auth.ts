import { apiClient } from "./client";
import type { AuthTokens } from "@/stores/auth";

type Credentials = { email: string; password: string };

export const authApi = {
  login: (credentials: Credentials) => apiClient<AuthTokens>("/auth/login", { method: "POST", body: JSON.stringify(credentials) }),
  register: (credentials: Credentials) => apiClient<AuthTokens>("/auth/register", { method: "POST", body: JSON.stringify(credentials) }),
  logout: (refreshToken: string) => apiClient<{ revoked: boolean }>("/auth/logout", { method: "POST", body: JSON.stringify({ refresh_token: refreshToken }) }),
};
