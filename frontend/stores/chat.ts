"use client";

import { create } from "zustand";
import { sessionsApi, streamChat } from "@/services/api/chat";
import { useAuthStore } from "@/stores/auth";
import type { Session } from "@/types/api";

export type ChatMessage = { role: "user" | "assistant"; content: string };
type Activity = { tool: string; success: boolean | null };
type Progress = { stage: string; tool?: string; success?: boolean };
type Notice = "" | "completed" | "incomplete" | "stopped";
type ChatState = {
  sessions: Session[];
  sessionId: string | null;
  messages: ChatMessage[];
  busy: boolean;
  activities: Activity[];
  activityNote: "idle" | "deciding" | "no-tools";
  error: string | null;
  progress: Progress;
  runId: string;
  evidence: any;
  notice: Notice;
  mode: string;
  refresh: () => Promise<void>;
  select: (id: string) => Promise<void>;
  newChat: () => void;
  send: (question: string, mode: string) => Promise<void>;
  stop: () => void;
  reset: () => void;
};

const empty = () => ({ sessions: [] as Session[], sessionId: null, messages: [] as ChatMessage[], busy: false,
  activities: [] as Activity[], activityNote: "idle" as const, error: null, progress: { stage: "" },
  runId: "", evidence: null, notice: "" as Notice, mode: "quick" });
let controller: AbortController | null = null;
let generation = 0;

/** Tab-scoped runtime. Route unmounts are deliberately NOT cancellation events. */
export const useChatStore = create<ChatState>((set, get) => ({
  ...empty(),
  refresh: async () => {
    const version = generation;
    const sessions = await sessionsApi.list();
    if (version === generation) set({ sessions });
  },
  select: async id => {
    if (get().busy) return;
    const version = ++generation;
    const history = await sessionsApi.messages(id);
    if (version !== generation) return;
    set({ sessionId: id, messages: history.map(m => ({ role: m.role as ChatMessage["role"], content: m.content })),
      activities: [], activityNote: "idle", error: null, progress: { stage: "" }, runId: "", evidence: null, notice: "" });
  },
  newChat: () => {
    if (get().busy) return;
    generation++;
    set({ ...empty(), sessions: get().sessions });
  },
  reset: () => {
    generation++;
    controller?.abort(); controller = null;
    set(empty());
  },
  stop: () => controller?.abort(),
  send: async (question, mode) => {
    question = question.trim();
    if (!question || get().busy) return;
    const version = ++generation;
    const current = () => generation === version;
    const abort = new AbortController();
    controller = abort;
    set(state => ({ busy: true, mode, error: null, progress: { stage: "starting" }, runId: "", evidence: null, notice: "",
      activities: [], activityNote: "deciding", messages: [...state.messages, { role: "user", content: question }, { role: "assistant", content: "" }] }));
    let finished = false;
    let toolCount = 0;
    try {
      let id = get().sessionId;
      if (!id) {
        const session = await sessionsApi.create(question.slice(0,36));
        if (!current()) return;
        id = session.id;
        set(state => ({ sessionId: id, sessions: [session, ...state.sessions.filter(s => s.id !== id)] }));
      }
      if (abort.signal.aborted) throw new DOMException("Stopped", "AbortError");
      await streamChat(question, id, (event, payload) => {
        if (!current()) return;
        if (event === "run_started") set({ runId: String(payload.run_id ?? ""), progress: { stage: "starting" } });
        if (event === "run_progress") set({ progress: { stage: String(payload.stage ?? "waiting") } });
        if (event === "tool_started") {
          const tool = String(payload.tool); toolCount++;
          set(state => ({ activityNote: "idle", progress: { stage: "tool_started", tool }, activities: [...state.activities, { tool, success: null }] }));
        }
        if (event === "tool_finished") {
          const tool = String(payload.tool), success = Boolean(payload.success);
          set(state => {
            const activities = [...state.activities];
            let index = -1;
            for (let i = activities.length - 1; i >= 0; i--) if (activities[i].tool === tool && activities[i].success === null) { index = i; break; }
            if (index >= 0) activities[index] = { tool, success }; else activities.push({ tool, success });
            return { activities, progress: { stage: "tool_finished", tool, success } };
          });
        }
        if (event === "answer_delta") set(state => {
          const messages = [...state.messages];
          const last = messages.at(-1)!;
          messages[messages.length - 1] = { ...last, content: last.content + String(payload.delta ?? "") };
          return { messages, progress: { stage: "answer" } };
        });
        if (event === "run_finished") {
          finished = true;
          set({ runId: String(payload.run_id ?? ""), sessionId: String(payload.session_id ?? id), evidence: payload.evidence ?? null,
            activityNote: toolCount === 0 ? "no-tools" : "idle", notice: payload.status === "completed" ? "completed" : "incomplete" });
        }
        if (event === "error") {
          finished = true;
          set({ error: String(payload.message ?? "Agent run failed"), activityNote: "idle" });
        }
      }, { signal: abort.signal, mode });
      if (current() && !finished) set({ error: "Connection closed before the research finished. Check task history before retrying." });
    } catch (error) {
      if (current()) set((error as Error).name === "AbortError" ? { notice: "stopped", activityNote: "idle" } : { error: (error as Error).message, activityNote: "idle" });
    } finally {
      if (current()) {
        controller = null;
        set({ busy: false, progress: { stage: "" } });
        get().refresh().catch(error => { if (current()) set({ error: error.message }); });
      }
    }
  },
}));

function subject(token?: string): string {
  if (!token) return "demo";
  try { return JSON.parse(atob(token.split(".")[1].replace(/-/g,"+").replace(/_/g,"/"))).sub ?? token; }
  catch { return token; }
}
// Switching identity is a cancellation boundary; navigating features is not.
useAuthStore.subscribe((state, previous) => {
  if (subject(state.tokens?.access_token) !== subject(previous.tokens?.access_token)) useChatStore.getState().reset();
});
