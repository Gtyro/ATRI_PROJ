<template>
  <div class="connection-logs-container">
    <h4>连接日志</h4>
    <el-table :data="logs" style="width: 100%" stripe>
      <el-table-column prop="date" label="日期" min-width="30%"></el-table-column>
      <el-table-column prop="account" label="账号" min-width="30%"></el-table-column>
      <el-table-column prop="duration" label="连接时长" min-width="40%"></el-table-column>
    </el-table>
  </div>
</template>

<script setup>
defineProps({
  logs: {
    type: Array,
    required: true,
    default: () => []
  }
});
</script>

<style scoped>
.connection-logs-container {
  width: 100%;
  overflow-x: hidden;
  box-sizing: border-box;
}

h4 {
  margin-top: 15px;
  margin-bottom: 10px;
  color: #606266;
}

:deep(.el-table th) {
  font-size: 12px;
  padding: 8px 0;
}

:deep(.el-table td) {
  font-size: 10px;
  padding: 6px 0;
}

/* 滚动条样式 */
.connection-logs-container::-webkit-scrollbar {
  width: 6px;
  height: 0; /* 隐藏横向滚动条 */
}

.connection-logs-container::-webkit-scrollbar-track {
  background: #f1f1f1;
  border-radius: 3px;
}

.connection-logs-container::-webkit-scrollbar-thumb {
  background: #c0c4cc;
  border-radius: 3px;
}

.connection-logs-container::-webkit-scrollbar-thumb:hover {
  background: #909399;
}
</style> 