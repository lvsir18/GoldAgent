import { expect, test, type Page, type Route } from "@playwright/test";

const ok = (route: Route, data: unknown) => route.fulfill({
  status: 200,
  contentType: "application/json",
  body: JSON.stringify({ success: true, data, meta: {} }),
});

async function mockApi(page: Page) {
  const forecast = { id: "forecast-1", request: { symbol: "AU0", model: "linear", horizon: 2 }, created_at: new Date().toISOString(), current_price: 525, predicted_prices: [526, 527], metrics: { mae: 1, rmse: 1.2, direction_accuracy: 0.6, horizon: 2, sample_count: 10, min_train: 30, baseline_mae: 2 }, metadata: {source:"fixture",source_type:"simulation",retrieved_at:new Date().toISOString()} };
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
    if (path.endsWith("/chat/stream")) return route.fulfill({ status: 200, contentType: "text/event-stream", body: 'event: answer_delta\ndata: {"delta":"测试回答"}\n\nevent: run_finished\ndata: {"run_id":"run-1","session_id":"session-1","status":"completed","evidence":{"citations":[],"snapshots":[],"limitations":[]}}\n\n' });
    if (path.endsWith("/forecasts") && route.request().method() === "GET") return ok(route, [forecast]);
    if (path.endsWith("/forecasts") || path.endsWith("/forecasts/forecast-1")) return ok(route, forecast);
    if (path.endsWith("/backtests") && route.request().method() === "GET") return ok(route, [{id:"backtest-1",status:"completed",created_at:new Date().toISOString()}]);
    if (path.endsWith("/backtests") && route.request().method() === "POST") return ok(route, { id: "backtest-1", status: "queued" });
    if (path.endsWith("/backtests/backtest-1")) return ok(route, { id: "backtest-1", status: "completed", result: { metrics: { cumulative_return: 0.1 }, trades: [], equity_curve:[{timestamp:"2026-01-01",value:100000},{timestamp:"2026-02-01",value:110000}], drawdown_curve:[{timestamp:"2026-01-01",value:0},{timestamp:"2026-02-01",value:-0.02}] } });
    if (path.endsWith("/portfolio") && route.request().method() === "GET") return ok(route, { grams: 20, average_cost: 500, planned_investment: 1000 });
    if (path.endsWith("/portfolio") && route.request().method() === "PUT") return ok(route, { grams: 20, average_cost: 500, planned_investment: 1000 });
    if (path.includes("/portfolio/analysis")) return ok(route, { market_value: 10500, cost_basis: 10000, pnl: 500, pnl_pct: 5, break_even_price: 500, risk_level: "balanced" });
    if (path.endsWith("/knowledge/documents") && route.request().method() === "GET") return ok(route, documents);
    if (path.endsWith("/knowledge/documents/document-1") && route.request().method() === "DELETE") { documents = []; return ok(route, { deleted: true }); }
    if (path.endsWith("/users/me") && route.request().method() === "GET") return ok(route, { id: "user-1", email: "demo@goldagent.local", profile: null, risk_profile: null });
    if (path.endsWith("/users/me/profile") || path.endsWith("/users/me/risk-profile")) return ok(route, {});
    if (path.endsWith("/reports")) return ok(route, []);
    if (path.endsWith("/news")) return ok(route,{ articles:[],query:"gold" });
    return ok(route, []);
  });
}

test.beforeEach(async ({ page }) => mockApi(page));

