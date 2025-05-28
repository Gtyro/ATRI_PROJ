<template>
  <div class="wordcloud-container" ref="cloudContainer">
    <div v-if="loading" class="loading-overlay">
      <el-icon class="loading-icon"><Loading /></el-icon>
      <p>{{ config.loadingText }}</p>
    </div>
    
    <div v-else-if="error" class="error-overlay">
      <el-icon class="error-icon"><WarningFilled /></el-icon>
      <p>{{ error }}</p>
    </div>
    
    <div v-else-if="words.length === 0" class="empty-overlay">
      <el-icon class="empty-icon"><Document /></el-icon>
      <p>{{ config.emptyText }}</p>
    </div>
    
    <div id="wordcloud" ref="wordcloudRef" class="wordcloud"></div>
    
    <div v-if="config.controlPanel.show" :class="['control-panel', `control-panel-${config.controlPanel.position}`]">
      <div v-if="config.controlPanel.showConversationSelector" class="conversation-selector">
        <span>会话: </span>
        <el-select 
          v-model="selectedConversation"
          placeholder="选择会话"
          @change="onConversationChange"
          filterable
        >
          <el-option 
            v-for="conv in conversations" 
            :key="conv" 
            :label="conv" 
            :value="conv"
          ></el-option>
        </el-select>
      </div>
      
      <el-button v-if="config.controlPanel.showRefreshButton" @click="refreshData" size="small" type="primary" :loading="refreshing">
        刷新数据
      </el-button>
      
      <div v-if="config.controlPanel.showLimitSlider" class="limit-slider">
        <span>词数: {{ limit }}</span>
        <el-slider 
          v-model="limit" 
          :min="10" 
          :max="config.controlPanel.maxLimit" 
          @change="onLimitChange"
        ></el-slider>
      </div>
      
      <div v-if="config.controlPanel.showHistorySelector" class="history-selector">
        <el-date-picker
          v-model="selectedDate"
          type="date"
          placeholder="选择日期"
          format="YYYY-MM-DD"
          value-format="YYYY-MM-DD"
          @change="loadHistoryData"
        ></el-date-picker>
        
        <el-select 
          v-model="selectedHour" 
          placeholder="选择小时" 
          @change="loadHistoryData"
          clearable
        >
          <el-option 
            v-for="h in 24" 
            :key="h-1" 
            :label="`${h-1}:00`" 
            :value="h-1"
          ></el-option>
        </el-select>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, onMounted, onUnmounted, watch, computed, nextTick } from 'vue'
import { ElNotification } from 'element-plus'
import { Loading, WarningFilled, Document } from '@element-plus/icons-vue'
import * as echarts from 'echarts'
import 'echarts-wordcloud'
import defaultConfig from './config'
import { getWordCloudData, getWordCloudHistory, getConversations } from '@/api/wordcloud'

