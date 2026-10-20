import { expect, test } from "@playwright/test";

test.skip(!process.env.GOLDAGENT_LIVE_E2E, "Requires a running GoldAgent backend and production frontend");

test("production frontend and backend are wired together", async ({ page, request }) => {
  const health = await request.get("http://127.0.0.1:8080/health");
  expect(health.ok()).toBeTruthy();
  await expect(health.json()).resolves.toEqual({ status: "ok" });

  const readiness = await request.get("http://127.0.0.1:8080/ready");
  expect(readiness.ok()).toBeTruthy();
  const readyBody = await readiness.json();
  expect(readyBody.status).toBe("ready");
  expect(readyBody.checks).toMatchObject({
    database: true,
    market_provider: "not_probed",
    checkpointer: true,
  });

  await page.goto("/settings");
  await expect(page.getByRole("heading", { name: "个性化设置" })).toBeVisible();

  await page.getByRole("link", { name: "Agent 对话", exact:true }).click();
  await expect(page).toHaveURL(/\/chat$/);
  await expect(page.getByRole("button", { name: "新会话",exact:true })).toBeVisible();
});
