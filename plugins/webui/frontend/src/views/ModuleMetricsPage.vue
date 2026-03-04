<template>
  <div class="module-metrics-page" data-testid="module-metrics-page">
    <el-card class="toolbar-card" shadow="never">
      <div class="toolbar-main">
        <div class="toolbar-title">
          <h3>模块统计</h3>
          <el-tag type="info" effect="plain">{{ modeTagText }}</el-tag>
        </div>

        <div class="toolbar-actions">
          <el-input
            v-model="searchKeyword"
            class="search-input"
            clearable
            placeholder="搜索模块（module_id / 标题 / 描述）"
            @keyup.enter="handleSearch"
            data-testid="module-search-input"
          >
            <template #prefix>
              <el-icon><Search /></el-icon>
            </template>
          </el-input>
          <el-button
            @click="toggleAdvanced"
            data-testid="module-toggle-advanced"
          >
            <el-icon><Filter /></el-icon>
            {{ showAdvanced ? "收起筛选" : "高级筛选" }}
          </el-button>
          <el-button @click="handleReset" data-testid="module-reset"
            >重置</el-button
          >
          <el-button
            type="primary"
            :loading="isRefreshing"
            @click="handleSearch"
            data-testid="module-refresh"
          >
            刷新
          </el-button>
        </div>
      </div>

      <el-collapse-transition>
        <div
          v-show="showAdvanced"
          class="advanced-filter-wrap"
          data-testid="module-advanced-filters"
        >
          <el-form :inline="true" class="filter-form">
            <el-form-item label="时间范围">
              <el-date-picker
                v-model="dateRange"
                type="datetimerange"
                range-separator="至"
                start-placeholder="开始时间"
                end-placeholder="结束时间"
                :clearable="false"
                style="width: 360px"
              />
            </el-form-item>

            <el-form-item label="Plugin">
              <el-select
                v-model="filters.plugin_name"
                placeholder="全部"
                clearable
                filterable
                style="width: 180px"
              >
                <el-option
                  v-for="item in options.plugin_names"
                  :key="item"
                  :label="item"
                  :value="item"
                />
              </el-select>
            </el-form-item>

            <el-form-item label="Module">
              <el-select
                v-model="filters.module_name"
                placeholder="全部"
                clearable
                filterable
                style="width: 180px"
              >
                <el-option
                  v-for="item in options.module_names"
                  :key="item"
                  :label="item"
                  :value="item"
                />
              </el-select>
            </el-form-item>

            <el-form-item label="Operation">
              <el-select
                v-model="filters.operation"
                placeholder="全部"
                clearable
                filterable
                style="width: 200px"
              >
                <el-option
                  v-for="item in options.operations"
                  :key="item"
                  :label="item"
                  :value="item"
                />
              </el-select>
            </el-form-item>

            <el-form-item label="Conv ID">
              <el-select
                v-model="filters.conv_id"
                placeholder="全部"
                clearable
                filterable
                style="width: 220px"
              >
                <el-option
                  v-for="item in options.conv_ids"
                  :key="item"
                  :label="item"
                  :value="item"
                />
              </el-select>
            </el-form-item>
          </el-form>
        </div>
      </el-collapse-transition>
    </el-card>

    <div
      v-if="mode === PAGE_MODE_OVERVIEW"
      class="overview-panel"
      v-loading="loading.overview"
    >
      <el-empty
        v-if="filteredOverviewItems.length === 0 && !loading.overview"
        description="暂无匹配模块"
      />

      <div v-else class="module-grid">
        <el-card
          v-for="item in filteredOverviewItems"
          :key="item.module_id"
          class="module-card"
          shadow="hover"
          :data-testid="`module-card-${item.module_id}`"
        >
          <template #header>
            <div class="module-card-header">
              <div class="module-card-title">
                <h4>{{ resolveModuleTitle(item) }}</h4>
                <p>{{ item.module_id }}</p>
              </div>
              <el-tooltip content="放大查看详情" placement="top">
                <el-button
                  circle
                  size="small"
                  type="primary"
                  plain
                  @click="handleFocus(item.module_id)"
                  :data-testid="`module-focus-${item.module_id}`"
                >
                  <el-icon><FullScreen /></el-icon>
                </el-button>
              </el-tooltip>
            </div>
          </template>

          <p class="module-description">{{ resolveModuleDescription(item) }}</p>

          <div v-if="getCardKpis(item).length > 0" class="module-kpi-strip">
            <div
              v-for="kpi in getCardKpis(item)"
              :key="kpi.key || kpi.label"
              class="module-kpi-item"
            >
              <span>{{ kpi.label || kpi.key }}</span>
              <strong>{{ formatKpiPreview(kpi) }}</strong>
            </div>
          </div>

          <ChartRenderer
            v-if="item.main_chart"
            :chart="item.main_chart"
            :height="260"
            :show-title="false"
            compact
          />
          <el-empty
            v-else
            class="module-chart-empty"
            description="暂无主图数据"
            :image-size="56"
          />
        </el-card>
      </div>
    </div>

    <div v-else class="focus-panel" data-testid="module-focus-panel">
      <el-card class="focus-header-card" shadow="never">
        <div class="focus-header">
          <div class="focus-title">
            <h3>{{ focusedModuleTitle }}</h3>
            <p>{{ focusedModuleId }}</p>
          </div>
          <div class="focus-actions">
            <el-button
              @click="backToOverview"
              data-testid="module-back-overview"
            >
              <el-icon><ArrowLeft /></el-icon>
              返回 overview
            </el-button>
            <el-button
              type="primary"
              :loading="loading.detail || loading.overview"
              @click="handleSearch"
            >
              刷新详情
            </el-button>
          </div>
        </div>
      </el-card>

      <div class="detail-grid" v-loading="loading.detail">
        <el-empty
          v-if="detailCharts.length === 0 && !loading.detail"
          description="暂无详情图表"
        />
        <el-card
          v-for="chart in detailCharts"
          :key="chart.chart_id || chart.title"
          class="detail-card"
          :class="resolveDetailCardClass(chart)"
          shadow="never"
        >
          <ChartRenderer
            :chart="chart"
            :height="resolveDetailChartHeight(chart)"
          />
        </el-card>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import { ElMessage } from "element-plus";
