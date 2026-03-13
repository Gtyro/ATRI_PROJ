<template>
  <div class="hour-container">
    <div ref="hourChartRef" class="hour-chart"></div>
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
  hours: {
    type: Array,
    default: () => [],
  },
  throughputData: {
    type: Array,
    default: () => [],
  },
});

const hourChartRef = ref(null);
let hourChart = null;
let resizeObserver = null;
let echartsRuntime = null;

const buildFallbackHours = () => {
  const now = new Date();
  const labels = [];
  for (let i = 23; i >= 0; i--) {
    const point = new Date(now);
    point.setHours(now.getHours() - i);
    labels.push(`${String(point.getHours()).padStart(2, "0")}:00`);
  }
  return labels;
};

const normalizeData = () => {
  const hours =
    Array.isArray(props.hours) && props.hours.length > 0
      ? [...props.hours]
      : buildFallbackHours();
  const rawData = Array.isArray(props.throughputData)
    ? props.throughputData
    : [];
  const data = hours.map((_, index) => Number(rawData[index]) || 0);
  return { hours, data };
};

const getHourColor = (label) => {
  const hour = Number.parseInt(String(label).split(":")[0], 10);
  if (hour >= 9 && hour <= 18) {
    return "#7bc96f";
  }
  if (hour >= 6 && hour < 9) {
    return "#c6e48b";
  }
  if (hour > 18 && hour <= 23) {
    return "#239a3b";
  }
  return "#ebedf0";
};

const ensureRuntime = async () => {
  if (!echartsRuntime) {
    echartsRuntime = await loadCoreEchartsRuntime();
  }
  return echartsRuntime;
};

const initHourChart = async () => {
  await nextTick();
  if (!hourChartRef.value || hourChart) return;

  const runtime = await ensureRuntime();
  hourChart = runtime.init(hourChartRef.value);
  resizeObserver = disconnectObserver(resizeObserver);
  resizeObserver = createResizeObserver(hourChartRef.value, handleResize);
};

const renderHourChart = async () => {
  if (!hourChart) {
    await initHourChart();
  }
  if (!hourChart) return;

  const { hours, data } = normalizeData();
  const option = {
    tooltip: {
      trigger: "axis",
      axisPointer: {
        type: "shadow",
      },
      formatter: "{b}: {c} 条消息",
    },
    grid: {
      left: "3%",
      right: "4%",
      bottom: "3%",
      top: "3%",
      containLabel: true,
    },
    xAxis: {
      type: "category",
      data: hours,
      axisLabel: {
        interval: 3,
        rotate: 0,
      },
    },
    yAxis: {
      type: "value",
      splitLine: {
        lineStyle: {
          type: "dashed",
        },
      },
    },
    series: [
      {
        data,
        type: "bar",
        itemStyle: {
          color(params) {
            const label = hours[params.dataIndex] || "00:00";
            return getHourColor(label);
          },
        },
        barWidth: "60%",
      },
    ],
  };

  hourChart.setOption(option, true);
};

const handleResize = () => {
  if (hourChart) {
    hourChart.resize();
  }
};

onMounted(() => {
  void renderHourChart();
});

watch(
  () => [props.hours, props.throughputData],
  () => {
    void renderHourChart();
  },
  { deep: true },
);

onUnmounted(() => {
  resizeObserver = disconnectObserver(resizeObserver);
  hourChart = disposeChart(hourChart);
});
</script>

<style scoped>
.hour-container {
  width: 100%;
}

.hour-chart {
  width: 100%;
  height: 180px;
}
</style>
