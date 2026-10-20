import { afterEach, describe, expect, it, vi } from "vitest";
import { apiClient, authenticatedFetch } from "@/services/api/client";
import { persistTokens } from "@/stores/auth";
import { streamChat } from "@/services/api/chat";

const tokens = { access_token: "old", refresh_token: "refresh", token_type: "bearer", expires_in: 60 };
afterEach(() => { localStorage.clear(); vi.unstubAllGlobals(); });

describe("one authenticated identity across REST and SSE", () => {
  it("single-flights concurrent token refresh and retries both requests", async () => {
    persistTokens(tokens);
    let refreshes = 0;
    vi.stubGlobal("fetch", vi.fn(async (url: string, init: RequestInit) => {
      if (url.endsWith("/auth/refresh")) { refreshes++; return new Response(JSON.stringify({ data: { ...tokens, access_token: "new" } })); }
      if (new Headers(init.headers).get("Authorization") !== "Bearer new") return new Response("", { status: 401 });
      return new Response(JSON.stringify({ success: true, data: "ok" }));
    }));
    expect(await Promise.all([apiClient("/portfolio"), apiClient("/reports")])).toEqual(["ok", "ok"]);
    expect(refreshes).toBe(1);
  });

  it("authenticates chat and parses CRLF SSE without losing split UTF-8", async () => {
    persistTokens(tokens);
    const events: unknown[] = [];
    const encoder = new TextEncoder();
    const bytes = encoder.encode('event: answer_delta\r\ndata: {"delta":"黄金"}\r\n\r\n');
    const fetchMock = vi.fn(async (_url: string, _init: RequestInit) => new Response(new ReadableStream({ start(controller) { for (const byte of bytes) controller.enqueue(new Uint8Array([byte])); controller.close(); } })));
    vi.stubGlobal("fetch", fetchMock);
    await streamChat("test", null, (event,payload) => events.push([event,payload]));
    expect(events).toEqual([["answer_delta", { delta: "黄金" }]]);
    const init = (fetchMock.mock.calls as unknown as [string,RequestInit][])[0][1];
    expect(new Headers(init.headers).get("Authorization")).toBe("Bearer old");
  });

  it("does not replace a newly signed-in account when an old refresh finishes", async () => {
    persistTokens(tokens);
    vi.stubGlobal("fetch", vi.fn(async (url: string) => {
      if (url.endsWith("/auth/refresh")) { persistTokens({ ...tokens, access_token: "other-user", refresh_token: "other-refresh" }); return new Response(JSON.stringify({data:{...tokens,access_token:"new"}})); }
      return new Response("", {status:401});
    }));
    expect((await authenticatedFetch("/reports")).status).toBe(401);
    expect(JSON.parse(localStorage.getItem("goldagent.auth")!).access_token).toBe("other-user");
  });
});
