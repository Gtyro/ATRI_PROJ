const jsonResponse = (route, body, status = 200) => {
  return route.fulfill({
    status,
    contentType: "application/json",
    body: JSON.stringify(body),
  });
};

const readJsonBody = (route) => {
  try {
    return route.request().postDataJSON();
  } catch {
    return {};
  }
};

export const mockAuthApis = async (page, token) => {
  await page.route("**/auth/**", async (route) => {
    const { pathname } = new URL(route.request().url());
    if (pathname.endsWith("/auth/token")) {
      await jsonResponse(route, {
        access_token: token,
        refresh_token: "refresh-token",
        token_type: "bearer",
      });
      return;
    }

    if (pathname.endsWith("/auth/users/me")) {
      await jsonResponse(route, {
        username: "admin",
      });
      return;
    }

    if (pathname.endsWith("/auth/refresh-token")) {
      await jsonResponse(route, {
        access_token: token,
        refresh_token: "refresh-token",
      });
      return;
    }

    await route.fulfill({ status: 404, body: "not mocked" });
  });
};

export const mockDashboardApis = async (page) => {
  await page.route("**/api/dashboard/**", async (route) => {
    const { pathname } = new URL(route.request().url());

    if (pathname.endsWith("/bot-info")) {
      await jsonResponse(route, []);
      return;
    }
    if (pathname.endsWith("/bot-connections")) {
      await jsonResponse(route, []);
      return;
    }
    if (pathname.endsWith("/chat-throughput/hourly")) {
      await jsonResponse(route, {
        hours: [],
        data: [],
      });
      return;
    }
    if (pathname.endsWith("/chat-throughput/daily")) {
      await jsonResponse(route, {
        start_date: "2026-01-01",
        end_date: "2026-01-01",
        data: [],
      });
      return;
    }
    if (pathname.endsWith("/system-info")) {
      await jsonResponse(route, {
        cpu: 12,
        memory: 34,
        memory_used: 2 * 1024 * 1024 * 1024,
        memory_total: 8 * 1024 * 1024 * 1024,
        disk: 56,
        disk_used: 100 * 1024 * 1024 * 1024,
        disk_total: 512 * 1024 * 1024 * 1024,
        os_name: "Linux",
        python_version: "3.12",
        uptime: 7200,
        timestamp: Date.now(),
      });
      return;
    }
    if (pathname.endsWith("/stream")) {
      await route.fulfill({
        status: 200,
        headers: {
          "content-type": "text/event-stream",
        },
        body: "event: dashboard_update\ndata: {}\n\n",
      });
      return;
    }

    await route.fulfill({ status: 404, body: "not mocked" });
  });
};

export const mockModuleMetricsApis = async (page) => {
  await page.route("**/api/module-metrics/**", async (route) => {
    const { pathname } = new URL(route.request().url());

    if (pathname === "/api/module-metrics/modules") {
      await jsonResponse(route, {
        items: [
          {
            module_id: "persona.image_understanding",
            title: "图片理解",
            description: "统计图片理解调用",
            plugin_name: "persona",
            module_name: "image_understanding",
          },
          {
            module_id: "persona.image_fetch",
            title: "图片拉取",
            description: "统计拉取来源分布",
            plugin_name: "persona",
            module_name: "image_fetch",
          },
        ],
      });
      return;
    }

    if (pathname === "/api/module-metrics/options") {
      await jsonResponse(route, {
        plugin_names: ["persona"],
        module_names: ["image_understanding", "image_fetch"],
        operations: ["image_understanding", "url"],
        conv_ids: ["group_1"],
      });
      return;
    }

    if (pathname === "/api/module-metrics/overview") {
      await jsonResponse(route, {
        items: [
          {
            module_id: "persona.image_understanding",
            title: "图片理解",
            kpis: [{ key: "total_calls", label: "调用次数", value: 12 }],
            main_chart: {
              chart_id: "persona.image_understanding.overview.main",
              type: "line",
              dataset: [],
              series: [],
            },
          },
          {
            module_id: "persona.image_fetch",
            title: "图片拉取",
            kpis: [{ key: "total_calls", label: "调用次数", value: 8 }],
            main_chart: {
              chart_id: "persona.image_fetch.overview.main",
              type: "pie",
              dataset: [],
              series: [],
            },
          },
        ],
      });
      return;
    }

    if (
      pathname.startsWith("/api/module-metrics/modules/") &&
      pathname.endsWith("/detail")
    ) {
      const moduleId = pathname.split("/")[4] || "";
      await jsonResponse(route, {
        module_id: moduleId,
        title: moduleId,
        charts: [
          {
            chart_id: `${moduleId}.detail.kpi`,
            type: "kpi",
            dataset: [],
            series: [],
          },
          {
            chart_id: `${moduleId}.detail.trend`,
            type: "line",
            dataset: [],
            series: [],
          },
        ],
      });
      return;
    }

    await route.fulfill({ status: 404, body: "not mocked" });
  });
};

