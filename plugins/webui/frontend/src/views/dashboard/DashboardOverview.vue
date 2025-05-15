<template>
  <div class="dashboard-container">
    <div class="dashboard-column left-column">
      <BotInfoPanel />
    </div>
    <div class="dashboard-column center-column">
      <SystemInfoPanel />
    </div>
    <div class="dashboard-column right-column">
      <ChatInfoPanel />
    </div>
  </div>
</template>

<script setup>
import BotInfoPanel from './BotInfoPanel.vue'
import SystemInfoPanel from './SystemInfoPanel.vue'
import ChatInfoPanel from './ChatInfoPanel.vue'
</script>

<style scoped>
.dashboard-container {
  display: flex;
  height: calc(100vh - 120px);
  gap: 20px;
  padding: 20px;
}

.dashboard-column {
  min-width: 0; /* 防止内容溢出 */
  display: flex;
  flex-direction: column;
}

.left-column {
  flex: 0 0 300px; /* 不缩放，不增长，保持300px宽度 */
}

.right-column {
  flex: 0 0 400px; /* 不缩放，不增长，保持300px宽度 */
}

.center-column {
  flex: 1; /* 占据所有剩余空间 */
}

/* 小屏幕适配 - 在非常小的屏幕上转为垂直布局 */
@media (max-width: 768px) {
  .dashboard-container {
    flex-direction: column;
    height: auto;
  }
  
  .dashboard-column {
    margin-bottom: 20px;
    width: 100%; /* 在小屏幕上占满宽度 */
    flex: none;
  }
}
</style> 