import { ArrowLeft, Filter, FullScreen, Search } from "@element-plus/icons-vue";

import ChartRenderer from "@/components/module-metrics/ChartRenderer.vue";
import {
  fetchModuleMetricDetail,
  fetchModuleMetricModules,
  fetchModuleMetricOptions,
  fetchModuleMetricOverview,
} from "@/api/module_metrics";
import type {
  ModuleMetricChart,
  ModuleMetricDefinition,
  ModuleMetricDetailPayload,
  ModuleMetricKpi,
  ModuleMetricOptionsPayload,
  ModuleMetricOverviewItem,
  ModuleMetricQueryParams,
} from "@/types/module_metrics";

type DateRange = [Date, Date];

interface ModuleFilters {
  plugin_name: string;
  module_name: string;
  operation: string;
  conv_id: string;
}

interface LoadingState {
  modules: boolean;
  options: boolean;
  overview: boolean;
  detail: boolean;
}

const PAGE_MODE_OVERVIEW = "overview";
const PAGE_MODE_FOCUS = "focus";
const DAY_MS = 24 * 60 * 60 * 1000;

const buildDefaultDateRange = (): DateRange => {
  const end = new Date();
  const start = new Date(end.getTime() - 7 * DAY_MS);
  return [start, end];
};

const mode = ref(PAGE_MODE_OVERVIEW);
const focusedModuleId = ref("");
const focusedDetail = ref<ModuleMetricDetailPayload | null>(null);

const dateRange = ref<DateRange>(buildDefaultDateRange());
const searchKeyword = ref("");
const showAdvanced = ref(false);

const filters = reactive<ModuleFilters>({
  plugin_name: "",
  module_name: "",
  operation: "",
  conv_id: "",
});

const options = reactive<ModuleMetricOptionsPayload>({
  plugin_names: [],
  module_names: [],
  operations: [],
  conv_ids: [],
});

const loading = reactive<LoadingState>({
  modules: false,
  options: false,
  overview: false,
  detail: false,
});

const moduleDefinitions = ref<ModuleMetricDefinition[]>([]);
const overviewItems = ref<ModuleMetricOverviewItem[]>([]);

const modeTagText = computed(() => {
  return mode.value === PAGE_MODE_OVERVIEW ? "Overview" : "Focus";
});

const isRefreshing = computed(() => {
  return (
    loading.modules || loading.options || loading.overview || loading.detail
  );
});