export const mockPluginPolicyApis = async (page) => {
  let enabled = true;
  await page.route("**/api/plugin-policy/**", async (route) => {
    const { pathname } = new URL(route.request().url());

    if (pathname === "/api/plugin-policy/matrix") {
      await jsonResponse(route, {
        groups: [{ group_id: "group_1", group_name: "测试群" }],
        plugins: ["persona"],
        policies: [
          {
            gid: "group_1",
            plugin_name: "persona",
            group_name: "测试群",
            enabled,
            ingest_enabled: true,
            config: {},
          },
        ],
        defaults: {
          global: { enabled: true, ingest_enabled: true, config: {} },
          plugins: {},
        },
        policy_meta: {
          persona: {
            controls: [],
          },
        },
      });
      return;
    }

    if (pathname === "/api/plugin-policy/policy") {
      const payload = route.request().postDataJSON();
      enabled = Boolean(payload.enabled);
      await jsonResponse(route, {
        policy: {
          gid: payload.gid,
          plugin_name: payload.plugin_name,
          group_name: payload.group_name || "测试群",
          enabled,
          ingest_enabled: true,
          config: {},
        },
      });
      return;
    }

    if (pathname === "/api/plugin-policy/batch") {
      await jsonResponse(route, { success: true });
      return;
    }

    await route.fulfill({ status: 404, body: "not mocked" });
  });
};

export const mockMemoryAdminApis = async (page) => {
  await page.route("**/db/memory/**", async (route) => {
    const request = route.request();
    const { pathname, searchParams } = new URL(request.url());

    if (pathname === "/db/memory/conversations") {
      await jsonResponse(route, {
        columns: ["id", "name"],
        rows: [
          {
            id: "group_1",
            name: "测试会话",
          },
        ],
      });
      return;
    }

    if (pathname === "/db/memory/nodes") {
      const convId = searchParams.get("conv_id") || "";
      const limit = Number(searchParams.get("limit") || "50");
      const allNodes = [
        {
          id: "n_public",
          name: "公共记忆节点",
          conv_id: "",
          act_lv: 0.9,
        },
        {
          id: "n_group_1",
          name: "群聊记忆节点",
          conv_id: "group_1",
          act_lv: 0.8,
        },
      ];
      const rows = allNodes
        .filter((node) => (convId ? node.conv_id === convId : true))
        .slice(0, limit);
      await jsonResponse(route, {
        columns: ["id", "name", "conv_id", "act_lv"],
        rows,
      });
      return;
    }

    if (pathname === "/db/memory/associations" && request.method() === "POST") {
      const payload = readJsonBody(route);
      const convId = payload.conv_id || "";
      const nodeIds = Array.isArray(payload.node_ids) ? payload.node_ids : [];
      const allLinks = [
        {
          source_id: "n_public",
          target_id: "n_group_1",
          source_name: "公共记忆节点",
          target_name: "群聊记忆节点",
          strength: 0.7,
          conv_id: "",
        },
        {
          source_id: "n_group_1",
          target_id: "n_group_1",
          source_name: "群聊记忆节点",
          target_name: "群聊记忆节点",
          strength: 0.9,
          conv_id: "group_1",
        },
      ];

      let rows = allLinks.filter((link) =>
        convId ? link.conv_id === convId : true,
      );
      if (nodeIds.length > 0) {
        rows = rows.filter(
          (link) =>
            nodeIds.includes(link.source_id) &&
            nodeIds.includes(link.target_id),
        );
      }

      await jsonResponse(route, {
        columns: [
          "source_id",
          "target_id",
          "source_name",
          "target_name",
          "strength",
        ],
        rows,
      });
      return;
    }

    await route.fulfill({ status: 404, body: "not mocked" });
  });
};

