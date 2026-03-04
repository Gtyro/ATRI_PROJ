import { expect, test } from "@playwright/test";

import { buildTestJwt, seedAuthenticatedStorage } from "./support/auth";
import { createRequestDiagnostics } from "./support/diagnostics";
import {
  mockAuthApis,
  mockDbAdminApis,
  mockDashboardApis,
  mockMemoryAdminApis,
  mockModuleMetricsApis,
  mockPluginPolicyApis,
} from "./support/mocks";

const smoke = (title, testBody) => {
  test(title, async ({ page }, testInfo) => {
    const diagnostics = createRequestDiagnostics(page);
    try {
      await testBody({ page });
    } catch (error) {
      await diagnostics.attach(testInfo, error);
      throw error;
    } finally {
      diagnostics.dispose();
    }
  });
};

smoke("@smoke 登录链路可达", async ({ page }) => {
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

smoke("@smoke 模块统计筛选与图表切换可用", async ({ page }) => {
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

smoke("@smoke 插件策略开关可更新", async ({ page }) => {
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

smoke("@smoke 记忆管理会话筛选可用", async ({ page }) => {
  await seedAuthenticatedStorage(page);
  await mockMemoryAdminApis(page);

  const initialNodesRequest = page.waitForRequest(
    (request) =>
      request.method() === "GET" && request.url().includes("/db/memory/nodes"),
  );
  const initialAssociationsRequest = page.waitForRequest(
    (request) =>
      request.method() === "POST" &&
      request.url().includes("/db/memory/associations"),
  );

  await page.goto("/#/admin/memory-admin");
  await initialNodesRequest;
  await initialAssociationsRequest;

  await expect(page.getByRole("heading", { name: "记忆管理" })).toBeVisible();
  await expect(page.locator(".graph-container")).toBeVisible();
  await expect(page.locator(".graph-info")).toContainText("节点数量：");
  await expect(page.locator(".graph-info")).toContainText("关联数量：");

  const filteredNodesRequest = page.waitForRequest(
    (request) =>
      request.method() === "GET" &&
      request.url().includes("/db/memory/nodes") &&
      request.url().includes("conv_id=group_1"),
  );

  await page.locator(".header-controls .el-select").click();
  await page.getByRole("option", { name: "会话 group_1 (测试会话)" }).click();
  await filteredNodesRequest;

  await expect(page.locator(".graph-info")).toContainText(
    "会话 group_1 知识图谱",
  );
});

smoke("@smoke 数据库管理 SQL 与 Neo4j 查询可用", async ({ page }) => {
  await seedAuthenticatedStorage(page);
  await mockDbAdminApis(page);

  await page.goto("/#/admin/db-admin");
  await expect(page.getByRole("heading", { name: "数据库管理" })).toBeVisible();
  await page.getByRole("tab", { name: "数据查询" }).click();

  const sqlRequestPromise = page.waitForRequest(
    (request) =>
      request.method() === "POST" &&
      request.url().includes("/db/query") &&
      request.postData()?.includes("FROM message_queue"),
  );

  await page
    .getByPlaceholder("输入SELECT SQL查询语句...")
    .fill("SELECT id, user_name, content FROM message_queue LIMIT 2");
  await page
    .locator(".sql-editor")
    .getByRole("button", { name: "执行查询" })
    .click();

  const sqlRequest = await sqlRequestPromise;
  const sqlPayload = sqlRequest.postDataJSON();
  expect(sqlPayload.query).toContain("FROM message_queue");
  await expect(
    page
      .getByRole("tabpanel", { name: "数据查询" })
      .getByRole("heading", { name: "查询结果 (2 行)" }),
  ).toBeVisible();

  await page.locator(".db-admin .card-header .el-select").click();
  await page.getByRole("option", { name: "Neo4j/OGM" }).click();
  await page.getByRole("tab", { name: "数据查询" }).click();

  await page
    .getByPlaceholder(
      "输入Cypher查询（例如：MATCH (n:CognitiveNode) RETURN n LIMIT 10）",
    )
    .fill("MATCH (n:CognitiveNode) RETURN n.uid as id, n.name as name LIMIT 1");

  const cypherRequestPromise = page.waitForRequest(
    (request) =>
      request.method() === "POST" &&
      request.url().includes("/db/neo4j/query") &&
      request.postData()?.includes("RETURN n.uid as id"),
  );

  await page
    .locator(".cypher-editor")
    .getByRole("button", { name: "执行查询" })
    .click();
  await cypherRequestPromise;
  await expect(
    page
      .getByRole("tabpanel", { name: "数据查询" })
      .getByRole("heading", { name: "查询结果 (1 行)" }),
  ).toBeVisible();
});
