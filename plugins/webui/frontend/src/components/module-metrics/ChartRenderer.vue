<template>
  <div class="chart-renderer" :class="{ 'is-compact': compact }">
    <div v-if="showTitle && chartTitle" class="chart-header">
      <h4>{{ chartTitle }}</h4>
    </div>

    <div v-if="isKpiType" class="kpi-grid">
      <div
        v-for="(item, index) in kpiItems"
        :key="item.key || item.label || index"
        class="kpi-item"
      >
        <span class="kpi-label">{{
          item.label || item.key || `KPI ${index + 1}`
        }}</span>
        <strong class="kpi-value" :class="{ 'is-danger': isDangerKpi(item) }">
          {{ formatKpiValue(item) }}
        </strong>
      </div>
      <el-empty
        v-if="kpiItems.length === 0"
        class="empty-block"
        description="暂无指标数据"
        :image-size="56"
      />
    </div>

    <div v-else-if="isTableType" class="table-wrap">
      <div
        v-if="useVirtualTable"
        class="table-v2-shell"
        :style="chartHeightStyle"
      >
        <el-auto-resizer>
          <template #default="{ width, height }">
            <el-table-v2
              :columns="virtualTableColumns"
              :data="virtualTableRows"
              :width="Math.max(Number(width), virtualTableMinWidth)"
              :height="Math.max(Number(height), 220)"
              :row-height="40"
              row-key="__row_key"
              fixed
            />
          </template>
        </el-auto-resizer>
      </div>

      <el-table
        v-else
        :data="tableRows"
        border
        stripe
        style="width: 100%"
        :max-height="tableHeight"
        empty-text="暂无数据"
      >
        <el-table-column
          v-for="column in tableColumns"
          :key="column.prop"
          :prop="column.prop"
          :label="column.label"
          :min-width="column.minWidth"
          show-overflow-tooltip
        >
          <template #default="{ row }">
            {{ formatTableCell(row[column.prop], column.prop) }}
          </template>
        </el-table-column>
      </el-table>

      <div v-if="tableMetaText || useVirtualTable" class="table-meta">
        <span v-if="useVirtualTable">已启用虚拟滚动</span>
        <span v-if="tableMetaText">{{ tableMetaText }}</span>
      </div>
    </div>

    <div
      v-else-if="isEChartType"
      ref="chartViewportRef"
      class="echart-shell"
      :style="chartHeightStyle"
    >
      <div v-if="!isChartVisible" class="chart-skeleton">
        <el-skeleton :rows="4" animated />
      </div>
      <div
        v-else
        ref="chartRef"
        class="echart-host"
        :style="chartHeightStyle"
      />
    </div>

    <el-empty
      v-else
      class="empty-block"
      description="暂不支持该图表类型"
      :image-size="56"
    />
  </div>
</template>

<script setup lang="ts">
import {
  computed,
  nextTick,
  onBeforeUnmount,
  onMounted,
  ref,
  watch,
} from "vue";
import type { EChartsType } from "echarts/core";

import type {
  ModuleMetricChart,
  ModuleMetricDataRow,
  ModuleMetricKpi,
  ModuleMetricMeta,
  ModuleMetricSeries,
  ModuleMetricXAxis,
} from "@/types/module_metrics";

const OPTION_CACHE_LIMIT = 80;
const VIRTUAL_TABLE_ROW_THRESHOLD = 120;
const VIRTUAL_TABLE_COLUMN_THRESHOLD = 10;
const optionCache = new Map<string, Record<string, unknown>>();
let echartsRuntimePromise: Promise<typeof import("echarts/core")> | null = null;

