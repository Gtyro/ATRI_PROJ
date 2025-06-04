<template>
  <div class="panel-container">
    <h3>机器人信息</h3>

    <!-- 机器人信息展示部分 -->
    <div class="bot-info-section">
      <div class="bot-cards-container">
        <BotInfoCard v-for="(bot, index) in botsToDisplay" :key="index" :bot="bot" />
      </div>
    </div>

    <!-- 连接日志展示部分 -->
    <div class="connection-logs-section">
      <ConnectionLogs :logs="connectionLogs" />
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue';
import { request } from '@/api';
import BotInfoCard from './components/botInfo/BotInfoCard.vue';
import ConnectionLogs from './components/botInfo/ConnectionLogs.vue';

// 机器人数据
const bots = ref([]);
const connectionLogs = ref([]);
const loading = ref(true);
const error = ref(null);

// 用于显示的机器人列表
const botsToDisplay = computed(() => {
  if (bots.value.length === 0) {
    // 无数据时显示占位
    return [{
      id: '加载中',
      platform: '未知',
      nickname: '未知',
      group_count: 0,
      friend_count: 0,
      plugin_calls_today: 0,
      messages_today: 0,
      uptime: '0小时0分钟'
    }];
  }

  if (bots.value.length === 1) {
    // 只有一个机器人时，重复三次展示
    const bot = bots.value[0];
    return [bot, bot, bot];
  }

  return bots.value;
});

// 加载机器人信息
const loadBotInfo = async () => {
  try {
    const response = await request.get('/api/dashboard/bot-info');
    bots.value = response.data;
    loading.value = false;
  } catch (err) {
    console.error('获取机器人信息失败:', err);
    error.value = '获取机器人信息失败';
    loading.value = false;
  }
};

// 加载连接日志
const loadConnectionLogs = async () => {
  try {
    const response = await request.get('/api/dashboard/bot-connections');
    connectionLogs.value = response.data;
  } catch (err) {
    console.error('获取连接日志失败:', err);
  }
};

// 生命周期钩子
onMounted(() => {
  loadBotInfo();
  loadConnectionLogs();
});
</script>

<style scoped>
.panel-container {
  height: 100%;
  width: 300px;
  padding: 5px;
  background-color: #fff;
  border-radius: 8px;
  box-shadow: 0 2px 12px 0 rgba(0,0,0,0.1);
  display: flex;
  flex-direction: column;
  box-sizing: border-box;
}

.panel-container h3 {
  margin-top: 0;
  padding-bottom: 10px;
  border-bottom: 1px solid #eaeaea;
  color: #606266;
}

/* 机器人信息部分 */
.bot-info-section {
  flex: 2;
  position: relative;
  margin: 15px 0;
  overflow-y: auto;
  overflow-x: hidden;
  height: calc(100% * 2/3);
  max-height: calc(100% * 2/3);
  width: 100%;
  box-sizing: border-box;
}

.bot-cards-container {
  display: flex;
  flex-direction: column;
  width: 100%;
  box-sizing: border-box;
}

/* 连接日志部分 */
.connection-logs-section {
  flex: 1;
  overflow-y: auto;
  overflow-x: hidden;
  padding-top: 15px;
  border-top: 1px solid #eaeaea;
  height: calc(100% * 1/3);
  max-height: calc(100% * 1/3);
  width: 100%;
  box-sizing: border-box;
}

/* 滚动条样式 */
.bot-info-section::-webkit-scrollbar {
  width: 6px;
  height: 0; /* 隐藏横向滚动条 */
}

.bot-info-section::-webkit-scrollbar-track {
  background: #f1f1f1;
  border-radius: 3px;
}

.bot-info-section::-webkit-scrollbar-thumb {
  background: #c0c4cc;
  border-radius: 3px;
}

.bot-info-section::-webkit-scrollbar-thumb:hover {
  background: #909399;
}

/* 为连接日志部分添加滚动条样式 */
.connection-logs-section::-webkit-scrollbar {
  width: 6px;
  height: 0; /* 隐藏横向滚动条 */
}

.connection-logs-section::-webkit-scrollbar-track {
  background: #f1f1f1;
  border-radius: 3px;
}

.connection-logs-section::-webkit-scrollbar-thumb {
  background: #c0c4cc;
  border-radius: 3px;
}

.connection-logs-section::-webkit-scrollbar-thumb:hover {
  background: #909399;
}
</style> 