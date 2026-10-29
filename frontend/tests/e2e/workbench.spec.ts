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

test("legacy tool-protocol answers are not presented as completed analysis", async ({ page }) => {
  const leaked = '<tool_call><function=goldspot_query_gold_price><parameter=product_type>国内期货</parameter></function></tool_call><tool_call><function=goldspot_search_gold_news><parameter=query>美联储 黄金价格 加息 降息 最新</parameter><parameter=days_back>5</parameter><parameter=max_results>10</parameter></function></tool_call><tool_call><function=goldspot_calculate_technical_indicators><parameter=commodity_symbol>AU0</parameter></function></tool_call>\n仅供投资分析参考，不构成投资建议，也不执行任何自动交易。';
  await page.route("**/api/v1/chat/stream", route => route.fulfill({status:200,contentType:"text/event-stream",body:`event: answer_delta\ndata: ${JSON.stringify({delta:leaked})}\n\nevent: run_finished\ndata: ${JSON.stringify({run_id:"fixture-protocol",session_id:"session-1",status:"incomplete"})}\n\n`}));
  await page.goto("/chat");
  await page.getByRole("combobox",{name:"研究模式"}).selectOption("deep");
  await page.getByRole("textbox").fill("结合最近的消息和市场行情分析，根据我现在的持仓给我一些操作建议");
  await page.getByRole("button",{name:"发送",exact:true}).click();
  await expect(page.locator("main")).toContainText("未执行的工具指令");
  await expect(page.locator("main")).not.toContainText(/goldspot_|<tool_call>|<function=/);
});

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
  await expect(page.getByText("历史检验次数", { exact:false })).toContainText("10");

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

for (const locale of ["zh", "en"] as const) {
  test(`every workbench presents product copy, not internal records (${locale})`, async ({ page }, testInfo) => {
    test.setTimeout(90000);
    const diagnostic = "ValidationError Traceback INTERNAL_CANARY postgres://private-host";
    const evidence = {citations:[{title:"黄金研报",chunk_id:"PRIVATE_CHUNK_CANARY",source:"Knowledge Base",page:2}],snapshots:[{tool:"get_market_history",metadata:{source:"AkShare/Sina Futures",retrieved_at:new Date().toISOString()}}],limitations:[diagnostic]};
    await page.route("**/api/v1/agent/runs**", route => ok(route, route.request().url().endsWith("/runs") ? [{id:"PRIVATE_RUN_CANARY",question:"页面核查任务",status:"failed",created_at:new Date().toISOString()}] : {id:"PRIVATE_RUN_CANARY",status:"failed",error:diagnostic,state:{question:"页面核查任务",final_answer:`保持谨慎。\n\n数据说明：get_market_history failed: ${diagnostic}`,evidence,tool_results:[{tool:"get_market_history",error:diagnostic,arguments:{context:"PRIVATE_CONTEXT_CANARY"}}]}}));
    await page.route("**/api/v1/knowledge/documents", route => ok(route,[{id:"PRIVATE_DOCUMENT_CANARY",filename:"研究资料.md",status:"ready",metadata:{embedding_provider:"EMBEDDING_CANARY",chunk_count:2}}]));
    await page.route("**/api/v1/knowledge/search", route => ok(route,[{chunk_id:"PRIVATE_CHUNK_CANARY",document_id:"PRIVATE_DOCUMENT_CANARY",content:"实际利率影响黄金。",metadata:{filename:"研究资料.md",page:2,chunk_index:"PRIVATE_CHUNK_CANARY"}}]));
    await page.route("**/api/v1/backtests/backtest-1", route => ok(route,{id:"PRIVATE_BACKTEST_CANARY",status:"completed",result:{metrics:{cumulative_return:0.1,INTERNAL_METRIC_CANARY:42},trades:[],equity_curve:[],drawdown_curve:[]}}));
    await page.route("**/api/v1/chat/stream", route => route.fulfill({status:200,contentType:"text/event-stream",body:`event: tool_finished\ndata: ${JSON.stringify({tool:"INTERNAL_TOOL_CANARY",success:false})}\n\nevent: answer_delta\ndata: ${JSON.stringify({delta:"资料暂不完整，请谨慎参考。"})}\n\nevent: run_finished\ndata: ${JSON.stringify({run_id:"PRIVATE_RUN_CANARY",session_id:"session-1",status:"completed",evidence})}\n\n`}));
    await page.goto("/dashboard");
    if (locale === "en") await page.getByRole("button",{name:"EN",exact:true}).click();
    for (const path of ["dashboard","analysis","chat","forecast","backtest","portfolio","news","reports","knowledge","tasks","settings","login"]) {
      await page.goto(`/${path}`);
      await expect(page.locator("main h1")).toBeVisible();
      if (path === "tasks") await page.getByRole("button",{name:/页面核查任务/}).click();
      if (path === "knowledge") {
        await expect(page.getByText("研究资料.md",{exact:true})).toBeVisible();
        await page.getByRole("button",{name:locale === "zh" ? "检索" : "Search",exact:true}).click();
        await expect(page.getByText("实际利率影响黄金。",{exact:true})).toBeVisible();
        expect(await page.locator('a[href^="/chat?q="]').getAttribute("href")).not.toContain("CANARY");
      }
      if (path === "chat") {
        await page.getByRole("textbox").fill("模拟界面核查");
        await page.getByRole("button",{name:locale === "zh" ? "发送" : "Send",exact:true}).click();
        await expect(page.getByText("资料暂不完整，请谨慎参考。",{exact:true})).toBeVisible();
      }
      if (path === "backtest") await expect(page.getByText(locale === "zh" ? "累计收益率" : "Cumulative return",{exact:true})).toBeVisible();
      if (path === "tasks") await expect(page.getByText("保持谨慎。",{exact:false})).toBeVisible();
      await page.locator("main details").evaluateAll(items => items.forEach(item => item.setAttribute("open","")));
      await expect(page.locator("main")).not.toContainText(/CANARY|ValidationError|Traceback|postgres:\/\/|get_market_history|Embedding|600ms|JWT|distributed queue/);
      if (["chat","tasks","knowledge"].includes(path)) await page.screenshot({path:testInfo.outputPath(`${path}-${locale}.png`),fullPage:true});
    }
  });
}

test("backend failures display a safe actionable message", async ({ page }) => {
  test.setTimeout(60000);
  await page.route("**/api/v1/**", route => route.fulfill({status:500,contentType:"application/json",body:JSON.stringify({success:false,error:{code:"INTERNAL_ERROR",message:"Traceback PRIVATE_ERROR_CANARY postgres://private-host"}})}));
  for (const path of ["dashboard","knowledge","tasks","chat"]) {
    await page.goto(`/${path}`);
    await expect(page.locator("main")).toContainText("暂时无法",{timeout:15000});
    await expect(page.locator("main")).not.toContainText(/PRIVATE_ERROR_CANARY|Traceback|postgres:\/\//);
  }
});
