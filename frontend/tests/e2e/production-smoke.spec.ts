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
    market_provider: true,
    checkpointer: true,
  });

  await page.goto("/settings");
  await expect(page.getByRole("heading", { name: "设置" })).toBeVisible();
  await expect(page.getByText("demo@goldagent.local")).toBeVisible();

  await page.getByRole("link", { name: "Agent Chat" }).click();
  await expect(page).toHaveURL(/\/chat$/);
  await expect(page.getByRole("button", { name: "新建会话" })).toBeVisible();
});