const loadEchartsRuntime = async (): Promise<typeof import("echarts/core")> => {
  if (!echartsRuntimePromise) {
    echartsRuntimePromise = Promise.all([
      import("echarts/core"),
      import("echarts/charts"),
      import("echarts/components"),
      import("echarts/renderers"),
    ]).then(
      ([echartsCore, echartsCharts, echartsComponents, echartsRenderers]) => {
        echartsCore.use([
          echartsCharts.LineChart,
          echartsCharts.BarChart,
          echartsCharts.PieChart,
          echartsComponents.TooltipComponent,
          echartsComponents.LegendComponent,
          echartsComponents.GridComponent,
          echartsComponents.DatasetComponent,
          echartsComponents.TitleComponent,
          echartsComponents.DataZoomComponent,
          echartsRenderers.CanvasRenderer,
        ]);
        return echartsCore;
      },
    );
  }

  return echartsRuntimePromise;
};

const TABLE_COLUMN_LABELS: Record<string, string> = {
  created_at: "时间",
  plugin_name: "Plugin",
  module_name: "Module",
  operation: "Operation",
  phase: "Phase",
  resolved_via: "来源",
  conv_id: "Conv ID",
  request_id: "Request ID",
  provider_name: "Provider",
  model: "Model",
  success: "结果",
  error_type: "错误类型",
  prompt_tokens: "Prompt",
  completion_tokens: "Completion",
  total_tokens: "Total",
  total_calls: "调用次数",
  failed_calls: "失败次数",
};

const props = withDefaults(
  defineProps<{
    chart?: Partial<ModuleMetricChart> | null;
    height?: number;
    showTitle?: boolean;
    compact?: boolean;
  }>(),
  {
    chart: () => ({}),
    height: 320,
    showTitle: true,
    compact: false,
  },
);

const chartRef = ref<HTMLDivElement | null>(null);
const chartViewportRef = ref<HTMLDivElement | null>(null);
const isChartVisible = ref(false);
let chartInstance: EChartsType | null = null;
let echartsRuntime: Awaited<ReturnType<typeof loadEchartsRuntime>> | null =
  null;
let resizeObserver: ResizeObserver | null = null;
let visibilityObserver: IntersectionObserver | null = null;
let renderToken = 0;

interface TableColumnView {
  prop: string;
  label: string;
  minWidth: number;
}

const chartTitle = computed(() => {
  const title = props.chart?.title;
  return title == null ? "" : String(title).trim();
});

const chartType = computed(() => {
  return String(props.chart?.type || "")
    .trim()
    .toLowerCase();
});

const chartDataset = computed<ModuleMetricDataRow[]>(() => {
  return Array.isArray(props.chart?.dataset)
    ? (props.chart.dataset as ModuleMetricDataRow[])
    : [];
});

const chartSeries = computed<ModuleMetricSeries[]>(() => {
  return Array.isArray(props.chart?.series)
    ? (props.chart.series as ModuleMetricSeries[])
    : [];
});

const chartXAxis = computed<ModuleMetricXAxis>(() => {
  const value = props.chart?.x_axis;
  if (value && typeof value === "object") {
    return value as ModuleMetricXAxis;
  }
  return {};
});

const chartMeta = computed<ModuleMetricMeta>(() => {
  const value = props.chart?.meta;
  if (value && typeof value === "object") {
    return value as ModuleMetricMeta;
  }
  return {};
});

const isEChartType = computed(() =>
  ["line", "bar", "pie"].includes(chartType.value),
);
const isTableType = computed(() => chartType.value === "table");
const isKpiType = computed(() => chartType.value === "kpi");

const chartHeightStyle = computed(() => {
  const normalized = Number(props.height);
  const height = Number.isFinite(normalized) ? Math.max(220, normalized) : 320;
  return { height: `${height}px` };
});

const kpiItems = computed<ModuleMetricKpi[]>(() => {
  return chartDataset.value.filter(
    (item) => item && typeof item === "object",
  ) as ModuleMetricKpi[];
});

const tableRows = computed<Record<string, unknown>[]>(() => {
  return chartDataset.value
    .filter((item) => item != null)
    .map((item) => {
      if (item && typeof item === "object" && !Array.isArray(item)) {
        return item as Record<string, unknown>;
      }
      return { value: item };
    });
});

const useVirtualTable = computed(() => {
  return (
    tableRows.value.length >= VIRTUAL_TABLE_ROW_THRESHOLD ||
    tableColumns.value.length >= VIRTUAL_TABLE_COLUMN_THRESHOLD
  );
});

