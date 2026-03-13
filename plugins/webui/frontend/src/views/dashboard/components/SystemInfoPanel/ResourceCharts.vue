<template>
  <div class="charts-area">
    <div class="chart-container">
      <h4>CPU使用率历史</h4>
      <div class="loading-container" v-if="loading">
        <el-icon class="is-loading"><Loading /></el-icon>
      </div>
      <div ref="cpuChartRef" class="chart"></div>
    </div>
    <div class="chart-container">
      <h4>内存使用率历史</h4>
      <div class="loading-container" v-if="loading">
        <el-icon class="is-loading"><Loading /></el-icon>
      </div>
      <div ref="memoryChartRef" class="chart"></div>
    </div>
  </div>
</template>

<script setup>
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { Loading } from "@element-plus/icons-vue";
import {
  createResizeObserver,
  disconnectObserver,
  disposeChart,
  loadCoreEchartsRuntime,
} from "@/utils/echarts";

// 工具函数：格式化时间戳为时:分:秒
function formatTimestamp(timestamp) {
  try {
    const date = new Date(Number(timestamp));
    if (isNaN(date.getTime())) {
      return null;
    }
    const hours = String(date.getHours()).padStart(2, "0");
    const minutes = String(date.getMinutes()).padStart(2, "0");
    const seconds = String(date.getSeconds()).padStart(2, "0");
    return `${hours}:${minutes}:${seconds}`;
  } catch (e) {
    return null;
  }
}

// 定义属性
const props = defineProps({
  cpuData: {
    type: Array,
    required: true,
  },
  memoryData: {
    type: Array,
    required: true,
  },
  timeData: {
    type: Array,
    required: true,
  },
  loading: {
    type: Boolean,
    default: false,
  },
});

// 图表引用
const cpuChartRef = ref(null);
const memoryChartRef = ref(null);
let cpuChart = null;
let memoryChart = null;
let cpuResizeObserver = null;
let memoryResizeObserver = null;
let echartsRuntime = null;

const ensureRuntime = async () => {
  if (!echartsRuntime) {
    echartsRuntime = await loadCoreEchartsRuntime();
  }
  return echartsRuntime;
};

const buildResourceChartOption = (seriesName, color, data = []) => ({
  title: {
    text: "",
    left: "center",
  },
  tooltip: {
    trigger: "axis",
    formatter(params) {
      const timeStr = formatTimestamp(params[0]?.axisValue);
      if (!timeStr) {
        return `时间: 未知<br/>${seriesName}: ${params[0]?.value ?? "-"}%`;
      }
      return `时间: ${timeStr}<br/>${seriesName}: ${params[0]?.value ?? "-"}%`;
    },
  },
  grid: {
    left: "3%",
    right: "4%",
    bottom: "3%",
    top: "8%",
    containLabel: true,
  },
  xAxis: {
    type: "category",
    boundaryGap: false,
    data: props.timeData || [],
    axisLabel: {
      formatter: (value) => {
        const timeStr = formatTimestamp(value);
        return timeStr || "-";
      },
    },
  },
  yAxis: {
    type: "value",
    min: 0,
    max: 100,
    axisLabel: {
      formatter: "{value}%",
    },
  },
  series: [
    {
      name: seriesName,
      type: "line",
      smooth: true,
      data,
      areaStyle: {
        opacity: 0.3,
      },
      itemStyle: {
        color,
      },
    },
  ],
});

const ensureCpuChart = async () => {
  await nextTick();
  if (!cpuChartRef.value) {
    return null;
  }
  if (!cpuChart) {
    const runtime = await ensureRuntime();
    cpuChart = runtime.init(cpuChartRef.value);
    cpuResizeObserver = disconnectObserver(cpuResizeObserver);
    cpuResizeObserver = createResizeObserver(cpuChartRef.value, () => {
      cpuChart?.resize();
    });
  }
  return cpuChart;
};

const ensureMemoryChart = async () => {
  await nextTick();
  if (!memoryChartRef.value) {
    return null;
  }
  if (!memoryChart) {
    const runtime = await ensureRuntime();
    memoryChart = runtime.init(memoryChartRef.value);
    memoryResizeObserver = disconnectObserver(memoryResizeObserver);
    memoryResizeObserver = createResizeObserver(memoryChartRef.value, () => {
      memoryChart?.resize();
    });
  }
  return memoryChart;
};

const renderCharts = async () => {
  try {
    const [cpuInstance, memoryInstance] = await Promise.all([
      ensureCpuChart(),
      ensureMemoryChart(),
    ]);

    cpuInstance?.setOption(
      buildResourceChartOption("CPU使用率", "#409EFF", props.cpuData || []),
      true,
    );
    memoryInstance?.setOption(
      buildResourceChartOption("内存使用率", "#67C23A", props.memoryData || []),
      true,
    );

    cpuInstance?.resize();
    memoryInstance?.resize();
  } catch (error) {
    console.error("渲染资源图表时出错:", error);
  }
};

// 监听数据变化，更新图表
watch(
  () => [props.cpuData, props.memoryData, props.timeData],
  () => {
    void renderCharts();
  },
  { deep: true },
);

// 生命周期钩子
onMounted(() => {
  void renderCharts();
});

onBeforeUnmount(() => {
  cpuResizeObserver = disconnectObserver(cpuResizeObserver);
  memoryResizeObserver = disconnectObserver(memoryResizeObserver);
  cpuChart = disposeChart(cpuChart);
  memoryChart = disposeChart(memoryChart);
});
</script>

<style scoped>
.charts-area {
  display: flex;
  gap: 15px;
  margin-bottom: 15px;
}

.chart-container {
  flex: 1;
  min-height: 200px;
  position: relative;
}

.chart {
  height: 200px;
  width: 100%;
}

h4 {
  margin: 0 0 10px 0;
  color: #606266;
  font-size: 14px;
  text-align: center;
}

.loading-container {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  display: flex;
  justify-content: center;
  align-items: center;
  background: rgba(255, 255, 255, 0.7);
  z-index: 1;
}

/* 响应式设计 */
@media (max-width: 992px) {
  .charts-area {
    flex-direction: column;
  }
}
</style>
