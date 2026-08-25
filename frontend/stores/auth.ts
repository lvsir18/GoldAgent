"use client";

import { create } from "zustand";

export type AuthTokens = {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
};

const STORAGE_KEY = "goldagent.auth";

export function getStoredTokens(): AuthTokens | null {
  if (typeof window === "undefined") return null;
  try { return JSON.parse(window.localStorage.getItem(STORAGE_KEY) ?? "null") as AuthTokens | null; }
  catch { return null; }
}

export function persistTokens(tokens: AuthTokens | null) {
  if (typeof window === "undefined") return;
  if (tokens) window.localStorage.setItem(STORAGE_KEY, JSON.stringify(tokens));
  else window.localStorage.removeItem(STORAGE_KEY);
}

type AuthState = {
  tokens: AuthTokens | null;
  hydrated: boolean;
  hydrate: () => void;
  setTokens: (tokens: AuthTokens | null) => void;
};

export const useAuthStore = create<AuthState>(set => ({
  tokens: null,
  hydrated: false,
  hydrate: () => set({ tokens: getStoredTokens(), hydrated: true }),
  setTokens: tokens => { persistTokens(tokens); set({ tokens }); },
}));