const virtualTableRows = computed<Record<string, unknown>[]>(() => {
  return tableRows.value.map((row, index) => ({
    ...row,
    __row_key: index,
  }));
});

const tableColumns = computed<TableColumnView[]>(() => {
  const rawColumns = chartMeta.value.columns;
  if (Array.isArray(rawColumns) && rawColumns.length > 0) {
    return rawColumns
      .map((column): TableColumnView | null => {
        if (typeof column === "string") {
          const prop = column;
          return {
            prop,
            label: formatColumnLabel(prop),
            minWidth: getColumnMinWidth(prop),
          };
        }
        if (!column || typeof column !== "object") {
          return null;
        }
        const prop = String(column.prop || "").trim();
        if (!prop) {
          return null;
        }
        return {
          prop,
          label: String(column.label || formatColumnLabel(prop)),
          minWidth: Number(column.minWidth) || getColumnMinWidth(prop),
        };
      })
      .filter((column): column is TableColumnView => column !== null);
  }

  const [firstRow] = tableRows.value;
  if (!firstRow || typeof firstRow !== "object") {
    return [];
  }
  return Object.keys(firstRow).map((key) => ({
    prop: key,
    label: formatColumnLabel(key),
    minWidth: getColumnMinWidth(key),
  }));
});

const virtualTableColumns = computed(() => {
  return tableColumns.value.map((column) => ({
    key: column.prop,
    dataKey: column.prop,
    title: column.label,
    width: Math.max(column.minWidth, 120),
    cellRenderer: ({ rowData }: { rowData: Record<string, unknown> }) =>
      formatTableCell(rowData?.[column.prop], column.prop),
  }));
});

const virtualTableMinWidth = computed(() => {
  const width = tableColumns.value.reduce(
    (sum, column) => sum + Math.max(column.minWidth, 120),
    0,
  );
  return Math.max(width, 640);
});

const tableHeight = computed(() => {
  const normalized = Number(props.height);
  const height = Number.isFinite(normalized) ? normalized : 360;
  return Math.max(220, Math.min(height, 520));
});

const tableMetaText = computed(() => {
  const total = Number(chartMeta.value.total);
  const page = Number(chartMeta.value.page);
  const size = Number(chartMeta.value.size);

  if (
    Number.isFinite(total) &&
    Number.isFinite(page) &&
    Number.isFinite(size)
  ) {
    return `第 ${page} 页，每页 ${size} 条，共 ${total} 条`;
  }
  if (Number.isFinite(total)) {
    return `共 ${total} 条`;
  }
  return "";
});

const pad = (value: number | string): string => String(value).padStart(2, "0");

const normalizeDateInput = (value: unknown): string | number | Date | null => {
  if (value instanceof Date) {
    return value;
  }
  if (typeof value === "string" || typeof value === "number") {
    return value;
  }
  return null;
};

const formatDateTime = (value: unknown): string => {
  if (!value) {
    return "-";
  }
  const normalized = normalizeDateInput(value);
  if (normalized == null) {
    return String(value);
  }
  const date = new Date(normalized);
  if (Number.isNaN(date.getTime())) {
    return String(value);
  }
  const year = date.getFullYear();
  const month = pad(date.getMonth() + 1);
  const day = pad(date.getDate());
  const hour = pad(date.getHours());
  const minute = pad(date.getMinutes());
  const second = pad(date.getSeconds());
  return `${year}-${month}-${day} ${hour}:${minute}:${second}`;
};

const formatAxisTime = (value: unknown): string => {
  if (!value) {
    return "-";
  }
  const normalized = normalizeDateInput(value);
  if (normalized == null) {
    return String(value);
  }
  const date = new Date(normalized);
  if (Number.isNaN(date.getTime())) {
    return String(value);
  }
  const year = date.getFullYear();
  const month = pad(date.getMonth() + 1);
  const day = pad(date.getDate());
  const hour = pad(date.getHours());
  const minute = pad(date.getMinutes());
  if (hour === "00" && minute === "00") {
    return `${year}-${month}-${day}`;
  }
  return `${month}-${day} ${hour}:${minute}`;
};