const moduleDefinitionMap = computed(() => {
  const mapping: Record<string, ModuleMetricDefinition> = {};
  for (const item of moduleDefinitions.value) {
    const moduleId = String(item?.module_id || "").trim();
    if (!moduleId) {
      continue;
    }
    mapping[moduleId] = item;
  }
  return mapping;
});

const normalizedOverviewItems = computed(() => {
  const items: ModuleMetricOverviewItem[] = [];
  for (const raw of overviewItems.value) {
    if (!raw || typeof raw !== "object") {
      continue;
    }
    const moduleId = String(raw.module_id || "").trim();
    if (!moduleId) {
      continue;
    }
    const definition = moduleDefinitionMap.value[moduleId];
    items.push({
      ...definition,
      ...raw,
      module_id: moduleId,
      title: raw.title || definition?.title || moduleId,
      kpis: Array.isArray(raw.kpis) ? raw.kpis : [],
      main_chart:
        raw.main_chart && typeof raw.main_chart === "object"
          ? raw.main_chart
          : null,
    });
  }
  return items;
});

const mergedOverviewItems = computed(() => {
  const ordered: ModuleMetricOverviewItem[] = [];
  const seen = new Set();
  const overviewById: Record<string, ModuleMetricOverviewItem> = {};

  for (const item of normalizedOverviewItems.value) {
    overviewById[item.module_id] = item;
  }

  for (const definition of moduleDefinitions.value) {
    const moduleId = String(definition?.module_id || "").trim();
    if (!moduleId || seen.has(moduleId)) {
      continue;
    }
    seen.add(moduleId);
    if (overviewById[moduleId]) {
      ordered.push(overviewById[moduleId]);
      continue;
    }
    ordered.push({
      ...definition,
      module_id: moduleId,
      title: definition?.title || moduleId,
      kpis: [],
      main_chart: null,
    });
  }

  for (const item of normalizedOverviewItems.value) {
    if (seen.has(item.module_id)) {
      continue;
    }
    seen.add(item.module_id);
    ordered.push(item);
  }

  return ordered;
});

const filteredOverviewItems = computed(() => {
  const keyword = String(searchKeyword.value || "")
    .trim()
    .toLowerCase();
  if (!keyword) {
    return mergedOverviewItems.value;
  }
  return mergedOverviewItems.value.filter((item) => {
    const candidates = [
      item.module_id,
      item.title,
      item.description,
      item.plugin_name,
      item.module_name,
    ];
    return candidates.some((value) =>
      String(value || "")
        .toLowerCase()
        .includes(keyword),
    );
  });
});

const detailCharts = computed(() => {
  const charts = focusedDetail.value?.charts;
  return Array.isArray(charts) ? charts : ([] as ModuleMetricChart[]);
});

const focusedModuleTitle = computed(() => {
  const detailTitle = String(focusedDetail.value?.title || "").trim();
  if (detailTitle) {
    return detailTitle;
  }
  const definition = moduleDefinitionMap.value[focusedModuleId.value];
  return String(definition?.title || focusedModuleId.value || "模块详情");
});

const pad = (value: number | string) => String(value).padStart(2, "0");

const toApiDateTime = (date: Date | null | undefined): string | null => {
  if (!(date instanceof Date) || Number.isNaN(date.getTime())) {
    return null;
  }
  const year = date.getFullYear();
  const month = pad(date.getMonth() + 1);
  const day = pad(date.getDate());
  const hour = pad(date.getHours());
  const minute = pad(date.getMinutes());
  const second = pad(date.getSeconds());
  return `${year}-${month}-${day}T${hour}:${minute}:${second}`;
};

const buildBaseParams = (): ModuleMetricQueryParams => {
  const params: ModuleMetricQueryParams = {};

  if (Array.isArray(dateRange.value) && dateRange.value.length === 2) {
    const [fromTime, toTime] = dateRange.value;
    const fromValue = toApiDateTime(fromTime);
    const toValue = toApiDateTime(toTime);
    if (fromValue) {
      params.from = fromValue;
    }
    if (toValue) {
      params.to = toValue;
    }
  }

  if (filters.plugin_name) {
    params.plugin_name = filters.plugin_name;
  }
  if (filters.module_name) {
    params.module_name = filters.module_name;
  }
  if (filters.operation) {
    params.operation = filters.operation;
  }
  if (filters.conv_id) {
    params.conv_id = filters.conv_id;
  }

  return params;
};

