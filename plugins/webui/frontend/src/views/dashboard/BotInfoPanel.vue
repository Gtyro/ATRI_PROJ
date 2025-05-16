<template>
  <div class="panel-container">
    <h3>机器人信息</h3>
    
    <!-- 机器人信息展示部分 -->
    <div class="bot-info-section">
      <div class="bot-cards-container">
        <el-card v-for="(bot, index) in botsToDisplay" :key="index" class="bot-card">
          <div class="card-header">
            <el-icon><Monitor /></el-icon>
            <span class="bot-id">{{ bot.id }}</span>
            <el-tag size="small" type="success" class="status-tag">在线</el-tag>
          </div>
          
          <div class="bot-info-grid">
            <!-- 第一行：平台和昵称 -->
            <div class="info-row">
              <!-- 平台信息 -->
              <div class="info-item">
                <div class="info-icon platform-icon">
                  <el-icon><Monitor /></el-icon>
                </div>
                <div class="info-content">
                  <div class="info-label">平台</div>
                  <div class="info-value">{{ bot.platform }}</div>
                </div>
              </div>
              
              <!-- 昵称 -->
              <div class="info-item">
                <div class="info-icon nickname-icon">
                  <el-icon><User /></el-icon>
                </div>
                <div class="info-content">
                  <div class="info-label">昵称</div>
                  <div class="info-value">{{ bot.nickname || '未知' }}</div>
                </div>
              </div>
            </div>
            
            <!-- 第二行：群组数量和好友数量 -->
            <div class="info-row">
              <!-- 群组数量 -->
              <div class="info-item">
                <div class="info-icon group-icon">
                  <el-icon><Service /></el-icon>
                </div>
                <div class="info-content">
                  <div class="info-label">群组数量</div>
                  <div class="info-value">{{ bot.group_count }}</div>
                </div>
              </div>
              
              <!-- 好友数量 -->
              <div class="info-item">
                <div class="info-icon friend-icon">
                  <el-icon><UserFilled /></el-icon>
                </div>
                <div class="info-content">
                  <div class="info-label">好友数量</div>
                  <div class="info-value">{{ bot.friend_count }}</div>
                </div>
              </div>
            </div>
            
            <!-- 第三行：今日插件调用和今日消息数 -->
            <div class="info-row">
              <!-- 今日插件调用 -->
              <div class="info-item">
                <div class="info-icon plugin-icon">
                  <el-icon><Tools /></el-icon>
                </div>
                <div class="info-content">
                  <div class="info-label">今日插件调用</div>
                  <div class="info-value">{{ bot.plugin_calls_today }}</div>
                </div>
              </div>
              
              <!-- 今日消息数 -->
              <div class="info-item">
                <div class="info-icon message-icon">
                  <el-icon><Message /></el-icon>
                </div>
                <div class="info-content">
                  <div class="info-label">今日消息数</div>
                  <div class="info-value">{{ bot.messages_today }}</div>
                </div>
              </div>
            </div>
            
            <!-- 第四行：运行时间 (单独一行) -->
            <div class="info-row single-item">
              <!-- 运行时间 -->
              <div class="info-item">
                <div class="info-icon time-icon">
                  <el-icon><Timer /></el-icon>
                </div>
                <div class="info-content">
                  <div class="info-label">运行时间</div>
                  <div class="info-value">{{ bot.uptime }}</div>
                </div>
              </div>
            </div>
          </div>
        </el-card>
      </div>
    </div>
    
    <!-- 连接日志展示部分 -->
    <div class="connection-logs-section">
      <h4>连接日志</h4>
      <el-table :data="connectionLogs" style="width: 100%" stripe>
        <el-table-column prop="date" label="日期" width="120"></el-table-column>
        <el-table-column prop="account" label="账号" width="120"></el-table-column>
        <el-table-column prop="duration" label="连接时长"></el-table-column>
      </el-table>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue';
import axios from 'axios';
import { Monitor, User, Service, UserFilled, Tools, Message, Timer } from '@element-plus/icons-vue';

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
    const response = await axios.get('/api/dashboard/bot-info');
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
    const response = await axios.get('/api/dashboard/bot-connections');
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
  padding: 15px;
  background-color: #fff;
  border-radius: 8px;
  box-shadow: 0 2px 12px 0 rgba(0,0,0,0.1);
  display: flex;
  flex-direction: column;
}