const toFiniteNumber = (value: unknown, fallback = 0): number => {
  const number = Number(value);
  return Number.isFinite(number) ? number : fallback;
};

const formatInteger = (value: unknown): string => {
  return Math.round(toFiniteNumber(value, 0)).toLocaleString();
};

const formatDecimal = (value: unknown): string => {
  return toFiniteNumber(value, 0).toFixed(2);
};

const formatPercent = (value: unknown): string => {
  return `${(toFiniteNumber(value, 0) * 100).toFixed(2)}%`;
};

const formatColumnLabel = (key: unknown): string => {
  const normalized = String(key || "").trim();
  if (!normalized) {
    return "字段";
  }
  if (TABLE_COLUMN_LABELS[normalized]) {
    return TABLE_COLUMN_LABELS[normalized];
  }
  return normalized
    .split("_")
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
};

const getColumnMinWidth = (prop: unknown): number => {
  const key = String(prop || "").trim();
  if (["created_at", "request_id", "conv_id"].includes(key)) {
    return 180;
  }
  if (
    [
      "operation",
      "module_name",
      "phase",
      "resolved_via",
      "error_type",
    ].includes(key)
  ) {
    return 140;
  }
  if (["prompt_tokens", "completion_tokens", "total_tokens"].includes(key)) {
    return 110;
  }
  return 120;
};

const isDangerKpi = (item: ModuleMetricKpi): boolean => {
  const key = String(item?.key || "").toLowerCase();
  return key.includes("failed") || key.includes("error");
};

const formatKpiValue = (item: ModuleMetricKpi): string => {
  const format = String(item?.format || "").toLowerCase();
  const raw = item?.value;
  if (format === "integer") {
    return formatInteger(raw);
  }
  if (format === "decimal") {
    return formatDecimal(raw);
  }
  if (format === "percent") {
    return formatPercent(raw);
  }
  const number = Number(raw);
  if (Number.isFinite(number)) {
    return number.toLocaleString();
  }
  if (raw == null || raw === "") {
    return "-";
  }
  return String(raw);
};

const formatTableCell = (value: unknown, key: string): string => {
  if (key === "success") {
    return value ? "成功" : "失败";
  }
  if (key === "created_at") {
    return formatDateTime(value);
  }
  if (
    [
      "prompt_tokens",
      "completion_tokens",
      "total_tokens",
      "total_calls",
      "failed_calls",
    ].includes(key)
  ) {
    return formatInteger(value);
  }
  if (value == null || value === "") {
    return "-";
  }
  return String(value);
};

const buildFallbackSeries = (xField: string): ModuleMetricSeries[] => {
  const [sample] = chartDataset.value;
  if (!sample || typeof sample !== "object") {
    return [];
  }
  return Object.keys(sample)
    .filter((key) => key !== xField)
    .filter((key) =>
      chartDataset.value.some((row) => Number.isFinite(Number(row?.[key]))),
    )
    .map((key) => ({
      field: key,
      name: formatColumnLabel(key),
      type: chartType.value,
    }));
};

