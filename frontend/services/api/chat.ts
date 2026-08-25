import { API_ROOT, apiClient } from "./client";
import type { Session } from "@/types/api";

export const sessionsApi = {
  list: () => apiClient<Session[]>("/sessions"),
  create: (title = "新会话") => apiClient<Session>("/sessions", { method: "POST", body: JSON.stringify({ title }) }),
  messages: (id: string) => apiClient<Array<{ id: string; role: string; content: string; created_at: string }>>(`/sessions/${id}/messages`),
  rename: (id: string, title: string) => apiClient<Session>(`/sessions/${id}`, { method: "PATCH", body: JSON.stringify({ title }) }),
  remove: (id: string) => apiClient<{ deleted: boolean }>(`/sessions/${id}`, { method: "DELETE" }),
};

export async function streamChat(message: string, sessionId: string | null, onEvent: (event: string, payload: Record<string, unknown>) => void) {
  const response = await fetch(`${API_ROOT}/chat/stream`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ message, session_id: sessionId }) });
  if (!response.ok || !response.body) throw new Error(`Chat stream failed: HTTP ${response.status}`);
  const reader = response.body.getReader(); const decoder = new TextDecoder(); let buffer = "";
  const parse = (block: string) => { let event = "message", data = "{}"; for (const line of block.split("\n")) { if (line.startsWith("event:")) event = line.slice(6).trim(); if (line.startsWith("data:")) data = line.slice(5).trim(); } try { onEvent(event, JSON.parse(data)); } catch { onEvent("error", { message: "Invalid SSE payload" }); } };
  while (true) { const { value, done } = await reader.read(); if (done) break; buffer += decoder.decode(value, { stream: true }); const parts = buffer.split("\n\n"); buffer = parts.pop() ?? ""; parts.forEach(parse); }
  if (buffer.trim()) parse(buffer);
}