test("dashboard and core workbenches complete their primary flows", async ({ page }, testInfo) => {
  await page.goto("/dashboard");
  await expect(page.getByRole("heading", { name: "黄金市场仪表盘" })).toBeVisible();
  await expect(page.getByText("¥525.00/g", { exact:true })).toBeVisible();
  await page.screenshot({path:testInfo.outputPath("dashboard.png"),fullPage:true});

  await page.goto("/chat");
  await page.getByRole("button", { name: "新会话", exact:true }).click();
  await page.getByPlaceholder("询问行情、新闻、预测、持仓或回测…").fill("分析黄金");
  await page.getByRole("button", { name: "发送", exact:true }).click();
  await expect(page.getByText("测试回答")).toBeVisible();
  await page.screenshot({path:testInfo.outputPath("chat.png"),fullPage:true});

  await page.goto("/forecast");
  await page.getByRole("button", { name: "运行预测" }).click();
  await expect(page.getByRole("img", { name: "预测路径与价格不变基准" })).toBeVisible();
  await page.reload();
  await expect(page.getByText("滚动样本", { exact:false })).toContainText("10");

  await page.goto("/backtest");
  await page.getByRole("button", { name: "运行回测" }).click();
  await expect(page.getByText("累计收益率")).toBeVisible();
  await page.screenshot({path:testInfo.outputPath("backtest.png"),fullPage:true});

  await page.goto("/portfolio");
  await page.getByLabel("当前参考价").fill("525");
  await page.getByRole("button", { name: "保存并分析" }).click();
  const breakEvenCard = page.getByText("盈亏平衡", { exact: true }).locator("..");
  await expect(breakEvenCard.getByText("500", { exact: true })).toBeVisible();

  await page.goto("/reports");
  await expect(page.getByRole("heading", { name: "研究报告库" })).toBeVisible();

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

test("mobile More exposes every feature and templates only draft questions", async ({ page }, testInfo) => {
  await page.setViewportSize({ width:390, height:844 });
  await page.goto("/chat");
  await page.getByRole("button",{name:"今日简报",exact:false}).click();
  await expect(page.getByRole("textbox")).toHaveValue(/简短晨报/);
  await page.getByRole("button",{name:"更多",exact:true}).click();
  const drawer = page.getByRole("dialog",{name:"全部功能"});
  await expect(drawer.getByRole("link",{name:"知识库",exact:true})).toBeVisible();
  await expect(drawer.getByRole("link",{name:"研究任务",exact:true})).toBeVisible();
  await page.screenshot({path:testInfo.outputPath("mobile-navigation.png"),fullPage:true});
  await drawer.getByRole("link",{name:"设置",exact:true}).click();
  await expect(page).toHaveURL(/\/settings$/);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy();
});

test("chat keeps running across navigation and shows navigation/session indicators", async ({ page }) => {
  let release!: () => void;
  const gate = new Promise<void>(resolve => { release = resolve; });
  let calls = 0;
  await page.route("**/api/v1/chat/stream", async route => {
    calls++;
    await gate;
    await route.fulfill({status:200,contentType:"text/event-stream",body:'event: answer_delta\ndata: {"delta":"离开页面后仍然完成"}\n\nevent: run_finished\ndata: {"run_id":"r-nav","session_id":"session-1","status":"completed"}\n\n'});
  });
  await page.goto("/chat");
  expect((await page.locator("aside").first().boundingBox())?.width).toBeLessThanOrEqual(188);
  await page.getByRole("textbox").fill("后台运行测试");
  await page.getByRole("button",{name:"发送",exact:true}).click();
  await expect(page.getByRole("img",{name:"Agent 正在运行",exact:true}).first()).toBeVisible();
  await page.getByRole("button",{name:"会话历史",exact:true}).click();
  await expect(page.getByRole("img",{name:"会话正在运行",exact:true})).toBeVisible();
  await page.getByRole("link",{name:"市场新闻",exact:true}).click();
  await expect(page).toHaveURL(/\/news$/);
  await expect(page.getByRole("img",{name:"Agent 正在运行",exact:true}).first()).toBeVisible();
  await page.locator('aside nav a[href="/chat"]').click();
  await expect(page.getByRole("button",{name:"停止",exact:true})).toBeVisible();
  release();
  await expect(page.getByText("离开页面后仍然完成",{exact:true})).toBeVisible();
  await expect(page.getByRole("img",{name:"Agent 正在运行",exact:true})).toHaveCount(0);
  expect(calls).toBe(1);
});

test("compact navigation fits English labels without horizontal overflow", async ({ page }) => {
  await page.goto("/dashboard");
  await page.getByRole("button", {name:"EN",exact:true}).click();
  const sidebar = page.locator("aside").first();
  await expect(sidebar.getByRole("link", {name:"Research tasks",exact:true})).toBeVisible();
  expect(await sidebar.evaluate(element => element.scrollWidth <= element.clientWidth)).toBeTruthy();
  expect((await sidebar.boundingBox())?.width).toBeLessThanOrEqual(188);
});

test("a completed chat saves a research report with preview and authenticated download", async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem("goldagent.auth", JSON.stringify({access_token:"isolated-fixture-token",refresh_token:"fixture-refresh",token_type:"bearer",expires_in:60})));
  const report = { id:"report-1",title:"分析黄金",report_type:"analysis",created_at:new Date().toISOString(),content:"# 测试研究\n\n## 研究结论\n\n已核查的模拟结果。" };
  let saved = false;
  let authenticatedDownload = false;
  await page.route("**/api/v1/reports**", async route => {
    const request = route.request();
    expect(request.headers().authorization).toBe("Bearer isolated-fixture-token");
    if (request.url().endsWith("/download")) { authenticatedDownload = true; return route.fulfill({status:200,contentType:"text/plain",body:report.content}); }
    if (request.method() === "POST") { expect(request.postDataJSON().run_id).toBe("run-1"); saved = true; return ok(route,report); }
    return ok(route,request.url().endsWith("/report-1") ? report : saved ? [report] : []);
  });
  await page.goto("/chat");
  await page.getByRole("textbox").fill("分析黄金");
  await page.getByRole("button",{name:"发送",exact:true}).click();
  await expect(page.getByText("测试回答",{exact:true})).toBeVisible();
  await page.getByRole("button",{name:"保存研究报告",exact:true}).click();
  await expect(page.getByRole("status")).toContainText("报告已保存");
  await page.goto("/reports");
  await page.getByRole("button",{name:"预览",exact:true}).click();
  await expect(page.getByRole("heading",{name:"研究结论",exact:true})).toBeVisible();
  const download = page.waitForEvent("download");
  await page.getByRole("button",{name:"下载",exact:true}).click();
  expect((await download).suggestedFilename()).toBe("分析黄金.md");
  expect(authenticatedDownload).toBeTruthy();
});
