<template>
  <div class="module-metrics-page">
    <el-card class="filter-card" shadow="never">
      <template #header>
        <div class="card-header-row">
          <h3>模块统计</h3>
          <div class="header-actions">
            <el-button @click="handleReset">重置</el-button>
            <el-button
              type="primary"
              :loading="isRefreshing"
              @click="handleSearch"
              >刷新</el-button
            >
          </div>
        </div>
      </template>

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

        <el-form-item label="聚合粒度">
          <el-select v-model="filters.interval" style="width: 120px">
            <el-option label="按天" value="day" />
            <el-option label="按小时" value="hour" />
          </el-select>
        </el-form-item>
      </el-form>
    </el-card>

    <div class="kpi-grid">
      <el-card class="kpi-card" shadow="never">
        <div class="kpi-label">调用次数</div>
        <div class="kpi-value">{{ formatInteger(summary.total_calls) }}</div>
      </el-card>
      <el-card class="kpi-card" shadow="never">
        <div class="kpi-label">失败次数</div>
        <div class="kpi-value is-danger">
          {{ formatInteger(summary.failed_calls) }}
        </div>
      </el-card>
      <el-card class="kpi-card" shadow="never">
        <div class="kpi-label">成功率</div>
        <div class="kpi-value">{{ formatPercent(summary.success_rate) }}</div>
      </el-card>
      <el-card class="kpi-card" shadow="never">
        <div class="kpi-label">总 Tokens</div>
        <div class="kpi-value">{{ formatInteger(summary.total_tokens) }}</div>
      </el-card>
      <el-card class="kpi-card" shadow="never">
        <div class="kpi-label">平均 Tokens/次</div>
        <div class="kpi-value">
          {{ formatDecimal(summary.avg_tokens_per_call) }}
        </div>
      </el-card>
    </div>

    <el-card class="trend-card" shadow="never">
      <template #header>
        <div class="card-header-row">
          <h4>调用与 Tokens 趋势</h4>
        </div>
      </template>
      <div
        ref="trendChartRef"
        v-loading="loading.summary"
        class="trend-chart"
      />
    </el-card>

    <el-card class="events-card" shadow="never">
      <template #header>
        <div class="card-header-row">
          <h4>事件明细</h4>
        </div>
      </template>

      <el-table
        v-loading="loading.events"
        :data="eventItems"
        border
        stripe
        style="width: 100%"
        max-height="420"
      >
        <el-table-column label="时间" min-width="170">
          <template #default="scope">
            {{ formatDateTime(scope.row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column prop="plugin_name" label="Plugin" min-width="120" />
        <el-table-column prop="module_name" label="Module" min-width="140" />
        <el-table-column prop="operation" label="Operation" min-width="150" />
        <el-table-column
          prop="conv_id"
          label="Conv ID"
          min-width="160"
          show-overflow-tooltip
        />
        <el-table-column
          prop="prompt_tokens"
          label="Prompt"
          min-width="90"
          align="right"
        />
        <el-table-column
          prop="completion_tokens"
          label="Completion"
          min-width="110"
          align="right"
        />
        <el-table-column
          prop="total_tokens"
          label="Total"
          min-width="90"
          align="right"
        />
        <el-table-column label="结果" width="90" align="center">
          <template #default="scope">
            <el-tag
              :type="scope.row.success ? 'success' : 'danger'"
              size="small"
            >
              {{ scope.row.success ? "成功" : "失败" }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column
          prop="error_type"
          label="错误类型"
          min-width="120"
          show-overflow-tooltip
        />
        <el-table-column
          prop="request_id"
          label="Request ID"
          min-width="180"
          show-overflow-tooltip
        >
          <template #default="scope">
            <span class="mono">{{ scope.row.request_id || "-" }}</span>
          </template>
        </el-table-column>
      </el-table>

      <div class="pagination-wrap">
        <el-pagination
          v-model:current-page="pagination.page"
          v-model:page-size="pagination.size"
          background
          layout="total, sizes, prev, pager, next"
          :page-sizes="[20, 50, 100]"
          :total="pagination.total"
          @current-change="handlePageChange"
          @size-change="handleSizeChange"
        />
      </div>
    </el-card>
  </div>
</template>

<script setup>
import {
  computed,
  nextTick,
  onBeforeUnmount,
  onMounted,
  reactive,
  ref,
} from "vue";
import { ElMessage } from "element-plus";
import * as echarts from "echarts";

import {
  fetchModuleMetricEvents,
  fetchModuleMetricOptions,
  fetchModuleMetricSummary,
} from "@/api/module_metrics";

const DAY_MS = 24 * 60 * 60 * 1000;

const buildDefaultDateRange = () => {
  const end = new Date();
  const start = new Date(end.getTime() - 7 * DAY_MS);
  return [start, end];
};

const dateRange = ref(buildDefaultDateRange());

const filters = reactive({
  plugin_name: "",
  module_name: "",
  operation: "",
  conv_id: "",
  interval: "day",
});

const options = reactive({
  plugin_names: [],
  module_names: [],
  operations: [],
  conv_ids: [],
});

const summary = reactive({
  total_calls: 0,
  failed_calls: 0,
  success_rate: 0,
  total_tokens: 0,
  avg_tokens_per_call: 0,
  trends: [],
});

const eventItems = ref([]);

const pagination = reactive({
  page: 1,
  size: 20,
  total: 0,
});

const loading = reactive({
  options: false,
  summary: false,
  events: false,
});

const trendChartRef = ref(null);
let trendChart = null;

const isRefreshing = computed(() => {
  return loading.options || loading.summary || loading.events;
});

const pad = (value) => String(value).padStart(2, "0");

const toApiDateTime = (date) => {
  if (!(date instanceof Date)) {
    return null;
  }
  if (Number.isNaN(date.getTime())) {
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

const buildBaseParams = () => {
  const params = {};

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

const formatInteger = (value) => {
  const number = Number(value || 0);
  return Number.isFinite(number) ? number.toLocaleString() : "0";
};

const formatDecimal = (value) => {
  const number = Number(value || 0);
  if (!Number.isFinite(number)) {
    return "0.00";
  }
  return number.toFixed(2);
};

const formatPercent = (value) => {
  const number = Number(value || 0);
  if (!Number.isFinite(number)) {
    return "0.00%";
  }
  return `${(number * 100).toFixed(2)}%`;
};

const formatDateTime = (value) => {
  if (!value) {
    return "-";
  }
  const date = new Date(value);
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

const formatTrendTime = (value) => {
  if (!value) {
    return "-";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return String(value);
  }
  const month = pad(date.getMonth() + 1);
  const day = pad(date.getDate());
  const hour = pad(date.getHours());
  return filters.interval === "hour"
    ? `${month}-${day} ${hour}:00`
    : `${date.getFullYear()}-${month}-${day}`;
};

const initTrendChart = () => {
  if (!trendChartRef.value) {
    return;
  }
  if (trendChart) {
    trendChart.dispose();
  }
  trendChart = echarts.init(trendChartRef.value);
  renderTrendChart();
};

const renderTrendChart = () => {
  if (!trendChart) {
    return;
  }

  const trends = Array.isArray(summary.trends) ? summary.trends : [];
  const xAxis = trends.map((item) => formatTrendTime(item.time));
  const callsSeries = trends.map((item) => Number(item.total_calls || 0));
  const tokensSeries = trends.map((item) => Number(item.total_tokens || 0));

  trendChart.setOption(
    {
      tooltip: {
        trigger: "axis",
      },
      legend: {
        data: ["调用次数", "总 Tokens"],
      },
      grid: {
        left: 40,
        right: 40,
        top: 40,
        bottom: 30,
      },
      xAxis: {
        type: "category",
        data: xAxis,
      },
      yAxis: [
        {
          type: "value",
          name: "调用次数",
          minInterval: 1,
        },
        {
          type: "value",
          name: "Tokens",
        },
      ],
      series: [
        {
          name: "调用次数",
          type: "line",
          smooth: true,
          yAxisIndex: 0,
          data: callsSeries,
        },
        {
          name: "总 Tokens",
          type: "line",
          smooth: true,
          yAxisIndex: 1,
          data: tokensSeries,
        },
      ],
    },
    true,
  );
};

const handleResize = () => {
  if (trendChart) {
    trendChart.resize();
  }
};

const loadOptions = async () => {
  loading.options = true;
  try {
    const { data } = await fetchModuleMetricOptions(buildBaseParams());
    options.plugin_names = data.plugin_names || [];
    options.module_names = data.module_names || [];
    options.operations = data.operations || [];
    options.conv_ids = data.conv_ids || [];
  } catch (error) {
    ElMessage.error("加载筛选项失败");
  } finally {
    loading.options = false;
  }
};

const loadSummary = async () => {
  loading.summary = true;
  try {
    const { data } = await fetchModuleMetricSummary({
      ...buildBaseParams(),
      interval: filters.interval,
    });
    summary.total_calls = Number(data.total_calls || 0);
    summary.failed_calls = Number(data.failed_calls || 0);
    summary.success_rate = Number(data.success_rate || 0);
    summary.total_tokens = Number(data.total_tokens || 0);
    summary.avg_tokens_per_call = Number(data.avg_tokens_per_call || 0);
    summary.trends = Array.isArray(data.trends) ? data.trends : [];
    await nextTick();
    renderTrendChart();
  } catch (error) {
    summary.total_calls = 0;
    summary.failed_calls = 0;
    summary.success_rate = 0;
    summary.total_tokens = 0;
    summary.avg_tokens_per_call = 0;
    summary.trends = [];
    renderTrendChart();
    ElMessage.error("加载汇总统计失败");
  } finally {
    loading.summary = false;
  }
};

const loadEvents = async () => {
  loading.events = true;
  try {
    const { data } = await fetchModuleMetricEvents({
      ...buildBaseParams(),
      page: pagination.page,
      size: pagination.size,
    });
    eventItems.value = data.items || [];
    pagination.total = Number(data.total || 0);
    pagination.page = Number(data.page || pagination.page);
    pagination.size = Number(data.size || pagination.size);
  } catch (error) {
    eventItems.value = [];
    pagination.total = 0;
    ElMessage.error("加载事件明细失败");
  } finally {
    loading.events = false;
  }
};

const refreshAll = async () => {
  await Promise.all([loadOptions(), loadSummary(), loadEvents()]);
};

const handleSearch = async () => {
  pagination.page = 1;
  await refreshAll();
};

const handleReset = async () => {
  dateRange.value = buildDefaultDateRange();
  filters.plugin_name = "";
  filters.module_name = "";
  filters.operation = "";
  filters.conv_id = "";
  filters.interval = "day";
  pagination.page = 1;
  pagination.size = 20;
  await refreshAll();
};

const handlePageChange = async (page) => {
  pagination.page = page;
  await loadEvents();
};

const handleSizeChange = async (size) => {
  pagination.size = size;
  pagination.page = 1;
  await loadEvents();
};

onMounted(async () => {
  initTrendChart();
  window.addEventListener("resize", handleResize);
  await refreshAll();
});

onBeforeUnmount(() => {
  window.removeEventListener("resize", handleResize);
  if (trendChart) {
    trendChart.dispose();
    trendChart = null;
  }
});
</script>

<style scoped>
.module-metrics-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
  flex: 1;
  min-height: 0;
}

.filter-card,
.trend-card,
.events-card {
  width: 100%;
}

.card-header-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.card-header-row h3,
.card-header-row h4 {
  margin: 0;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.filter-form {
  display: flex;
  flex-wrap: wrap;
  row-gap: 6px;
}

.filter-form :deep(.el-form-item) {
  margin-bottom: 8px;
}

.kpi-grid {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 12px;
}

.kpi-card {
  border-radius: 8px;
}

.kpi-label {
  font-size: 13px;
  color: #606266;
  margin-bottom: 6px;
}

.kpi-value {
  font-size: 24px;
  line-height: 1.2;
  color: #303133;
  font-weight: 600;
}

.kpi-value.is-danger {
  color: #f56c6c;
}

.trend-chart {
  width: 100%;
  height: 320px;
}

.events-card :deep(.el-card__body) {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.pagination-wrap {
  display: flex;
  justify-content: flex-end;
}

.mono {
  font-family:
    ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono",
    "Courier New", monospace;
}

@media (max-width: 1280px) {
  .kpi-grid {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}

@media (max-width: 768px) {
  .kpi-grid {
    grid-template-columns: repeat(1, minmax(0, 1fr));
  }

  .filter-form {
    flex-direction: column;
    align-items: stretch;
  }

  .filter-form :deep(.el-form-item__content) {
    width: 100%;
  }
}
</style>
