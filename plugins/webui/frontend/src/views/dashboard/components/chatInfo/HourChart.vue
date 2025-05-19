<template>
  <div class="hour-container">
    <div ref="hourChartRef" class="hour-chart"></div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue';
import * as echarts from 'echarts';

// DOM引用
const hourChartRef = ref(null);
// echarts实例
let hourChart = null;

// 生成过去24小时的模拟数据
const generateHourlyData = () => {
  const result = [];
  const hours = [];
  const now = new Date();
  
  for (let i = 23; i >= 0; i--) {
    const time = new Date(now);
    time.setHours(now.getHours() - i);
    
    // 格式化小时标签 "HH:00"
    const hourStr = time.getHours().toString().padStart(2, '0') + ':00';
    hours.push(hourStr);
    
    // 生成随机消息数，工作时间段消息较多
    const hour = time.getHours();
    const isWorkHour = hour >= 9 && hour <= 18;
    const value = Math.floor(Math.random() * (isWorkHour ? 25 : 10));
    
    result.push(value);
  }
  
  return { hours, data: result };
};

// 初始化小时统计图
const initHourChart = () => {
  if (!hourChartRef.value) return;
  
  // 创建图表实例
  hourChart = echarts.init(hourChartRef.value);
  
  const { hours, data } = generateHourlyData();
  
  // 图表配置
  const option = {
    tooltip: {
      trigger: 'axis',
      axisPointer: {
        type: 'shadow'
      },
      formatter: '{b}: {c} 条消息'
    },
    grid: {
      left: '3%',
      right: '4%',
      bottom: '3%',
      top: '3%',
      containLabel: true
    },
    xAxis: {
      type: 'category',
      data: hours,
      axisLabel: {
        interval: 3,  // 每隔3个显示一个标签
        rotate: 0
      }
    },
    yAxis: {
      type: 'value',
      splitLine: {
        lineStyle: {
          type: 'dashed'
        }
      }
    },
    series: [{
      data: data,
      type: 'bar',
      itemStyle: {
        color: function(params) {
          // 为不同时段设置不同颜色
          const idx = params.dataIndex;
          const hour = parseInt(hours[idx].split(':')[0]);
          
          if (hour >= 9 && hour <= 18) {
            return '#7bc96f';  // 工作时间为绿色
          } else if (hour >= 6 && hour < 9) {
            return '#c6e48b';  // 早晨为浅绿色
          } else if (hour > 18 && hour <= 23) {
            return '#239a3b';  // 晚上为深绿色
          } else {
            return '#ebedf0';  // 深夜为浅灰色
          }
        }
      },
      barWidth: '60%'
    }]
  };
  
  // 应用配置
  hourChart.setOption(option);
};

// 处理窗口大小调整
const handleResize = () => {
  hourChart && hourChart.resize();
};

// 生命周期钩子
onMounted(() => {
  initHourChart();
  window.addEventListener('resize', handleResize);
});

onUnmounted(() => {
  if (hourChart) {
    hourChart.dispose();
    hourChart = null;
  }
  window.removeEventListener('resize', handleResize);
});
</script>

<style scoped>
.hour-container {
  width: 100%;
}

.hour-chart {
  width: 100%;
  height: 180px;
}
</style> 