const formatKpiPreview = (kpi: ModuleMetricKpi): string => {
  const format = String(kpi?.format || "").toLowerCase();
  const number = Number(kpi?.value);
  if (format === "percent") {
    return Number.isFinite(number) ? `${(number * 100).toFixed(2)}%` : "0.00%";
  }
  if (format === "decimal") {
    return Number.isFinite(number) ? number.toFixed(2) : "0.00";
  }
  if (Number.isFinite(number)) {
    return Math.round(number).toLocaleString();
  }
  if (kpi?.value == null || kpi.value === "") {
    return "-";
  }
  return String(kpi.value);
};

const resolveModuleTitle = (item: ModuleMetricOverviewItem): string => {
  return String(item?.title || item?.module_id || "未命名模块");
};

const resolveModuleDescription = (item: ModuleMetricOverviewItem): string => {
  const description = String(item?.description || "").trim();
  if (description) {
    return description;
  }
  const pluginName = String(item?.plugin_name || "-");
  const moduleName = String(item?.module_name || "-");
  return `${pluginName} / ${moduleName}`;
};

const getCardKpis = (item: ModuleMetricOverviewItem): ModuleMetricKpi[] => {
  if (!Array.isArray(item?.kpis)) {
    return [];
  }
  return item.kpis.slice(0, 3);
};

const resolveDetailCardClass = (chart: ModuleMetricChart): string => {
  const type = String(chart?.type || "").toLowerCase();
  return type ? `detail-card--${type}` : "detail-card--default";
};

const resolveDetailChartHeight = (chart: ModuleMetricChart): number => {
  const type = String(chart?.type || "").toLowerCase();
  if (type === "table") {
    return 420;
  }
  if (type === "kpi") {
    return 200;
  }
  if (type === "pie") {
    return 320;
  }
  return 340;
};

const loadModules = async () => {
  loading.modules = true;
  try {
    const { data } = await fetchModuleMetricModules();
    moduleDefinitions.value = Array.isArray(data?.items) ? data.items : [];
  } catch (error) {
    moduleDefinitions.value = [];
    ElMessage.error("加载模块定义失败");
  } finally {
    loading.modules = false;
  }
};

const loadOptions = async () => {
  loading.options = true;
  try {
    const { data } = await fetchModuleMetricOptions(buildBaseParams());
    options.plugin_names = Array.isArray(data?.plugin_names)
      ? data.plugin_names
      : [];
    options.module_names = Array.isArray(data?.module_names)
      ? data.module_names
      : [];
    options.operations = Array.isArray(data?.operations) ? data.operations : [];
    options.conv_ids = Array.isArray(data?.conv_ids) ? data.conv_ids : [];
  } catch (error) {
    options.plugin_names = [];
    options.module_names = [];
    options.operations = [];
    options.conv_ids = [];
    ElMessage.error("加载筛选项失败");
  } finally {
    loading.options = false;
  }
};

const loadOverview = async () => {
  loading.overview = true;
  try {
    const { data } = await fetchModuleMetricOverview(buildBaseParams());
    overviewItems.value = Array.isArray(data?.items) ? data.items : [];
  } catch (error) {
    overviewItems.value = [];
    ElMessage.error("加载模块总览失败");
  } finally {
    loading.overview = false;
  }
};

const loadFocusDetail = async () => {
  const moduleId = String(focusedModuleId.value || "").trim();
  if (!moduleId) {
    focusedDetail.value = null;
    return;
  }
  loading.detail = true;
  try {
    const { data } = await fetchModuleMetricDetail(moduleId, buildBaseParams());
    focusedDetail.value =
      data && typeof data === "object"
        ? data
        : { module_id: moduleId, charts: [] };
  } catch (error) {
    focusedDetail.value = { module_id: moduleId, charts: [] };
    ElMessage.error("加载模块详情失败");
  } finally {
    loading.detail = false;
  }
};

const refreshPage = async () => {
  const tasks = [loadModules(), loadOptions(), loadOverview()];
  if (mode.value === PAGE_MODE_FOCUS && focusedModuleId.value) {
    tasks.push(loadFocusDetail());
  }
  await Promise.all(tasks);
};

const handleSearch = async () => {
  await refreshPage();
};

