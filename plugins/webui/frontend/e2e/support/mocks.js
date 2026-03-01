const jsonResponse = (route, body, status = 200) => {
  return route.fulfill({
    status,
    contentType: "application/json",
    body: JSON.stringify(body),
  });
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