export const mockDbAdminApis = async (page) => {
  await page.route("**/db/**", async (route) => {
    const request = route.request();
    const { pathname } = new URL(request.url());

    if (pathname === "/db/tables") {
      await jsonResponse(route, {
        tables: ["message_queue", "logs"],
      });
      return;
    }

    if (pathname.startsWith("/db/table/") && request.method() === "GET") {
      const tableName = pathname.split("/").pop();
      if (tableName === "message_queue") {
        await jsonResponse(route, {
          columns: [
            { name: "id", type: "INTEGER", pk: 1 },
            { name: "user_name", type: "TEXT", pk: 0 },
            { name: "content", type: "TEXT", pk: 0 },
            { name: "created_at", type: "TEXT", pk: 0 },
          ],
        });
        return;
      }
      if (tableName === "logs") {
        await jsonResponse(route, {
          columns: [
            { name: "id", type: "INTEGER", pk: 1 },
            { name: "level", type: "TEXT", pk: 0 },
            { name: "message", type: "TEXT", pk: 0 },
            { name: "timestamp", type: "TEXT", pk: 0 },
          ],
        });
        return;
      }
      await jsonResponse(route, { columns: [] });
      return;
    }

    if (pathname === "/db/query" && request.method() === "POST") {
      const payload = readJsonBody(route);
      const query = String(payload.query || "");
      if (query.includes("FROM message_queue")) {
        await jsonResponse(route, {
          columns: ["id", "user_name", "content"],
          rows: [
            { id: 1, user_name: "alice", content: "你好" },
            { id: 2, user_name: "bob", content: "收到" },
          ],
        });
        return;
      }
      if (query.includes("FROM logs")) {
        await jsonResponse(route, {
          columns: ["id", "level", "message"],
          rows: [{ id: 1, level: "INFO", message: "ok" }],
        });
        return;
      }
      await jsonResponse(route, { columns: [], rows: [] });
      return;
    }

    if (pathname === "/db/neo4j/query" && request.method() === "POST") {
      const payload = readJsonBody(route);
      const query = String(payload.query || "");

      if (query.includes("RETURN DISTINCT labels(n) as labels")) {
        await jsonResponse(route, {
          metadata: [{ name: "labels", type: "LIST" }],
          results: [[["CognitiveNode", "Memory"]]],
        });
        return;
      }

      if (query.includes("MATCH (n:CognitiveNode) RETURN n LIMIT 1")) {
        await jsonResponse(route, {
          metadata: [{ name: "n", type: "NODE" }],
          results: [
            [
              {
                identity: "1",
                labels: ["CognitiveNode"],
                properties: {
                  uid: "node_1",
                  name: "示例节点",
                  conv_id: "group_1",
                  act_lv: 0.95,
                },
              },
            ],
          ],
        });
        return;
      }

      if (query.includes("RETURN n.uid as id")) {
        await jsonResponse(route, {
          metadata: [
            { name: "id", type: "STRING" },
            { name: "name", type: "STRING" },
          ],
          results: [["node_1", "示例节点"]],
        });
        return;
      }

      await jsonResponse(route, {
        metadata: [],
        results: [],
      });
      return;
    }

    await route.fulfill({ status: 404, body: "not mocked" });
  });
};
