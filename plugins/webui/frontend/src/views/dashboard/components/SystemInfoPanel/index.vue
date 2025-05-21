<template>
  <div class="panel-container">
    <h3>系统运行信息</h3>
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
import { ref, onMounted, onBeforeUnmount } from 'vue'
import ResourceCharts from './ResourceCharts.vue'
import ResourceMetrics from './ResourceMetrics.vue'
import SystemDetails from './SystemDetails.vue'

// 响应式状态
const loading = ref(true)
const currentData = ref({
  cpu: 0,
  memory: 0,
  memory_used: 0,
  memory_total: 0,
  disk: 0,
  disk_used: 0,
  disk_total: 0,
  os_name: '-',
  python_version: '-',
  uptime: 0,
  timestamp: Date.now()
})

// 图表数据
const cpuData = ref([])
const memoryData = ref([])
const timeData = ref([])

// 设置更新间隔（毫秒）
const UPDATE_INTERVAL = 3000
let updateTimer = null

// 更新图表数据
function updateChartData(newData) {
  const timestamp = Date.now()
  timeData.value.push(timestamp)
  cpuData.value.push(newData.cpu)
  memoryData.value.push(newData.memory)
  
  // 限制数据点数量，防止内存占用过高
  if (timeData.value.length > 20) {
    timeData.value.shift()
    cpuData.value.shift()
    memoryData.value.shift()
  }
}

// 从API获取系统信息
async function fetchSystemInfo() {
  try {
    // 修改API路径
    const response = await fetch('/api/dashboard/system-info')
    if (!response.ok) {
      throw new Error(`API返回错误状态码: ${response.status}`)
    }
    const data = await response.json()
    
    currentData.value = data
    updateChartData(data)
    loading.value = false
  } catch (error) {
    console.error('获取系统信息失败:', error)
    // 测试数据，仅在API调用失败时使用
    const mockData = {
      cpu: Math.floor(Math.random() * 100),
      memory: Math.floor(Math.random() * 100),
      memory_used: Math.floor(Math.random() * 8 * 1024 * 1024 * 1024),
      memory_total: 8 * 1024 * 1024 * 1024,
      disk: Math.floor(Math.random() * 100),
      disk_used: Math.floor(Math.random() * 500 * 1024 * 1024 * 1024),
      disk_total: 500 * 1024 * 1024 * 1024,
      os_name: 'Linux',
      python_version: '3.9.10',
      uptime: 3600 * 24 * 2 + 3600 * 5,
      timestamp: Date.now()
    }
    currentData.value = mockData
    updateChartData(mockData)
    loading.value = false
  }
}

// 设置定时获取系统信息
function startDataFetching() {
  fetchSystemInfo() // 立即执行一次
  updateTimer = setInterval(fetchSystemInfo, UPDATE_INTERVAL)
}

// 生命周期钩子
onMounted(() => {
  startDataFetching()
})

onBeforeUnmount(() => {
  clearInterval(updateTimer)
})
</script>

<style scoped>
.panel-container {
  height: 100%;
  padding: 15px;
  background-color: #fff;
  border-radius: 8px;
  box-shadow: 0 2px 12px 0 rgba(0,0,0,0.1);
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
</style> 