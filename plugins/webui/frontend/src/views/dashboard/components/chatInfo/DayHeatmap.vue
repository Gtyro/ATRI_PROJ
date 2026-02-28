<template>
  <div class="heatmap-container">
    <div ref="heatmapRef" class="heatmap-chart"></div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, watch } from "vue";
import * as echarts from "echarts";

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

const buildFallbackRange = () => {
  const end = new Date();
  const start = new Date();
  start.setMonth(end.getMonth() - 3);
  return [
    echarts.format.formatTime("yyyy-MM-dd", start),
    echarts.format.formatTime("yyyy-MM-dd", end),
  ];
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

const initHeatmap = () => {
  if (!heatmapRef.value) return;
  heatmapChart = echarts.init(heatmapRef.value);
};

const renderHeatmap = () => {
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
  initHeatmap();
  renderHeatmap();
  window.addEventListener("resize", handleResize);
});

watch(
  () => [props.heatmapData, props.startDate, props.endDate],
  () => {
    renderHeatmap();
  },
  { deep: true },
);

onUnmounted(() => {
  if (heatmapChart) {
    heatmapChart.dispose();
    heatmapChart = null;
  }
  window.removeEventListener("resize", handleResize);
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
