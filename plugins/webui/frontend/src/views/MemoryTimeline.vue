<template>
  <div class="memory-timeline-page">
    <h1 class="page-title">记忆脉络</h1>
    
    <el-row :gutter="20">
      <el-col :span="24">
        <MemoryFilter 
          :conversations="memoryStore.conversations"
          :default-conv-id="memoryStore.currentConvId"
          :time-range="memoryStore.timeRange"
          @update:conv-id="updateConvId"
          @update:time-range="updateTimeRange"
          @filter="loadMemoryData"
        />
      </el-col>
    </el-row>
    
    <el-row :gutter="20" class="main-content">
      <el-col :md="16" :sm="24" class="timeline-container">
        <div class="timeline-card">
          <div class="card-header">
            <h2>时间轴可视化</h2>
            <el-tag type="info">共 {{ memoryStore.timelineData.length }} 条记忆</el-tag>
          </div>
          
          <div class="timeline-view">
            <MemoryTimeline3D
              :memories="memoryStore.timelineData"
              :selected-memory="memoryStore.selectedMemory"
              :loading="memoryStore.isLoading"
              @select-memory="selectMemory"
            />
          </div>
        </div>
      </el-col>
      
      <el-col :md="8" :sm="24" class="detail-container">
        <div class="detail-card">
          <div class="card-header">
            <h2>记忆详情</h2>
          </div>
          
          <MemoryDetail :memory="memoryStore.selectedMemory" />
        </div>
      </el-col>
    </el-row>
    
    <el-row v-if="memoryStore.error" class="error-message">
      <el-col :span="24">
        <el-alert
          :title="memoryStore.error"
          type="error"
          :closable="false"
          show-icon
        />
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { onMounted, onBeforeUnmount } from 'vue';
import { useMemoryStore } from '@/stores/memory';
import MemoryFilter from '@/components/memory/MemoryFilter.vue';
import MemoryTimeline3D from '@/components/memory/MemoryTimeline3D.vue';
import MemoryDetail from '@/components/memory/MemoryDetail.vue';

// 初始化存储
const memoryStore = useMemoryStore();

// 加载记忆数据
const loadMemoryData = async () => {
  try {
    await memoryStore.fetchMemoryTimeline();
  } catch (error) {
    console.error('加载记忆数据失败', error);
  }
};

// 选择记忆
const selectMemory = async (memory) => {
  try {
    await memoryStore.fetchMemoryDetail(memory.id);
  } catch (error) {
    console.error('加载记忆详情失败', error);
  }
};

// 更新会话ID
const updateConvId = (convId) => {
  memoryStore.setCurrentConvId(convId);
};

// 更新时间范围
const updateTimeRange = (timeRange) => {
  memoryStore.setTimeRange(timeRange.start, timeRange.end);
};

// 组件挂载时加载数据
onMounted(async () => {
  // 加载会话列表
  try {
    await memoryStore.fetchConversations();
  } catch (error) {
    console.error('加载会话列表失败', error);
  }
  
  // 加载记忆数据
  loadMemoryData();
});

// 组件卸载时重置状态
onBeforeUnmount(() => {
  memoryStore.resetState();
});
</script>

<style scoped>
.memory-timeline-page {
  padding: 20px;
  height: 100%;
  display: flex;
  flex-direction: column;
}

.page-title {
  margin-top: 0;
  margin-bottom: 20px;
  color: #303133;
}

.main-content {
  flex: 1;
  margin-bottom: 20px;
  min-height: 600px;
}

.timeline-container, .detail-container {
  height: 100%;
  min-height: 600px;
}

.timeline-card, .detail-card {
  height: 100%;
  background-color: #fff;
  border-radius: 8px;
  box-shadow: 0 2px 12px 0 rgba(0, 0, 0, 0.1);
  display: flex;
  flex-direction: column;
}

.card-header {
  padding: 16px;
  border-bottom: 1px solid #ebeef5;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.card-header h2 {
  margin: 0;
  font-size: 16px;
  font-weight: 500;
  color: #303133;
}

.timeline-view {
  flex: 1;
  height: 100%;
  min-height: 500px;
  position: relative;
}

.error-message {
  margin-top: 20px;
}

@media (max-width: 768px) {
  .timeline-container, .detail-container {
    margin-bottom: 20px;
  }
}
</style> 