const buildLineOrBarOption = (): Record<string, unknown> => {
  const xField = String(chartXAxis.value.field || "").trim();
  const axisType = String(chartXAxis.value.type || "category").toLowerCase();
  const seriesConfig =
    chartSeries.value.length > 0
      ? chartSeries.value
      : buildFallbackSeries(xField);
  const hasRightAxis = seriesConfig.some((item) => item?.y_axis === "right");
  const xData = chartDataset.value.map((row) => {
    const value = xField ? row?.[xField] : undefined;
    return axisType === "time" ? formatAxisTime(value) : (value ?? "-");
  });

  return {
    tooltip: {
      trigger: "axis",
    },
    legend: {
      top: 0,
    },
    grid: {
      left: 40,
      right: hasRightAxis ? 48 : 20,
      top: 36,
      bottom: 24,
      containLabel: true,
    },
    xAxis: {
      type: "category",
      data: xData,
      axisLabel: {
        hideOverlap: true,
      },
    },
    yAxis: hasRightAxis
      ? [
          {
            type: "value",
            minInterval: 1,
          },
          {
            type: "value",
            position: "right",
            minInterval: 1,
          },
        ]
      : [
          {
            type: "value",
            minInterval: 1,
          },
        ],
    series: seriesConfig.map((item) => {
      const field = String(item?.field || "").trim();
      const seriesType = String(item?.type || chartType.value || "line");
      return {
        name: item?.name || formatColumnLabel(field),
        type: seriesType,
        smooth: seriesType === "line",
        yAxisIndex: item?.y_axis === "right" ? 1 : 0,
        data: chartDataset.value.map((row) => toFiniteNumber(row?.[field], 0)),
      };
    }),
    dataZoom:
      chartDataset.value.length > 24
        ? [
            {
              type: "inside",
            },
            {
              type: "slider",
              height: 14,
              bottom: 0,
            },
          ]
        : [],
  };
};

const buildPieOption = (): Record<string, unknown> => {
  const [mainSeries] = chartSeries.value;
  const valueField = String(mainSeries?.field || "value").trim();
  const nameField = String(mainSeries?.name_field || "name").trim();
  const data = chartDataset.value.map((row, index) => {
    const fallbackName = `item_${index + 1}`;
    const name = row?.[nameField] ?? row?.name ?? row?.label ?? fallbackName;
    return {
      name: String(name),
      value: toFiniteNumber(row?.[valueField] ?? row?.value, 0),
    };
  });

  return {
    tooltip: {
      trigger: "item",
    },
    legend: {
      type: "scroll",
      top: 0,
    },
    series: [
      {
        name: mainSeries?.name || chartTitle.value || "分布",
        type: "pie",
        radius: props.compact ? ["40%", "70%"] : ["34%", "70%"],
        center: ["50%", "56%"],
        data,
        label: {
          formatter: "{b}: {d}%",
        },
      },
    ],
  };
};

const buildChartOption = (): Record<string, unknown> => {
  if (chartType.value === "line" || chartType.value === "bar") {
    return buildLineOrBarOption();
  }
  if (chartType.value === "pie") {
    return buildPieOption();
  }
  return {};
};

const safeStringify = (value: unknown): string => {
  try {
    return JSON.stringify(value);
  } catch (_error) {
    return String(value);
  }
};

const buildOptionCacheKey = (): string => {
  const total = chartDataset.value.length;
  const first = total > 0 ? chartDataset.value[0] : null;
  const last = total > 1 ? chartDataset.value[total - 1] : first;
  const chartId = String(
    props.chart?.chart_id || chartTitle.value || chartType.value || "chart",
  ).trim();

  return [
    chartId,
    chartType.value,
    chartSeries.value.length,
    chartXAxis.value.field || "",
    props.compact ? "1" : "0",
    safeStringify(first),
    safeStringify(last),
    total,
  ].join("::");
};

const getCachedChartOption = (): Record<string, unknown> => {
  const key = buildOptionCacheKey();
  const cached = optionCache.get(key);
  if (cached) {
    return cached;
  }

  const option = buildChartOption();
  optionCache.set(key, option);

  if (optionCache.size > OPTION_CACHE_LIMIT) {
    const oldest = optionCache.keys().next().value;
    if (typeof oldest === "string") {
      optionCache.delete(oldest);
    }
  }

  return option;
};

const ensureChartInstance = async (): Promise<EChartsType | null> => {
  if (!chartRef.value) {
    return null;
  }

  if (!echartsRuntime) {
    echartsRuntime = await loadEchartsRuntime();
  }

  if (!chartInstance) {
    chartInstance = echartsRuntime.init(chartRef.value);
  }

  return chartInstance;
};

const disposeChart = (): void => {
  if (chartInstance) {
    chartInstance.dispose();
    chartInstance = null;
  }
};