export default {
  name: 'WordCloudComponent',
  components: {
    Loading,
    WarningFilled,
    Document
  },
  props: {
    // 用户自定义配置，会与默认配置合并
    customConfig: {
      type: Object,
      default: () => ({})
    },
    // 初始词数限制
    initialLimit: {
      type: Number,
      default: null
    },
    // 是否自动加载数据
    autoLoad: {
      type: Boolean,
      default: true
    },
    // 是否自动适应容器大小
    autoResize: {
      type: Boolean,
      default: true
    }
  },
  
  setup(props, { emit }) {
    // 合并配置
    const config = computed(() => {
      return {
        ...defaultConfig,
        ...props.customConfig,
        cloudOptions: {
          ...defaultConfig.cloudOptions,
          ...(props.customConfig.cloudOptions || {})
        },
        controlPanel: {
          ...defaultConfig.controlPanel,
          ...(props.customConfig.controlPanel || {})
        }
      }
    })
    
    // 状态变量
    const wordcloudRef = ref(null)
    const cloudContainer = ref(null)
    const chart = ref(null)
    const words = ref([])
    const loading = ref(false)
    const refreshing = ref(false)
    const error = ref(null)
    const limit = ref(props.initialLimit || config.value.controlPanel.defaultLimit)
    const selectedDate = ref('')
    const selectedHour = ref(null)
    const selectedConversation = ref('')
    const conversations = ref([])
    const resizeObserver = ref(null)
    const autoRefreshTimer = ref(null)
    
    // 初始化图表
    const initChart = () => {
      if (!wordcloudRef.value) return
      
      // 初始化ECharts实例
      if (chart.value) {
        chart.value.dispose()
      }
      
      chart.value = echarts.init(wordcloudRef.value)
      
      // 设置响应式
      if (props.autoResize) {
        setupResizeObserver()
      }
      
      // 渲染词云
      renderWordCloud()
    }
    
    // 渲染词云
    const renderWordCloud = () => {
      if (!chart.value || words.value.length === 0) return
      
      // 计算字体大小范围
      const containerWidth = wordcloudRef.value.clientWidth
      const containerHeight = wordcloudRef.value.clientHeight
      const maxFontSize = Math.min(
        config.value.cloudOptions.maxFontSize,
        Math.floor(containerWidth / config.value.cloudOptions.fontSizeRatio)
      )
      
      // 设置词云配置
      const option = {
        series: [{
          type: 'wordCloud',
          shape: 'circle',
          left: 'center',
          top: 'center',
          width: '100%',
          height: '100%',
          right: null,
          bottom: null,
          sizeRange: [config.value.cloudOptions.minFontSize, maxFontSize],
          rotationRange: config.value.cloudOptions.rotationRange,
          rotationStep: config.value.cloudOptions.rotationStep,
          gridSize: 15,
          drawOutOfBound: false,
          textStyle: {
            fontFamily: config.value.cloudOptions.fontFamily,
            fontWeight: 'normal',
            color: function () {
              return config.value.cloudOptions.colors[
                Math.floor(Math.random() * config.value.cloudOptions.colors.length)
              ]
            }
          },
          emphasis: {
            textStyle: {
              fontWeight: 'bold',
              shadowBlur: 10,
              shadowColor: 'rgba(0, 0, 0, 0.3)'
            }
          },
          data: words.value.map(item => ({
            name: item.word,
            value: item.weight
          }))
        }],
        backgroundColor: config.value.cloudOptions.backgroundColor
      }
      
      // 设置动画
      if (config.value.cloudOptions.animation) {
        chart.value.setOption(option, {
          animationDuration: config.value.cloudOptions.animationDuration,
          animationEasing: 'elasticOut'
        })
      } else {
        chart.value.setOption(option)
      }
    }
    
    // 获取会话列表
    const fetchConversations = async () => {
      try {
        const response = await getConversations()
        if (response.data.success) {
          conversations.value = response.data.data || []
          
          // 如果有会话且当前未选择会话，则选择第一个
          if (conversations.value.length > 0 && !selectedConversation.value) {
            selectedConversation.value = conversations.value[0]
            await loadData()
          }
        }
      } catch (err) {
        console.error('获取会话列表失败', err)
      }
    }
    
    // 会话变更处理
    const onConversationChange = (value) => {
      selectedConversation.value = value
      loadData()
    }
    
    // 加载数据
    const loadData = async (forceRefresh = false) => {
      if (!selectedConversation.value) {
        error.value = '请先选择会话'
        return
      }
      
      try {
        loading.value = true
        error.value = null
        
        console.log('开始加载词云数据', { 
          convId: selectedConversation.value,
          limit: limit.value, 
          forceRefresh 
        })
        
        const response = await getWordCloudData(
          selectedConversation.value,
          limit.value, 
          forceRefresh
        )
        console.log('词云数据加载响应', response.data)
        
        if (response.data.success) {
          words.value = response.data.data || []
          console.log(`成功加载词云数据: ${words.value.length}个词`)
          emit('data-loaded', words.value)
        } else {
          error.value = response.data.message || config.value.errorText
          console.error('加载词云数据失败', error.value)
          emit('data-error', error.value)
        }
      } catch (err) {
        error.value = err.message || config.value.errorText
        console.error('加载词云数据出错', err)
        emit('data-error', error.value)
      } finally {
        loading.value = false
        refreshing.value = false
        
        // 渲染词云
        nextTick(() => {
          renderWordCloud()
        })
      }
    }
    
    // 加载历史数据
    const loadHistoryData = async () => {
      if (!selectedConversation.value || !selectedDate.value) return
      
      try {
        loading.value = true
        error.value = null
        
        const response = await getWordCloudHistory(
          selectedConversation.value,
          selectedDate.value, 
          selectedHour.value
        )
        
        if (response.data.success) {
          words.value = response.data.data || []
          emit('history-loaded', {
            convId: selectedConversation.value,
            date: selectedDate.value,
            hour: selectedHour.value,
            data: words.value
          })
        } else {
          error.value = response.data.message || '找不到历史数据'
          emit('history-error', error.value)
        }
      } catch (err) {
        error.value = err.message || config.value.errorText
        emit('history-error', error.value)
      } finally {
        loading.value = false
        
        // 渲染词云
        nextTick(() => {
          renderWordCloud()
        })
      }
    }
    
    // 刷新数据
    const refreshData = async () => {
      refreshing.value = true
      await loadData(true)
      
      ElNotification({
        title: '词云已更新',
        message: '词云数据已成功刷新',
        type: 'success',
        duration: 2000
      })
    }
    
    // 监听词数限制变化
    const onLimitChange = (val) => {
      limit.value = val
      loadData()
    }
    
    // 设置自动刷新
    const setupAutoRefresh = () => {
      if (config.value.autoRefreshInterval > 0) {
        autoRefreshTimer.value = setInterval(() => {
          loadData(true)
        }, config.value.autoRefreshInterval)
      }
    }
    
    // 设置响应式
    const setupResizeObserver = () => {
      if (!cloudContainer.value) return
      
      // 如果已经有观察者，先清除
      if (resizeObserver.value) {
        resizeObserver.value.disconnect()
      }
      
      // 创建新的观察者
      resizeObserver.value = new ResizeObserver(() => {
        if (chart.value) {
          chart.value.resize()
          renderWordCloud()
        }
      })
      
      // 开始观察
      resizeObserver.value.observe(cloudContainer.value)
    }
    
    // 组件挂载
    onMounted(() => {
      // 初始化图表
      nextTick(() => {
        initChart()
        
        // 获取会话列表
        fetchConversations()
        
        // 设置自动刷新
        setupAutoRefresh()
      })
    })
    
    // 组件卸载
    onUnmounted(() => {
      // 清理图表
      if (chart.value) {
        chart.value.dispose()
        chart.value = null
      }
      
      // 清理观察者
      if (resizeObserver.value) {
        resizeObserver.value.disconnect()
        resizeObserver.value = null
      }
      
      // 清理定时器
      if (autoRefreshTimer.value) {
        clearInterval(autoRefreshTimer.value)
        autoRefreshTimer.value = null
      }
    })
    
    // 监听配置变化
    watch(() => props.customConfig, () => {
      nextTick(() => {
        renderWordCloud()
      })
    }, { deep: true })
    
    return {
      wordcloudRef,
      cloudContainer,
      config,
      words,
      loading,
      refreshing,
      error,
      limit,
      selectedDate,
      selectedHour,
      selectedConversation,
      conversations,
      loadData,
      refreshData,
      onLimitChange,
      loadHistoryData,
      onConversationChange,
      fetchConversations
    }
  }
}
</script>

