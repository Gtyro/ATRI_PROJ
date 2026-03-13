<template>
  <div class="heatmap-container">
    <div ref="heatmapRef" class="heatmap-chart"></div>
  </div>
</template>

<script setup>
import { nextTick, onMounted, onUnmounted, ref, watch } from "vue";

import {
  createResizeObserver,
  disconnectObserver,
  disposeChart,
  loadCoreEchartsRuntime,
} from "@/utils/echarts";

const props = defineProps({
  heatmapData: {
    type: Array,
    default: () => [],
  },
  startDate: {
    type: String,
    default: "",
  },
  endDate: {
    type: String,
    default: "",
  },
});

const heatmapRef = ref(null);
let heatmapChart = null;
let resizeObserver = null;
let echartsRuntime = null;

const formatDateKey = (value) => {
  const date = value instanceof Date ? value : new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "";
  }

  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
};

const buildFallbackRange = () => {
  const end = new Date();
  const start = new Date();
  start.setMonth(end.getMonth() - 3);
  return [formatDateKey(start), formatDateKey(end)];
};

const normalizeHeatmapData = () => {
  if (!Array.isArray(props.heatmapData)) {
    return [];
  }
  return props.heatmapData
    .map((item) => {
      if (!Array.isArray(item) || item.length < 2) {
        return null;
      }
      const date = String(item[0] || "").trim();
      if (!date) {
        return null;
      }
      return [date, Number(item[1]) || 0];
    })
    .filter(Boolean);
};

const ensureRuntime = async () => {
  if (!echartsRuntime) {
    echartsRuntime = await loadCoreEchartsRuntime();
  }
  return echartsRuntime;
};

const initHeatmap = async () => {
  await nextTick();
  if (!heatmapRef.value || heatmapChart) return;

  const runtime = await ensureRuntime();
  heatmapChart = runtime.init(heatmapRef.value);
  resizeObserver = disconnectObserver(resizeObserver);
  resizeObserver = createResizeObserver(heatmapRef.value, handleResize);
};

const renderHeatmap = async () => {
  if (!heatmapChart) {
    await initHeatmap();
  }
  if (!heatmapChart) return;

  const data = normalizeHeatmapData();
  const [fallbackStart, fallbackEnd] = buildFallbackRange();
  const startDate = props.startDate || fallbackStart;
  const endDate = props.endDate || fallbackEnd;
  const maxValue = Math.max(1, ...data.map((item) => Number(item[1]) || 0));

  const option = {
    tooltip: {
      position: "top",
      formatter: (params) => `${params.data[0]}: ${params.data[1]} 条消息`,
    },
    visualMap: {
      min: 0,
      max: maxValue,
      calculable: true,
      orient: "horizontal",
      left: "center",
      bottom: "0%",
      inRange: {
        color: ["#ebedf0", "#c6e48b", "#7bc96f", "#239a3b", "#196127"],
      },
    },
    calendar: {
      top: 20,
      left: 40,
      right: 10,
      cellSize: ["auto", 15],
      range: [startDate, endDate],
      itemStyle: {
        borderWidth: 0.5,
      },
      yearLabel: { show: true },
    },
    series: {
      type: "heatmap",
      coordinateSystem: "calendar",
      data,
    },
  };

  heatmapChart.setOption(option, true);
};

const handleResize = () => {
  if (heatmapChart) {
    heatmapChart.resize();
  }
};

onMounted(() => {
  void renderHeatmap();
});

watch(
  () => [props.heatmapData, props.startDate, props.endDate],
  () => {
    void renderHeatmap();
  },
  { deep: true },
);

onUnmounted(() => {
  resizeObserver = disconnectObserver(resizeObserver);
  heatmapChart = disposeChart(heatmapChart);
});
</script>

<style scoped>
.heatmap-container {
  width: 100%;
}

.heatmap-chart {
  width: 100%;
  height: 180px;
}
</style>
