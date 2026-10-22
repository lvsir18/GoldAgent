import React from "react";
import { act, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { useChatStore } from "@/stores/chat";
import { useAuthStore } from "@/stores/auth";
import { streamChat } from "@/services/api/chat";

vi.mock("@/services/api/chat", () => ({
  sessionsApi: { create: vi.fn(async () => ({id:"s1",title:"Question"})), list: vi.fn(async () => [{id:"s1",title:"Question"}]), messages: vi.fn(async () => []) },
  streamChat: vi.fn(),
}));
afterEach(() => { useChatStore.getState().reset(); useAuthStore.getState().setTokens(null); vi.clearAllMocks(); });

function View() {
  const { busy, messages } = useChatStore();
  return <div>{busy ? "running" : "idle"}{messages.map(m => m.content).join("|")}</div>;
}

describe("route-independent chat runtime", () => {
  it("continues after the page unmounts and restores the answer on return", async () => {
    let emit!: Parameters<typeof streamChat>[2], finish!: () => void;
    let signal!: AbortSignal;
    vi.mocked(streamChat).mockImplementation(async (_,__,callback,options) => {
      emit = callback; signal = options!.signal!;
      await new Promise<void>(resolve => { finish = resolve; });
    });
    const view = render(<View/>);
    let execution!: Promise<void>;
    await act(async () => { execution = useChatStore.getState().send("Question", "deep"); });
    expect(screen.getByText(/running/)).toBeInTheDocument();
    view.unmount();
    expect(signal.aborted).toBe(false);
    emit("answer_delta", {delta:"completed off-page"});
    emit("run_finished", {run_id:"r1",session_id:"s1",status:"completed"});
    finish(); await execution;
    render(<View/>);
    expect(screen.getByText(/completed off-page/)).toBeInTheDocument();
    expect(useChatStore.getState().busy).toBe(false);
    expect(useChatStore.getState().mode).toBe("deep");
  });

  it("still cancels when Stop is explicitly requested", async () => {
    vi.mocked(streamChat).mockImplementation(async (_,__,___,options) => {
      await new Promise<void>((_,reject) => options!.signal!.addEventListener("abort", () => reject(new DOMException("Stopped","AbortError")), {once:true}));
    });
    const execution = useChatStore.getState().send("Question", "quick");
    await Promise.resolve();
    useChatStore.getState().stop();
    await execution;
    expect(useChatStore.getState().busy).toBe(false);
    expect(useChatStore.getState().notice).toBe("stopped");
  });

  it("cancels and clears state on identity changes; ignores late callbacks", async () => {
    let emit!: Parameters<typeof streamChat>[2];
    vi.mocked(streamChat).mockImplementation(async (_,__,callback,options) => {
      emit = callback;
      await new Promise<void>((_,reject) => options!.signal!.addEventListener("abort", () => reject(new DOMException("Stopped","AbortError")), {once:true}));
    });
    const execution = useChatStore.getState().send("private question", "deep");
    await Promise.resolve();
    useAuthStore.getState().setTokens({access_token:"other-user",refresh_token:"other",token_type:"bearer",expires_in:60});
    emit("answer_delta", {delta:"must not leak"});
    await execution;
    expect(useChatStore.getState().messages).toEqual([]);
    expect(useChatStore.getState().busy).toBe(false);
  });
});
