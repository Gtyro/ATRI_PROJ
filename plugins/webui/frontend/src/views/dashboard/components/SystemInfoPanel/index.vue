<template>
  <div class="panel-container">
    <h3>系统运行信息</h3>
    <el-alert
      v-if="errorMessage"
      :title="errorMessage"
      type="error"
      :closable="false"
      show-icon
      class="panel-error"
    />
    <div class="panel-content">
      <!-- 上半部分：图表区域 -->
      <resource-charts
        :cpu-data="cpuData"
        :memory-data="memoryData"
        :time-data="timeData"
        :loading="loading"
      />

      <!-- 下半部分：当前状态指标 -->
      <resource-metrics :current-data="currentData" />

      <system-details :current-data="currentData" />
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount } from "vue";
import { request } from "@/api";
import ResourceCharts from "./ResourceCharts.vue";
import ResourceMetrics from "./ResourceMetrics.vue";
import SystemDetails from "./SystemDetails.vue";

// 响应式状态
const loading = ref(true);
const errorMessage = ref("");
const currentData = ref({
  cpu: 0,
  memory: 0,
  memory_used: 0,
  memory_total: 0,
  disk: 0,
  disk_used: 0,
  disk_total: 0,
  os_name: "-",
  python_version: "-",
  uptime: 0,
  timestamp: Date.now(),
});

// 图表数据
const cpuData = ref([]);
const memoryData = ref([]);
const timeData = ref([]);

// 设置更新间隔（毫秒）
const UPDATE_INTERVAL = 3000;
let updateTimer = null;

// 更新图表数据
function updateChartData(newData) {
  const timestamp = Date.now();
  timeData.value.push(timestamp);
  cpuData.value.push(newData.cpu);
  memoryData.value.push(newData.memory);

  // 限制数据点数量，防止内存占用过高
  if (timeData.value.length > 20) {
    timeData.value.shift();
    cpuData.value.shift();
    memoryData.value.shift();
  }
}

// 从API获取系统信息
async function fetchSystemInfo() {
  try {
    const response = await request.get("/api/dashboard/system-info");
    const data = response?.data ?? {};

    currentData.value = data;
    updateChartData(data);
    errorMessage.value = "";
    loading.value = false;
  } catch (error) {
    console.error("获取系统信息失败:", error);
    errorMessage.value = "系统运行数据拉取失败，请检查登录状态或后端服务";
    loading.value = false;
  }
}

// 设置定时获取系统信息
function startDataFetching() {
  fetchSystemInfo(); // 立即执行一次
  updateTimer = setInterval(fetchSystemInfo, UPDATE_INTERVAL);
}

// 生命周期钩子
onMounted(() => {
  startDataFetching();
});

onBeforeUnmount(() => {
  clearInterval(updateTimer);
});
</script>

<style scoped>
.panel-container {
  height: 100%;
  padding: 15px;
  background-color: #fff;
  border-radius: 8px;
  box-shadow: 0 2px 12px 0 rgba(0, 0, 0, 0.1);
  overflow-y: auto;
}

.panel-container h3 {
  margin-top: 0;
  padding-bottom: 10px;
  border-bottom: 1px solid #eaeaea;
  color: #606266;
}

.panel-content {
  margin-top: 15px;
}

.panel-error {
  margin-top: 12px;
}
</style>
