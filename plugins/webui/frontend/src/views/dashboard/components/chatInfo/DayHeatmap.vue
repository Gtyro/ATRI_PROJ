<template>
  <div class="heatmap-container">
    <div ref="heatmapRef" class="heatmap-chart"></div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue';
import * as echarts from 'echarts';

// DOM引用
const heatmapRef = ref(null);
// echarts实例
let heatmapChart = null;

// 模拟的消息数据 - 实际应从API获取
const generateMockData = () => {
  const result = [];
  const startDate = new Date();
  startDate.setMonth(startDate.getMonth() - 3);
  
  for (let i = 0; i < 120; i++) {
    const date = new Date(startDate);
    date.setDate(date.getDate() + i);
    
    // 随机消息数量，周末稍多
    const dayOfWeek = date.getDay();
    const isWeekend = dayOfWeek === 0 || dayOfWeek === 6;
    const value = Math.floor(Math.random() * (isWeekend ? 30 : 20));
    
    result.push([
      echarts.format.formatTime('yyyy-MM-dd', date),
      value
    ]);
  }
  return result;
};

// 获取当前日期和指定月数前的日期
const getDateRange = () => {
  const end = new Date(); // 当前日期
  const start = new Date();
  start.setMonth(end.getMonth() - 3);
  
  return [
    echarts.format.formatTime('yyyy-MM-dd', start),
    echarts.format.formatTime('yyyy-MM-dd', end)
  ];
};

// 初始化热力图
const initHeatmap = () => {
  if (!heatmapRef.value) return;
  
  // 创建图表实例
  heatmapChart = echarts.init(heatmapRef.value);
  
  const data = generateMockData();
  const maxValue = Math.max(...data.map(item => item[1]));
  const [startDate, endDate] = getDateRange();
  
  // 图表配置
  const option = {
    tooltip: {
      position: 'top',
      formatter: (params) => {
        return `${params.data[0]}: ${params.data[1]} 条消息`;
      }
    },
    visualMap: {
      min: 0,
      max: maxValue,
      calculable: true,
      orient: 'horizontal',
      left: 'center',
      bottom: '0%',
      inRange: {
        color: ['#ebedf0', '#c6e48b', '#7bc96f', '#239a3b', '#196127']
      }
    },
    calendar: {
      top: 20,
      left: 40,
      right: 10,
      cellSize: ['auto', 15],
      range: [startDate, endDate],
      itemStyle: {
        borderWidth: 0.5
      },
      yearLabel: { show: true }
    },
    series: {
      type: 'heatmap',
      coordinateSystem: 'calendar',
      data: data
    }
  };
  
  // 应用配置
  heatmapChart.setOption(option);
};

// 处理窗口大小调整
const handleResize = () => {
  heatmapChart && heatmapChart.resize();
};

// 生命周期钩子
onMounted(() => {
  initHeatmap();
  window.addEventListener('resize', handleResize);
});

onUnmounted(() => {
  if (heatmapChart) {
    heatmapChart.dispose();
    heatmapChart = null;
  }
  window.removeEventListener('resize', handleResize);
});
</script>

<style scoped>
.heatmap-container {
  width: 100%;
}

.heatmap-chart {
  width: 100%;
  height: 180px;
}
</style> 