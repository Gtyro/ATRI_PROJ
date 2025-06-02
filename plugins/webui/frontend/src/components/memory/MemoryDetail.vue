<template>
  <div class="memory-detail">
    <div v-if="memory" class="memory-card">
      <div class="memory-header">
        <h3 class="memory-title">{{ memory.title }}</h3>
        <div class="memory-meta">
          <el-tag v-if="memory.is_permanent" type="danger" size="small">永久记忆</el-tag>
          <el-tag v-else type="info" size="small">临时记忆</el-tag>
          <span class="memory-date">{{ formatDate(memory.created_at) }}</span>
        </div>
      </div>
      
      <div class="memory-content">
        <p>{{ memory.content }}</p>
      </div>
      
      <div class="memory-footer">
        <div class="memory-stats">
          <div class="stat-item">
            <span class="stat-label">权重:</span>
            <el-progress 
              :percentage="memory.weight * 100" 
              :color="getWeightColor(memory.weight)"
              :stroke-width="10"
              :format="weightFormat"
            />
          </div>
          <div class="stat-item">
            <span class="stat-label">最后访问:</span>
            <span>{{ formatDate(memory.last_accessed) }}</span>
          </div>
        </div>
        
        <div v-if="showAssociatedNodes && memory.associated_nodes && memory.associated_nodes.length > 0" class="associated-nodes">
          <h4>关联认知节点</h4>
          <div class="node-tags">
            <el-tag 
              v-for="node in memory.associated_nodes" 
              :key="node.id"
              :type="node.is_permanent ? 'success' : 'info'"
              class="node-tag"
            >
              {{ node.name }}
            </el-tag>
          </div>
        </div>
      </div>
    </div>
    
    <div v-else class="no-memory-selected">
      <el-empty description="请选择一个记忆查看详情" />
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue';
import { ElTag, ElProgress, ElEmpty } from 'element-plus';

const props = defineProps({
  memory: {
    type: Object,
    default: null
  },
  showAssociatedNodes: {
    type: Boolean,
    default: true
  }
});

// 格式化日期
const formatDate = (timestamp) => {
  if (!timestamp) return '';
  
  const date = new Date(timestamp * 1000);
  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  });
};

// 根据权重计算颜色
const getWeightColor = (weight) => {
  if (weight >= 0.8) return '#67C23A';
  if (weight >= 0.5) return '#E6A23C';
  return '#F56C6C';
};

// 权重格式化函数
const weightFormat = (percentage) => {
  return (percentage / 100).toFixed(2);
};
</script>

<style scoped>
.memory-detail {
  padding: 16px;
  height: 100%;
  overflow-y: auto;
}

.memory-card {
  background-color: #fff;
  border-radius: 8px;
  box-shadow: 0 2px 12px 0 rgba(0, 0, 0, 0.1);
  padding: 20px;
}

.memory-header {
  border-bottom: 1px solid #ebeef5;
  padding-bottom: 16px;
  margin-bottom: 16px;
}

.memory-title {
  margin: 0 0 10px 0;
  font-size: 18px;
  color: #303133;
}

.memory-meta {
  display: flex;
  align-items: center;
  font-size: 13px;
  color: #909399;
}

.memory-date {
  margin-left: 10px;
}

.memory-content {
  margin-bottom: 20px;
  color: #606266;
  line-height: 1.6;
  white-space: pre-wrap;
}

.memory-footer {
  border-top: 1px solid #ebeef5;
  padding-top: 16px;
}

.memory-stats {
  margin-bottom: 16px;
}

.stat-item {
  display: flex;
  align-items: center;
  margin-bottom: 8px;
}

.stat-label {
  width: 80px;
  font-size: 14px;
  color: #606266;
}

.associated-nodes {
  margin-top: 16px;
}

.associated-nodes h4 {
  margin: 0 0 10px 0;
  font-size: 14px;
  color: #606266;
}

.node-tags {
  display: flex;
  flex-wrap: wrap;
}

.node-tag {
  margin: 0 8px 8px 0;
}

.no-memory-selected {
  height: 100%;
  display: flex;
  justify-content: center;
  align-items: center;
}
</style> 