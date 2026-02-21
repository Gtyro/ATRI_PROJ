import { defineComponent } from "vue";
import { mount } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";

import ModuleMetricsPage from "@/views/ModuleMetricsPage.vue";
import {
  fetchModuleMetricDetail,
  fetchModuleMetricModules,
  fetchModuleMetricOptions,
  fetchModuleMetricOverview,
} from "@/api/module_metrics";

vi.mock("@/api/module_metrics", () => ({
  fetchModuleMetricDetail: vi.fn(),
  fetchModuleMetricModules: vi.fn(),
  fetchModuleMetricOptions: vi.fn(),
  fetchModuleMetricOverview: vi.fn(),
}));

vi.mock("@/components/module-metrics/ChartRenderer.vue", () => ({
  default: defineComponent({
    name: "ChartRendererStub",
    props: {
      chart: {
        type: Object,
        default: () => ({}),
      },
    },
    template:
      '<div class="chart-renderer-stub">{{ chart?.type || "unknown" }}</div>',
  }),
}));

const flushPromises = async () => {
  await Promise.resolve();
  await Promise.resolve();
};

const settle = async (times = 4) => {
  for (let i = 0; i < times; i += 1) {
    await flushPromises();
  }
};

const MODULE_DEFINITIONS = [
  {
    module_id: "persona.image_understanding",
    title: "图片理解",
    description: "统计图片理解调用",
    plugin_name: "persona",
    module_name: "image_understanding",
  },
  {
    module_id: "persona.image_url_fallback",
    title: "图片 URL 回退",
    description: "统计回退来源分布",
    plugin_name: "persona",
    module_name: "image_url_fallback",
  },
];

const OVERVIEW_ITEMS = [
  {
    module_id: "persona.image_understanding",
    title: "图片理解",
    kpis: [
      { key: "total_calls", label: "调用次数", value: 12, format: "integer" },
    ],
    main_chart: {
      chart_id: "persona.image_understanding.overview.main",
      type: "line",
      dataset: [],
      series: [],
    },
  },
  {
    module_id: "persona.image_url_fallback",
    title: "图片 URL 回退",
    kpis: [
      { key: "total_calls", label: "调用次数", value: 8, format: "integer" },
    ],
    main_chart: {
      chart_id: "persona.image_url_fallback.overview.main",
      type: "pie",
      dataset: [],
      series: [],
    },
  },
];

const DETAIL_PAYLOAD = {
  module_id: "persona.image_understanding",
  title: "图片理解",
  charts: [
    {
      chart_id: "persona.image_understanding.detail.kpi",
      type: "kpi",
      dataset: [],
      series: [],
    },
    {
      chart_id: "persona.image_understanding.detail.trend.day",
      type: "line",
      dataset: [],
      series: [],
    },
  ],
};

const ElCardStub = defineComponent({
  name: "ElCardStub",
  template:
    '<section class="el-card"><header class="el-card__header"><slot name="header" /></header><div class="el-card__body"><slot /></div></section>',
});

const ElButtonStub = defineComponent({
  name: "ElButtonStub",
  emits: ["click"],
  template:
    '<button class="el-button" @click="$emit(\'click\')"><slot /></button>',
});

const mountPage = () =>
  mount(ModuleMetricsPage, {
    global: {
      stubs: {
        "el-card": ElCardStub,
        "el-button": ElButtonStub,
        "el-input": true,
        "el-tag": true,
        "el-form": true,
        "el-form-item": true,
        "el-select": true,
        "el-option": true,
        "el-date-picker": true,
        "el-empty": true,
        "el-tooltip": true,
        "el-collapse-transition": true,
        "el-icon": true,
      },
      directives: {
        loading() {},
      },
    },
  });

const setMaybeRef = (holder, key, value) => {
  const current = holder[key];
  if (current && typeof current === "object" && "value" in current) {
    current.value = value;
    return;
  }
  holder[key] = value;
};

describe("ModuleMetricsPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();

    fetchModuleMetricModules.mockResolvedValue({
      data: { items: MODULE_DEFINITIONS },
    });
    fetchModuleMetricOptions.mockResolvedValue({
      data: {
        plugin_names: ["persona"],
        module_names: ["image_understanding", "image_url_fallback"],
        operations: ["image_understanding", "url", "file_id"],
        conv_ids: ["group_1"],
      },
    });
    fetchModuleMetricOverview.mockResolvedValue({
      data: { items: OVERVIEW_ITEMS },
    });
    fetchModuleMetricDetail.mockResolvedValue({
      data: DETAIL_PAYLOAD,
    });
  });

  it("loads and renders overview modules on mount", async () => {
    const wrapper = mountPage();
    await settle();

    expect(fetchModuleMetricModules).toHaveBeenCalledTimes(1);
    expect(fetchModuleMetricOptions).toHaveBeenCalledTimes(1);
    expect(fetchModuleMetricOverview).toHaveBeenCalledTimes(1);
    expect(wrapper.findAll(".module-card")).toHaveLength(2);
    expect(wrapper.text()).toContain("图片理解");
    expect(wrapper.text()).toContain("图片 URL 回退");
    expect(wrapper.findAll(".chart-renderer-stub")).toHaveLength(2);
  });

  it("switches between overview and focus when clicking focus and back", async () => {
    const wrapper = mountPage();
    await settle();

    const setupState = wrapper.vm.$.setupState;
    await setupState.handleFocus("persona.image_understanding");
    await settle();

    expect(fetchModuleMetricDetail).toHaveBeenCalledTimes(1);
    expect(fetchModuleMetricDetail).toHaveBeenCalledWith(
      "persona.image_understanding",
      expect.any(Object),
    );
    expect(wrapper.find(".focus-panel").exists()).toBe(true);
    expect(wrapper.text()).toContain("返回 overview");

    setupState.backToOverview();
    await settle();

    expect(wrapper.find(".focus-panel").exists()).toBe(false);
    expect(wrapper.find(".overview-panel").exists()).toBe(true);
  });

  it("passes advanced filters to overview/options requests when refreshing", async () => {
    const wrapper = mountPage();
    await settle();

    const setupState = wrapper.vm.$.setupState;
    setupState.filters.plugin_name = "persona";
    setupState.filters.module_name = "image_understanding";
    setupState.filters.operation = "image_understanding";
    setupState.filters.conv_id = "group_1";
    setMaybeRef(setupState, "dateRange", [
      new Date("2026-02-01T03:04:05"),
      new Date("2026-02-02T06:07:08"),
    ]);

    const refreshButton = wrapper.findAll(".toolbar-actions .el-button").at(-1);
    await refreshButton.trigger("click");
    await settle();

    const overviewParams = fetchModuleMetricOverview.mock.calls.at(-1)[0];
    expect(overviewParams).toMatchObject({
      from: "2026-02-01T03:04:05",
      to: "2026-02-02T06:07:08",
      plugin_name: "persona",
      module_name: "image_understanding",
      operation: "image_understanding",
      conv_id: "group_1",
    });

    const optionParams = fetchModuleMetricOptions.mock.calls.at(-1)[0];
    expect(optionParams).toMatchObject({
      from: "2026-02-01T03:04:05",
      to: "2026-02-02T06:07:08",
      plugin_name: "persona",
      module_name: "image_understanding",
      operation: "image_understanding",
      conv_id: "group_1",
    });
  });
});
