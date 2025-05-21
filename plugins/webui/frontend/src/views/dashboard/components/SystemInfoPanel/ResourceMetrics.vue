<template>
  <div class="current-metrics">
    <el-card class="metric-card" shadow="hover">
      <template #header>
        <div class="metric-header">
          <el-icon><Monitor /></el-icon>
          <span>CPU当前使用率</span>
        </div>
      </template>
      <div class="metric-value">
        <span class="percentage">{{ currentData.cpu }}%</span>
        <el-progress :percentage="currentData.cpu" :color="getProgressColor(currentData.cpu)" />
      </div>
    </el-card>
    
    <el-card class="metric-card" shadow="hover">
      <template #header>
        <div class="metric-header">
          <el-icon><Cpu /></el-icon>
          <span>内存当前使用率</span>
        </div>
      </template>
      <div class="metric-value">
        <span class="percentage">{{ currentData.memory }}%</span>
        <el-progress :percentage="currentData.memory" :color="getProgressColor(currentData.memory)" />
        <div class="memory-details">
          已用: {{ formatBytes(currentData.memory_used) }} / 总计: {{ formatBytes(currentData.memory_total) }}
        </div>
      </div>
    </el-card>
    
    <el-card class="metric-card" shadow="hover">
      <template #header>
        <div class="metric-header">
          <el-icon><FolderOpened /></el-icon>
          <span>磁盘使用率</span>
        </div>
      </template>
      <div class="metric-value">
        <span class="percentage">{{ currentData.disk }}%</span>
        <el-progress :percentage="currentData.disk" :color="getProgressColor(currentData.disk)" />
        <div class="memory-details">
          已用: {{ formatBytes(currentData.disk_used) }} / 总计: {{ formatBytes(currentData.disk_total) }}
        </div>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { Monitor, Cpu, FolderOpened } from '@element-plus/icons-vue'

// 定义属性
const props = defineProps({
  currentData: {
    type: Object,
    required: true
  }
})

// 工具函数
function getProgressColor(value) {
  if (value < 50) return '#67C23A'
  if (value < 80) return '#E6A23C'
  return '#F56C6C'
}

function formatBytes(bytes) {
  if (!bytes || bytes === 0) return '0 B'
  
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB']
  const i = Math.floor(Math.log(bytes) / Math.log(1024))
  return (bytes / Math.pow(1024, i)).toFixed(2) + ' ' + sizes[i]
}
</script>

<style scoped>
.current-metrics {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 15px;
  margin-bottom: 15px;
}

.metric-card {
  margin-bottom: 0;
}

.metric-header {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  font-weight: bold;
}

.metric-value {
  text-align: center;
  padding: 10px 0;
}

.percentage {
  font-size: 24px;
  font-weight: bold;
  margin-bottom: 10px;
  display: block;
}

.memory-details {
  margin-top: 8px;
  font-size: 12px;
  color: #909399;
}

/* 响应式设计 */
@media (max-width: 992px) {
  .current-metrics {
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (max-width: 768px) {
  .current-metrics {
    grid-template-columns: 1fr;
  }
}
</style> 