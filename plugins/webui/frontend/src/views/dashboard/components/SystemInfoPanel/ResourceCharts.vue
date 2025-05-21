<template>
  <div class="charts-area">
    <div class="chart-container">
      <h4>CPU使用率历史</h4>
      <div class="loading-container" v-if="loading">
        <el-icon class="is-loading"><Loading /></el-icon>
      </div>
      <div ref="cpuChartRef" class="chart"></div>
    </div>
    <div class="chart-container">
      <h4>内存使用率历史</h4>
      <div class="loading-container" v-if="loading">
        <el-icon class="is-loading"><Loading /></el-icon>
      </div>
      <div ref="memoryChartRef" class="chart"></div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount, watch } from 'vue'
import { Loading } from '@element-plus/icons-vue'
import * as echarts from 'echarts/core'
import { LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, TitleComponent, LegendComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'

// 注册必要的ECharts组件
echarts.use([LineChart, GridComponent, TooltipComponent, TitleComponent, LegendComponent, CanvasRenderer])

// 工具函数：格式化时间戳为时:分:秒
function formatTimestamp(timestamp) {
  try {
    const date = new Date(Number(timestamp))
    if (isNaN(date.getTime())) {
      return null
    }
    const hours = String(date.getHours()).padStart(2, '0')
    const minutes = String(date.getMinutes()).padStart(2, '0')
    const seconds = String(date.getSeconds()).padStart(2, '0')
    return `${hours}:${minutes}:${seconds}`
  } catch (e) {
    return null
  }
}

// 定义属性
const props = defineProps({
  cpuData: {
    type: Array,
    required: true
  },
  memoryData: {
    type: Array,
    required: true
  },
  timeData: {
    type: Array,
    required: true
  },
  loading: {
    type: Boolean,
    default: false
  }
})

// 图表引用
const cpuChartRef = ref(null)
const memoryChartRef = ref(null)
let cpuChart = null
let memoryChart = null

// 初始化图表
function initCharts() {
  try {
    if (cpuChartRef.value && !cpuChart) {
      cpuChart = echarts.init(cpuChartRef.value)
      cpuChart.setOption({
        title: {
          text: '',
          left: 'center'
        },
        tooltip: {
          trigger: 'axis',
          formatter: function(params) {
            const timeStr = formatTimestamp(params[0].axisValue)
            if (!timeStr) {
              return '时间: 未知<br/>' + params[0].seriesName + ': ' + params[0].value + '%'
            }
            return '时间: ' + timeStr + '<br/>' + params[0].seriesName + ': ' + params[0].value + '%'
          }
        },
        grid: {
          left: '3%',
          right: '4%',
          bottom: '3%',
          top: '8%',
          containLabel: true
        },
        xAxis: {
          type: 'category',
          boundaryGap: false,
          data: props.timeData || [],
          axisLabel: {
            formatter: value => {
              const timeStr = formatTimestamp(value)
              return timeStr || '-'
            }
          }
        },
        yAxis: {
          type: 'value',
          min: 0,
          max: 100,
          axisLabel: {
            formatter: '{value}%'
          }
        },
        series: [{
          name: 'CPU使用率',
          type: 'line',
          smooth: true,
          data: props.cpuData || [],
          areaStyle: {
            opacity: 0.3
          },
          itemStyle: {
            color: '#409EFF'
          }
        }]
      })
    }

    if (memoryChartRef.value && !memoryChart) {
      memoryChart = echarts.init(memoryChartRef.value)
      memoryChart.setOption({
        title: {
          text: '',
          left: 'center'
        },
        tooltip: {
          trigger: 'axis',
          formatter: function(params) {
            const timeStr = formatTimestamp(params[0].axisValue)
            if (!timeStr) {
              return '时间: 未知<br/>' + params[0].seriesName + ': ' + params[0].value + '%'
            }
            return '时间: ' + timeStr + '<br/>' + params[0].seriesName + ': ' + params[0].value + '%'
          }
        },
        grid: {
          left: '3%',
          right: '4%',
          bottom: '3%',
          top: '8%',
          containLabel: true
        },
        xAxis: {
          type: 'category',
          boundaryGap: false,
          data: props.timeData || [],
          axisLabel: {
            formatter: value => {
              const timeStr = formatTimestamp(value)
              return timeStr || '-'
            }
          }
        },
        yAxis: {
          type: 'value',
          min: 0,
          max: 100,
          axisLabel: {
            formatter: '{value}%'
          }
        },
        series: [{
          name: '内存使用率',
          type: 'line',
          smooth: true,
          data: props.memoryData || [],
          areaStyle: {
            opacity: 0.3
          },
          itemStyle: {
            color: '#67C23A'
          }
        }]
      })
    }
    
    // 监听窗口大小变化，重新渲染图表
    window.addEventListener('resize', resizeCharts)
  } catch (error) {
    console.error('初始化图表时出错:', error)
  }
}

// 调整图表尺寸
function resizeCharts() {
  try {
    if (cpuChart) cpuChart.resize()
    if (memoryChart) memoryChart.resize()
  } catch (error) {
    console.error('调整图表尺寸时出错:', error)
  }
}

// 监听数据变化，更新图表
watch(() => [props.cpuData, props.memoryData, props.timeData], ([newCpuData, newMemoryData, newTimeData]) => {
  try {
    if (cpuChart) {
      cpuChart.setOption({
        xAxis: { data: newTimeData || [] },
        series: [{ data: newCpuData || [] }]
      })
    }
    
    if (memoryChart) {
      memoryChart.setOption({
        xAxis: { data: newTimeData || [] },
        series: [{ data: newMemoryData || [] }]
      })
    }
  } catch (error) {
    console.error('更新图表数据时出错:', error)
  }
}, { deep: true })

// 生命周期钩子
onMounted(() => {
  initCharts()
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', resizeCharts)
  if (cpuChart) cpuChart.dispose()
  if (memoryChart) memoryChart.dispose()
})
</script>

<style scoped>
.charts-area {
  display: flex;
  gap: 15px;
  margin-bottom: 15px;
}

.chart-container {
  flex: 1;
  min-height: 200px;
  position: relative;
}

.chart {
  height: 200px;
  width: 100%;
}

h4 {
  margin: 0 0 10px 0;
  color: #606266;
  font-size: 14px;
  text-align: center;
}

.loading-container {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  display: flex;
  justify-content: center;
  align-items: center;
  background: rgba(255, 255, 255, 0.7);
  z-index: 1;
}

/* 响应式设计 */
@media (max-width: 992px) {
  .charts-area {
    flex-direction: column;
  }
}
</style> 