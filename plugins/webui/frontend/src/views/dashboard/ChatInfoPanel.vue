<template>
  <div class="panel-container">
    <h3>聊天信息</h3>
    <div class="panel-content">
      <!-- 消息吞吐量组件 -->
      <message-throughput />
      
      <!-- 未来可添加更多组件 -->
    </div>
  </div>
</template>

<script setup>
import { MessageThroughput } from './components/chatInfo';
</script>

<style scoped>
.panel-container {
  height: 100%;
  padding: 15px;
  background-color: #fff;
  border-radius: 8px;
  box-shadow: 0 2px 12px 0 rgba(0,0,0,0.1);
}

.panel-container h3 {
  margin-top: 0;
  padding-bottom: 10px;
  border-bottom: 1px solid #eaeaea;
  color: #606266;
}

.panel-content {
  margin-top: 15px;
  width: 100%;
}
</style> 