const handleReset = async () => {
  dateRange.value = buildDefaultDateRange();
  searchKeyword.value = "";
  filters.plugin_name = "";
  filters.module_name = "";
  filters.operation = "";
  filters.conv_id = "";
  await refreshPage();
};

const toggleAdvanced = () => {
  showAdvanced.value = !showAdvanced.value;
};

const handleFocus = async (moduleId: string): Promise<void> => {
  focusedModuleId.value = String(moduleId || "").trim();
  mode.value = PAGE_MODE_FOCUS;
  await loadFocusDetail();
};

const backToOverview = () => {
  mode.value = PAGE_MODE_OVERVIEW;
  focusedModuleId.value = "";
  focusedDetail.value = null;
};

onMounted(async () => {
  await refreshPage();
});
</script>

<style scoped>
.module-metrics-page {
  display: flex;
  flex-direction: column;
  flex: 0 0 auto;
  gap: 16px;
  width: 100%;
  min-height: 0;
}

.toolbar-card {
  width: 100%;
  flex: 0 0 auto;
}

.toolbar-card :deep(.el-card__body) {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.toolbar-main {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 12px;
}

.toolbar-title {
  display: flex;
  align-items: center;
  gap: 10px;
}

.toolbar-title h3 {
  margin: 0;
}

.toolbar-actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 8px;
  flex-wrap: wrap;
  flex: 1 1 auto;
  min-width: 0;
}

.search-input {
  width: 420px;
  max-width: 100%;
  min-width: 260px;
  flex: 0 0 420px;
}

.advanced-filter-wrap {
  border-top: 1px solid #ebeef5;
  padding-top: 12px;
}

.filter-form {
  display: flex;
  flex-wrap: wrap;
  row-gap: 8px;
}

.filter-form :deep(.el-form-item) {
  margin-bottom: 0;
}

.overview-panel,
.focus-panel {
  display: flex;
  flex-direction: column;
  gap: 12px;
  min-height: 0;
}

.module-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(340px, 1fr));
  grid-auto-flow: dense;
  gap: 12px;
  align-items: start;
}

.module-card {
  min-height: 0;
}

.module-card :deep(.el-card__body) {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.module-card-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.module-card-title h4 {
  margin: 0;
  font-size: 16px;
}

.module-card-title p {
  margin: 4px 0 0;
  font-size: 12px;
  color: #909399;
  font-family:
    ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono",
    "Courier New", monospace;
}

.module-description {
  margin: 0;
  font-size: 13px;
  color: #606266;
}

.module-kpi-strip {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(100px, 1fr));
  gap: 8px;
}

.module-kpi-item {
  border: 1px solid #ebeef5;
  border-radius: 8px;
  padding: 8px 10px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.module-kpi-item span {
  font-size: 12px;
  color: #606266;
}

.module-kpi-item strong {
  font-size: 16px;
  color: #303133;
}

.module-chart-empty {
  min-height: 180px;
}

.focus-header-card :deep(.el-card__body) {
  padding: 14px 18px;
}

.focus-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}

.focus-title h3 {
  margin: 0;
}

.focus-title p {
  margin: 4px 0 0;
  font-size: 12px;
  color: #909399;
  font-family:
    ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono",
    "Courier New", monospace;
}

.focus-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.detail-grid {
  display: grid;
  grid-template-columns: repeat(12, minmax(0, 1fr));
  gap: 12px;
  align-items: start;
}

.detail-card {
  grid-column: span 6;
  min-height: 0;
}

.detail-card--kpi,
.detail-card--table {
  grid-column: 1 / -1;
}

.detail-card :deep(.el-card__body) {
  min-height: 0;
}

@media (max-width: 1280px) {
  .module-grid {
    grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  }
}

@media (max-width: 960px) {
  .detail-card {
    grid-column: 1 / -1;
  }

  .search-input {
    width: 100%;
    min-width: 0;
    flex: 1 1 100%;
  }
}

@media (max-width: 768px) {
  .toolbar-main {
    align-items: stretch;
  }

  .toolbar-actions {
    width: 100%;
    justify-content: flex-start;
  }

  .filter-form {
    flex-direction: column;
    align-items: stretch;
  }

  .filter-form :deep(.el-form-item__content) {
    width: 100%;
  }

  .module-grid {
    grid-template-columns: repeat(1, minmax(0, 1fr));
  }
}
</style>