const handleResize = (): void => {
  if (chartInstance) {
    chartInstance.resize();
  }
};

const clearVisibilityObserver = (): void => {
  if (visibilityObserver) {
    visibilityObserver.disconnect();
    visibilityObserver = null;
  }
};

const bindVisibilityObserver = async (): Promise<void> => {
  if (!isEChartType.value) {
    clearVisibilityObserver();
    isChartVisible.value = false;
    return;
  }

  await nextTick();
  if (!chartViewportRef.value || typeof IntersectionObserver === "undefined") {
    isChartVisible.value = true;
    return;
  }

  clearVisibilityObserver();
  visibilityObserver = new IntersectionObserver(
    (entries) => {
      const [entry] = entries;
      if (!entry) {
        return;
      }
      if (entry.isIntersecting || entry.intersectionRatio > 0) {
        isChartVisible.value = true;
        clearVisibilityObserver();
        renderEchart();
      }
    },
    { rootMargin: "120px" },
  );
  visibilityObserver.observe(chartViewportRef.value);
};

const bindResizeObserver = (): void => {
  if (typeof ResizeObserver === "undefined") {
    return;
  }
  if (resizeObserver) {
    resizeObserver.disconnect();
    resizeObserver = null;
  }
  if (!chartRef.value) {
    return;
  }
  resizeObserver = new ResizeObserver(() => {
    handleResize();
  });
  resizeObserver.observe(chartRef.value);
};

const renderEchart = async (): Promise<void> => {
  if (!isEChartType.value || !isChartVisible.value) {
    disposeChart();
    return;
  }

  const currentToken = ++renderToken;
  await nextTick();

  const instance = await ensureChartInstance();
  if (!instance || currentToken !== renderToken) {
    return;
  }

  instance.setOption(getCachedChartOption(), true);
  bindResizeObserver();
  handleResize();
};

watch(
  isEChartType,
  (value) => {
    if (!value) {
      isChartVisible.value = false;
      clearVisibilityObserver();
      disposeChart();
      return;
    }

    isChartVisible.value = false;
    bindVisibilityObserver();
  },
  { immediate: true },
);

watch(
  () => [props.chart, props.height, props.compact, isChartVisible.value],
  () => {
    renderEchart();
  },
  {
    deep: true,
    immediate: true,
  },
);

onMounted(() => {
  window.addEventListener("resize", handleResize);
  bindVisibilityObserver();
  renderEchart();
});

onBeforeUnmount(() => {
  window.removeEventListener("resize", handleResize);
  clearVisibilityObserver();
  if (resizeObserver) {
    resizeObserver.disconnect();
    resizeObserver = null;
  }
  disposeChart();
});
</script>

<style scoped>
.chart-renderer {
  width: 100%;
  min-height: 0;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.chart-renderer.is-compact {
  gap: 8px;
}

.chart-header h4 {
  margin: 0;
  font-size: 15px;
  color: #303133;
}

.echart-shell {
  width: 100%;
}

.echart-host {
  width: 100%;
}

.chart-skeleton {
  border: 1px solid #ebeef5;
  border-radius: 8px;
  padding: 12px;
  background: #fff;
}

.kpi-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
  gap: 10px;
}

.kpi-item {
  border: 1px solid #ebeef5;
  border-radius: 8px;
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-height: 84px;
  background: #fff;
}

.kpi-label {
  font-size: 12px;
  color: #606266;
}

.kpi-value {
  font-size: 22px;
  line-height: 1.2;
  color: #303133;
  font-weight: 600;
}

.kpi-value.is-danger {
  color: #f56c6c;
}

.table-wrap {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.table-v2-shell {
  width: 100%;
  border: 1px solid #ebeef5;
  border-radius: 8px;
  overflow: hidden;
}

.table-meta {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  flex-wrap: wrap;
  font-size: 12px;
  color: #909399;
}

.empty-block {
  min-height: 160px;
}

@media (max-width: 768px) {
  .kpi-grid {
    grid-template-columns: repeat(1, minmax(0, 1fr));
  }
}
</style>
