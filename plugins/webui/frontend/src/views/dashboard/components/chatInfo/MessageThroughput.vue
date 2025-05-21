<template>
  <div class="message-throughput">
    <div class="header">
      <h4 class="title">Message Throughput</h4>
      <div class="view-switcher">
        <el-radio-group v-model="currentView" size="small">
          <el-radio-button value="hour">Hour</el-radio-button>
          <el-radio-button value="day">Day</el-radio-button>
        </el-radio-group>
      </div>
    </div>
    
    <div class="chart-container">
      <hour-chart v-if="currentView === 'hour'" />
      <day-heatmap v-else />
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue';
import HourChart from './HourChart.vue';
import DayHeatmap from './DayHeatmap.vue';

// 当前视图模式："hour" 或 "day"
const currentView = ref('day');
</script>

<style scoped>
.message-throughput {
  width: 100%;
}

.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 15px;
}

.title {
  margin: 0;
  font-size: 16px;
  font-weight: 500;
  color: #303133;
}

.chart-container {
  width: 100%;
}
</style> 