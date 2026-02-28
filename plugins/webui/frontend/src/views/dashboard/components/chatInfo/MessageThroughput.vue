<template>
  <div class="message-throughput">
    <div class="header">
      <h4 class="title">Message Throughput</h4>
      <div class="view-switcher">
        <el-radio-group v-model="currentView" size="small">
          <el-radio-button value="hour">Hour</el-radio-button>
          <el-radio-button value="day">Day</el-radio-button>
        </el-radio-group>
      </div>
    </div>

    <div class="chart-container">
      <hour-chart
        v-if="currentView === 'hour'"
        :hours="hourly.hours"
        :throughput-data="hourly.data"
      />
      <day-heatmap
        v-else
        :heatmap-data="daily.data"
        :start-date="daily.start_date"
        :end-date="daily.end_date"
      />
    </div>
  </div>
</template>

<script setup>
import { onBeforeUnmount, onMounted, ref } from "vue";

import {
  fetchChatThroughputDaily,
  fetchChatThroughputHourly,
  subscribeDashboardStream,
} from "@/api/dashboard";
import HourChart from "./HourChart.vue";
import DayHeatmap from "./DayHeatmap.vue";

const currentView = ref("day");

const hourly = ref({
  hours: [],
  data: [],
});

const daily = ref({
  start_date: "",
  end_date: "",
  data: [],
});

let streamAbortController = null;

const applyHourly = (payload) => {
  const hours = Array.isArray(payload?.hours) ? payload.hours : [];
  const data = Array.isArray(payload?.data) ? payload.data : [];
  hourly.value = {
    hours,
    data: hours.map((_, index) => Number(data[index]) || 0),
  };
};

const applyDaily = (payload) => {
  const rows = Array.isArray(payload?.data) ? payload.data : [];
  daily.value = {
    start_date: String(payload?.start_date || ""),
    end_date: String(payload?.end_date || ""),
    data: rows
      .map((item) => {
        if (!Array.isArray(item) || item.length < 2) {
          return null;
        }
        return [String(item[0] || ""), Number(item[1]) || 0];
      })
      .filter(Boolean),
  };
};

const loadThroughputSnapshot = async () => {
  try {
    const [hourResponse, dayResponse] = await Promise.all([
      fetchChatThroughputHourly(24),
      fetchChatThroughputDaily(120),
    ]);
    applyHourly(hourResponse?.data);
    applyDaily(dayResponse?.data);
  } catch (error) {
    console.error("加载聊天吞吐统计失败:", error);
  }
};

const startThroughputStream = () => {
  if (streamAbortController) {
    streamAbortController.abort();
  }
  streamAbortController = new AbortController();

  void subscribeDashboardStream({
    intervalSeconds: 5,
    signal: streamAbortController.signal,
    onUpdate(payload) {
      const throughput = payload?.throughput;
      if (!throughput || typeof throughput !== "object") {
        return;
      }
      if (throughput.hourly) {
        applyHourly(throughput.hourly);
      }
      if (throughput.daily) {
        applyDaily(throughput.daily);
      }
    },
    onError(error) {
      if (streamAbortController?.signal?.aborted) {
        return;
      }
      console.error("聊天吞吐 SSE 连接异常:", error);
    },
  });
};

onMounted(() => {
  loadThroughputSnapshot();
  startThroughputStream();
});

onBeforeUnmount(() => {
  if (streamAbortController) {
    streamAbortController.abort();
    streamAbortController = null;
  }
});
</script>

<style scoped>
.message-throughput {
  width: 100%;
}

.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 15px;
}

.title {
  margin: 0;
  font-size: 16px;
  font-weight: 500;
  color: #303133;
}

.chart-container {
  width: 100%;
}
</style>
