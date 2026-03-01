import { expect, test } from "@playwright/test";

import { buildTestJwt, seedAuthenticatedStorage } from "./support/auth";
import {
  mockAuthApis,
  mockDashboardApis,
  mockModuleMetricsApis,
  mockPluginPolicyApis,
} from "./support/mocks";

test("@smoke 登录链路可达", async ({ page }) => {
  const token = buildTestJwt();
  await mockAuthApis(page, token);
  await mockDashboardApis(page);

  await page.goto("/#/login");

  await page.getByPlaceholder("请输入用户名").fill("admin");
  await page.getByPlaceholder("请输入密码").fill("admin");
  await page.getByTestId("login-submit").click();

  await expect(page).toHaveURL(/#\/admin\/dashboard$/);
  await expect(page.getByText("仪表盘")).toBeVisible();
});

test("@smoke 模块统计筛选与图表切换可用", async ({ page }) => {
  await seedAuthenticatedStorage(page);
  await mockModuleMetricsApis(page);

  await page.goto("/#/admin/module-metrics");

  await expect(page.getByTestId("module-metrics-page")).toBeVisible();
  await expect(page.locator(".module-card")).toHaveCount(2);

  await page
    .getByPlaceholder("搜索模块（module_id / 标题 / 描述）")
    .fill("图片拉取");
  await expect(page.locator(".module-card")).toHaveCount(1);
  await expect(
    page.getByTestId("module-card-persona.image_fetch"),
  ).toBeVisible();

  await page.getByTestId("module-focus-persona.image_fetch").click();
  await expect(page.getByTestId("module-focus-panel")).toBeVisible();
  await page.getByTestId("module-back-overview").click();
  await expect(page.getByTestId("module-focus-panel")).toHaveCount(0);
});

test("@smoke 插件策略开关可更新", async ({ page }) => {
  await seedAuthenticatedStorage(page);
  await mockPluginPolicyApis(page);

  await page.goto("/#/admin/plugin-policy");
  await expect(page.getByTestId("plugin-policy-page")).toBeVisible();

  const requestPromise = page.waitForRequest(
    (request) =>
      request.method() === "POST" &&
      request.url().includes("/api/plugin-policy/policy"),
  );

  await page.getByTestId("policy-enabled-group_1-persona").click();

  const request = await requestPromise;
  const payload = request.postDataJSON();
  expect(payload).toMatchObject({
    gid: "group_1",
    plugin_name: "persona",
  });
});
