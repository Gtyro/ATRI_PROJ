<template>
  <div class="system-info">
    <el-descriptions title="系统信息" :column="2" border>
      <el-descriptions-item label="系统">{{ currentData.os_name }}</el-descriptions-item>
      <el-descriptions-item label="Python版本">{{ currentData.python_version }}</el-descriptions-item>
      <el-descriptions-item label="运行时长">{{ formatUptime(currentData.uptime) }}</el-descriptions-item>
      <el-descriptions-item label="更新时间">{{ formatTime(currentData.timestamp) }}</el-descriptions-item>
    </el-descriptions>
  </div>
</template>

<script setup>
// 定义属性
const props = defineProps({
  currentData: {
    type: Object,
    required: true
  }
})

function formatTime(timestamp) {
  return new Date(timestamp).toLocaleTimeString()
}

function formatUptime(seconds) {
  const days = Math.floor(seconds / 86400)
  const hours = Math.floor((seconds % 86400) / 3600)
  const minutes = Math.floor((seconds % 3600) / 60)
  
  let result = ''
  if (days > 0) result += `${days}天 `
  if (hours > 0 || days > 0) result += `${hours}小时 `
  result += `${minutes}分钟`
  
  return result
}
</script>

<style scoped>
.system-info {
  margin-top: 15px;
}
</style> 