<style scoped>
.wordcloud-container {
  width: 100%;
  height: 100%;
  position: relative;
  min-height: 300px;
}

.wordcloud {
  width: 100%;
  height: 100%;
  min-height: 300px;
}

.loading-overlay,
.error-overlay,
.empty-overlay {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  background-color: rgba(255, 255, 255, 0.8);
  z-index: 10;
}

.loading-icon,
.error-icon,
.empty-icon {
  font-size: 48px;
  margin-bottom: 16px;
}

.error-icon {
  color: #f56c6c;
}

.empty-icon {
  color: #909399;
}

.control-panel {
  position: absolute;
  background-color: rgba(255, 255, 255, 0.8);
  padding: 16px;
  border-radius: 4px;
  box-shadow: 0 2px 12px 0 rgba(0, 0, 0, 0.1);
  z-index: 20;
}

.control-panel-right {
  top: 16px;
  right: 16px;
  width: 200px;
}

.control-panel-left {
  top: 16px;
  left: 16px;
  width: 200px;
}

.control-panel-top {
  top: 16px;
  left: 50%;
  transform: translateX(-50%);
  width: auto;
  display: flex;
  align-items: center;
}

.control-panel-bottom {
  bottom: 16px;
  left: 50%;
  transform: translateX(-50%);
  width: auto;
  display: flex;
  align-items: center;
}

.limit-slider {
  margin-top: 16px;
}

.history-selector {
  margin-top: 16px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.control-panel-top .limit-slider,
.control-panel-bottom .limit-slider,
.control-panel-top .history-selector,
.control-panel-bottom .history-selector {
  margin-top: 0;
  margin-left: 16px;
}

.conversation-selector {
  margin-top: 16px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.control-panel-top .conversation-selector,
.control-panel-bottom .conversation-selector {
  margin-left: 16px;
}

@media (max-width: 768px) {
  .control-panel {
    position: relative;
    top: auto;
    left: auto;
    right: auto;
    bottom: auto;
    transform: none;
    width: 100%;
    margin-top: 16px;
  }
  
  .control-panel-top,
  .control-panel-bottom {
    flex-direction: column;
    align-items: stretch;
  }
  
  .control-panel-top .limit-slider,
  .control-panel-bottom .limit-slider,
  .control-panel-top .history-selector,
  .control-panel-bottom .history-selector,
  .control-panel-top .conversation-selector,
  .control-panel-bottom .conversation-selector {
    margin-left: 0;
    margin-top: 16px;
  }
}
</style> 