.panel-container h3 {
  margin-top: 0;
  padding-bottom: 10px;
  border-bottom: 1px solid #eaeaea;
  color: #606266;
}

.panel-container h4 {
  margin-top: 15px;
  margin-bottom: 10px;
  color: #606266;
}

/* 机器人信息部分 */
.bot-info-section {
  flex: 2;
  position: relative;
  margin: 15px 0;
  overflow-y: auto;
  height: calc(100% * 2/3);
  max-height: calc(100% * 2/3);
}

.bot-cards-container {
  display: flex;
  flex-direction: column;
}

.bot-card {
  width: 100%;
  margin-bottom: 16px;
  flex-shrink: 0;
  height: auto; /* 自适应高度 */
}

/* 卡片头部样式 */
.card-header {
  display: flex;
  align-items: center;
  margin-bottom: 12px;
  padding-bottom: 8px;
  border-bottom: 1px dashed #ebeef5;
}

.card-header i {
  font-size: 18px;
  color: #409EFF;
  margin-right: 8px;
}

.bot-id {
  font-size: 15px;
  font-weight: 600;
  color: #303133;
  flex-grow: 1;
}

.status-tag {
  margin-left: 8px;
}

/* 网格布局改为固定行布局 */
.bot-info-grid {
  display: flex;
  flex-direction: column;
  gap: 8px; /* 减少行间距 */
}

.info-row {
  display: flex;
  gap: 8px;
  width: 100%;
}

.info-row .info-item {
  flex: 1;
  min-width: 0; /* 避免内容溢出 */
}

.info-row.single-item {
  justify-content: center;
}

.info-row.single-item .info-item {
  width: 100%;
}

/* 信息项样式 */
.info-item {
  display: flex;
  align-items: flex-start;
  background-color: #f9f9f9;
  padding: 8px; /* 减小内边距 */
  border-radius: 6px;
  transition: all 0.3s;
}

.info-item:hover {
  background-color: #f0f9ff;
  transform: translateY(-2px);
  box-shadow: 0 2px 6px rgba(0, 0, 0, 0.05);
}

.info-icon {
  display: flex;
  justify-content: center;
  align-items: center;
  width: 24px; /* 适当增大一点点 */
  height: 24px;
  border-radius: 50%;
  margin-right: 8px;
}

/* 为不同类型的图标设置不同的颜色 */
.platform-icon {
  background-color: #ecf5ff;
}
.platform-icon i {
  color: #409EFF;
}

.nickname-icon {
  background-color: #f0f9eb;
}
.nickname-icon i {
  color: #67C23A;
}

.group-icon {
  background-color: #fdf6ec;
}
.group-icon i {
  color: #E6A23C;
}

.friend-icon {
  background-color: #fef0f0;
}
.friend-icon i {
  color: #F56C6C;
}

.plugin-icon {
  background-color: #f5f7fa;
}
.plugin-icon i {
  color: #909399;
}

.message-icon {
  background-color: #ecf5ff;
}
.message-icon i {
  color: #409EFF;
}

.time-icon {
  background-color: #f0f9eb;
}
.time-icon i {
  color: #67C23A;
}

.info-icon i {
  font-size: 14px;
}

.info-content {
  flex: 1;
  min-width: 0; /* 确保内容不会溢出 */
  overflow: hidden;
}

.info-label {
  font-size: 12px;
  color: #909399;
  margin-bottom: 2px; /* 减小标签与值之间的间距 */
}

.info-value {
  font-size: 13px;
  font-weight: 500;
  color: #303133;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* 连接日志部分 */
.connection-logs-section {
  flex: 1;
  overflow-y: auto;
  padding-top: 15px;
  border-top: 1px solid #eaeaea;
  height: calc(100% * 1/3);
  max-height: calc(100% * 1/3);
}

/* 滚动条样式 */
.bot-info-section::-webkit-scrollbar,
.connection-logs-section::-webkit-scrollbar {
  width: 6px;
}

.bot-info-section::-webkit-scrollbar-track,
.connection-logs-section::-webkit-scrollbar-track {
  background: #f1f1f1;
  border-radius: 3px;
}

.bot-info-section::-webkit-scrollbar-thumb,
.connection-logs-section::-webkit-scrollbar-thumb {
  background: #c0c4cc;
  border-radius: 3px;
}

.bot-info-section::-webkit-scrollbar-thumb:hover,
.connection-logs-section::-webkit-scrollbar-thumb:hover {
  background: #909399;
}
</style> 