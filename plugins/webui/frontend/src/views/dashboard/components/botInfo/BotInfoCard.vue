<template>
  <el-card class="bot-card">
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
</template>

<script setup>
import { Monitor, User, Service, UserFilled, Tools, Message, Timer } from '@element-plus/icons-vue';

defineProps({
  bot: {
    type: Object,
    required: true
  }
});
</script>

<style scoped>
.bot-card {
  width: 100%;
  margin-bottom: 16px;
  flex-shrink: 0;
  height: auto; /* 自适应高度 */
  box-sizing: border-box; /* 添加盒模型设置 */
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
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.status-tag {
  margin-left: 8px;
  flex-shrink: 0;
}

/* 网格布局改为固定行布局 */
.bot-info-grid {
  display: flex;
  flex-direction: column;
  gap: 8px; /* 减少行间距 */
  width: 100%;
  box-sizing: border-box;
}

.info-row {
  display: flex;
  gap: 8px;
  width: 100%;
  box-sizing: border-box;
}

.info-row .info-item {
  flex: 1;
  min-width: 0; /* 避免内容溢出 */
  box-sizing: border-box;
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
  box-sizing: border-box;
  width: 100%;
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
</style> 