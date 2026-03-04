// @ts-nocheck
import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  fetchModuleMetricDetail,
  fetchModuleMetricModules,
  fetchModuleMetricOptions,
  fetchModuleMetricOverview,
} from "@/api/module_metrics";
import { request } from "@/api/index";

vi.mock("@/api/index", () => ({
  request: {
    get: vi.fn(),
  },
}));

describe("module_metrics contract validation", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("accepts valid modules payload", async () => {
    request.get.mockResolvedValue({
      data: {
        items: [
          {
            module_id: "persona.image_understanding",
            title: "图片理解",
          },
        ],
      },
    });

    await expect(fetchModuleMetricModules()).resolves.toMatchObject({
      data: {
        items: [{ module_id: "persona.image_understanding" }],
      },
    });
  });

  it("rejects modules payload without module_id", async () => {
    request.get.mockResolvedValue({
      data: {
        items: [{ title: "缺失 module_id" }],
      },
    });

    await expect(fetchModuleMetricModules()).rejects.toThrow(
      "contract mismatch",
    );
  });

  it("accepts valid overview payload", async () => {
    request.get.mockResolvedValue({
      data: {
        items: [
          {
            module_id: "persona.image_fetch",
            title: "图片拉取",
            kpis: [{ key: "total_calls", label: "调用次数", value: 10 }],
            main_chart: {
              type: "line",
              chart_id: "chart-1",
              dataset: [],
              series: [],
            },
          },
        ],
      },
    });

    await expect(fetchModuleMetricOverview()).resolves.toMatchObject({
      data: {
        items: [{ module_id: "persona.image_fetch" }],
      },
    });
  });

  it("rejects detail payload with invalid chart schema", async () => {
    request.get.mockResolvedValue({
      data: {
        module_id: "persona.image_fetch",
        charts: [{ chart_id: "c-1", dataset: [], series: [] }],
      },
    });

    await expect(
      fetchModuleMetricDetail("persona.image_fetch"),
    ).rejects.toThrow("contract mismatch");
  });

  it("rejects options payload with non-string options", async () => {
    request.get.mockResolvedValue({
      data: {
        plugin_names: ["persona"],
        module_names: ["image_fetch"],
        operations: ["url"],
        conv_ids: [1001],
      },
    });

    await expect(fetchModuleMetricOptions()).rejects.toThrow(
      "contract mismatch",
    );
  });
});
