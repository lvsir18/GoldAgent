import { expect, test, type Page, type Route } from "@playwright/test";

const ok = (route: Route, data: unknown) => route.fulfill({
  status: 200,
  contentType: "application/json",
  body: JSON.stringify({ success: true, data, meta: {} }),
});

async function mockApi(page: Page) {
  let documents = [{ id: "document-1", filename: "gold-notes.md", status: "ready", metadata: { chunk_count: 2, embedding_provider: "fixture" } }];
  await page.route("**/api/v1/**", async route => {
    const url = new URL(route.request().url());
    const path = url.pathname;
    if (path.endsWith("/market/summary")) return ok(route, { price: 525, change_1d_pct: 1, change_1w_pct: 2, change_1m_pct: 3, metadata: { source: "fixture", source_type: "simulation", is_derived: false, is_cached: false, is_stale: false, retrieved_at: new Date().toISOString(), currency: "CNY", market: "CN", symbol: "AU0" } });
    if (path.endsWith("/market/history")) return ok(route, { points: [{ timestamp: new Date().toISOString(), open: 520, high: 530, low: 518, close: 525, volume: 1000 }], metadata: { source: "fixture" } });
    if (path.endsWith("/market/indicators")) return ok(route, { rsi: 55, macd: 1, trend: "uptrend", volatility: 0.01, support: 500, resistance: 540, metadata: { source: "fixture", source_type: "simulation", is_derived: false, is_cached: false, is_stale: false, retrieved_at: new Date().toISOString(), currency: "CNY", market: "CN", symbol: "AU0" } });
    if (path.endsWith("/sessions") && route.request().method() === "GET") return ok(route, []);
    if (path.endsWith("/sessions") && route.request().method() === "POST") return ok(route, { id: "session-1", title: "新会话", status: "active", created_at: new Date().toISOString(), updated_at: new Date().toISOString() });
    if (path.endsWith("/sessions/session-1/messages")) return ok(route, []);
    if (path.endsWith("/chat/stream")) return route.fulfill({ status: 200, contentType: "text/event-stream", body: 'event: answer_delta\ndata: {"delta":"测试回答"}\n\nevent: run_finished\ndata: {"session_id":"session-1","status":"completed"}\n\n' });
    if (path.endsWith("/forecasts")) return ok(route, { id: "forecast-1", current_price: 525, predicted_prices: [526, 527], metrics: { mae: 1, rmse: 1.2, direction_accuracy: 0.6 }, disclaimer: "Model estimate" });
    if (path.endsWith("/backtests") && route.request().method() === "POST") return ok(route, { id: "backtest-1", status: "queued" });
    if (path.endsWith("/backtests/backtest-1")) return ok(route, { id: "backtest-1", status: "completed", result: { metrics: { cumulative_return: 0.1 }, trades: [] } });
    if (path.endsWith("/portfolio") && route.request().method() === "GET") return ok(route, { grams: 20, average_cost: 500, planned_investment: 1000 });
    if (path.endsWith("/portfolio") && route.request().method() === "PUT") return ok(route, { grams: 20, average_cost: 500, planned_investment: 1000 });
    if (path.includes("/portfolio/analysis")) return ok(route, { market_value: 10500, cost_basis: 10000, pnl: 500, pnl_pct: 5, break_even_price: 500, risk_level: "balanced" });
    if (path.endsWith("/knowledge/documents") && route.request().method() === "GET") return ok(route, documents);
    if (path.endsWith("/knowledge/documents/document-1") && route.request().method() === "DELETE") { documents = []; return ok(route, { deleted: true }); }
    if (path.endsWith("/users/me") && route.request().method() === "GET") return ok(route, { id: "user-1", email: "demo@goldagent.local", profile: null, risk_profile: null });
    if (path.endsWith("/users/me/profile") || path.endsWith("/users/me/risk-profile")) return ok(route, {});
    if (path.endsWith("/reports")) return ok(route, []);
    return ok(route, []);
  });
}

test.beforeEach(async ({ page }) => mockApi(page));

test("dashboard and core workbenches complete their primary flows", async ({ page }) => {
  await page.goto("/dashboard");
  await expect(page.getByRole("heading", { name: "黄金市场 Dashboard" })).toBeVisible();
  await expect(page.getByText("¥525.00/g")).toBeVisible();

  await page.goto("/chat");
  await page.getByRole("button", { name: "新建会话" }).click();
  await page.getByPlaceholder("询问行情、新闻、预测、持仓或回测…").fill("分析黄金");
  await page.getByRole("button", { name: "发送" }).click();
  await expect(page.getByText("测试回答")).toBeVisible();

  await page.goto("/forecast");
  await page.getByRole("button", { name: "运行预测" }).click();
  await expect(page.getByText("T+1 · 526.00")).toBeVisible();

  await page.goto("/backtest");
  await page.getByRole("button", { name: "运行回测" }).click();
  await expect(page.getByText("累计收益率")).toBeVisible();

  await page.goto("/portfolio");
  await page.getByLabel("当前参考价").fill("525");
  await page.getByRole("button", { name: "保存并分析" }).click();
  const breakEvenCard = page.getByText("盈亏平衡", { exact: true }).locator("..");
  await expect(breakEvenCard.getByText("500", { exact: true })).toBeVisible();

  await page.goto("/reports");
  await expect(page.getByRole("heading", { name: "分析报告" })).toBeVisible();

  await page.goto("/knowledge");
  await expect(page.getByText("gold-notes.md")).toBeVisible();
  page.once("dialog", dialog => dialog.accept());
  await page.getByRole("button", { name: "删除文档：gold-notes.md" }).click();
  await expect(page.getByText("gold-notes.md")).not.toBeVisible();

  await page.goto("/settings");
  await expect(page.getByRole("heading", { name: "个性化设置" })).toBeVisible();
  await page.getByRole("button", { name: "保存个性化设置" }).click();
  await expect(page.getByText("已保存，将在下一次 Agent 对话中生效。")).toBeVisible();
});
