<template>
  <div class="wordcloud-page">
    <div class="page-header">
      <h1>聊天词云</h1>
      <p class="description">展示聊天中出现频率最高的词汇</p>
    </div>
    
    <el-card class="wordcloud-card">
      <template #header>
        <div class="card-header">
          <span>词频统计</span>
          <div class="header-actions">
            <el-select 
              v-model="selectedConversation" 
              placeholder="选择会话" 
              filterable
              @change="onConversationChange"
              class="conversation-select"
            >
              <el-option 
                v-for="conv in conversations" 
                :key="conv" 
                :label="conv" 
                :value="conv"
              ></el-option>
            </el-select>
            
            <el-tooltip content="生成新词云数据" placement="top">
              <el-button type="primary" size="small" @click="generateNewData" :loading="generating">
                生成新数据
              </el-button>
            </el-tooltip>
            <el-tooltip content="配置" placement="top">
              <el-button type="info" size="small" @click="showConfig = true">
                <el-icon><Setting /></el-icon>
              </el-button>
            </el-tooltip>
          </div>
        </div>
      </template>
      
      <div class="wordcloud-wrapper" :style="{height: `${cloudHeight}px`}">
        <WordCloudComponent 
          ref="wordCloudRef"
          :custom-config="customConfig"
          :initial-limit="wordLimit"
          @data-loaded="onDataLoaded"
          @data-error="onDataError"
        />
      </div>
    </el-card>
    
    <el-dialog
      v-model="showConfig"
      title="词云配置"
      width="500px"
    >
      <el-form label-width="120px">
        <el-form-item label="时间范围">
          <el-select v-model="configForm.hours" placeholder="选择时间范围">
            <el-option label="最近12小时" :value="12" />
            <el-option label="最近24小时" :value="24" />
            <el-option label="最近48小时" :value="48" />
            <el-option label="最近7天" :value="168" />
          </el-select>
        </el-form-item>
        
        <el-form-item label="词数限制">
          <el-slider v-model="configForm.wordLimit" :min="20" :max="200" :step="10" show-input />
        </el-form-item>
        
        <el-form-item label="面板位置">
          <el-select v-model="configForm.panelPosition" placeholder="选择控制面板位置">
            <el-option label="右侧" value="right" />
            <el-option label="左侧" value="left" />
            <el-option label="顶部" value="top" />
            <el-option label="底部" value="bottom" />
          </el-select>
        </el-form-item>
        
        <el-form-item label="显示控制面板">
          <el-switch v-model="configForm.showPanel" />
        </el-form-item>
      </el-form>
      
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="showConfig = false">取消</el-button>
          <el-button type="primary" @click="applyConfig">应用</el-button>
        </span>
      </template>
    </el-dialog>
  </div>
</template>

<script>
import { ref, reactive, computed, onMounted, nextTick } from 'vue'
import { ElNotification, ElMessageBox } from 'element-plus'
import { Setting } from '@element-plus/icons-vue'
import WordCloudComponent from './WordCloudComponent.vue'
import { generateWordCloud, getConversations } from '@/api/wordcloud'

export default {
  name: 'WordCloudPage',
  components: {
    WordCloudComponent,
    Setting
  },
  setup() {
    // 词云组件引用
    const wordCloudRef = ref(null)
    
    // 状态变量
    const cloudHeight = ref(500)
    const wordLimit = ref(80)
    const generating = ref(false)
    const showConfig = ref(false)
    const selectedConversation = ref('') // 当前选择的会话
    const conversations = ref([]) // 所有会话列表
    
    // 配置表单
    const configForm = reactive({
      hours: 24,
      wordLimit: 80,
      panelPosition: 'right',
      showPanel: true
    })
    
    // 自定义配置
    const customConfig = ref({
      controlPanel: {
        position: 'right',
        show: true
      }
    })
    
    // 应用配置
    const applyConfig = () => {
      wordLimit.value = configForm.wordLimit
      
      customConfig.value = {
        controlPanel: {
          position: configForm.panelPosition,
          show: configForm.showPanel
        }
      }
      
      showConfig.value = false
      
      // 通知词云组件更新
      nextTick(() => {
        if (wordCloudRef.value) {
          wordCloudRef.value.loadData()
        }
      })
    }
    
    // 获取会话列表
    const fetchConversations = async () => {
      try {
        const response = await getConversations()
        if (response.data.success) {
          conversations.value = response.data.data || []
          // 如果有会话且未选择会话，自动选择第一个
          if (conversations.value.length > 0 && !selectedConversation.value) {
            selectedConversation.value = conversations.value[0]
            if (wordCloudRef.value) {
              wordCloudRef.value.selectedConversation = selectedConversation.value
              wordCloudRef.value.loadData()
            }
          }
        }
      } catch (err) {
        console.error('获取会话列表失败', err)
        ElNotification({
          title: '错误',
          message: '获取会话列表失败',
          type: 'error'
        })
      }
    }
    
    // 会话切换
    const onConversationChange = (convId) => {
      selectedConversation.value = convId
      if (wordCloudRef.value) {
        wordCloudRef.value.selectedConversation = convId
        wordCloudRef.value.loadData()
      }
    }
    
    // 生成新词云数据
    const generateNewData = async () => {
      if (!selectedConversation.value) {
        ElNotification({
          title: '提示',
          message: '请先选择会话',
          type: 'warning'
        })
        return
      }
      
      try {
        generating.value = true
        
        await ElMessageBox.confirm(
          '生成新的词云数据可能需要一些时间，确定要继续吗？',
          '提示',
          {
            confirmButtonText: '确定',
            cancelButtonText: '取消',
            type: 'warning'
          }
        )
        
        const response = await generateWordCloud(
          selectedConversation.value,
          configForm.wordLimit, 
          configForm.hours
        )
        
        if (response.data.success) {
          ElNotification({
            title: '成功',
            message: '词云数据生成成功',
            type: 'success'
          })
          
          // 刷新词云
          if (wordCloudRef.value) {
            wordCloudRef.value.loadData(true)
          }
        } else {
          ElNotification({
            title: '错误',
            message: response.data.message || '词云数据生成失败',
            type: 'error'
          })
        }
      } catch (err) {
        if (err !== 'cancel') {
          ElNotification({
            title: '错误',
            message: err.message || '词云数据生成失败',
            type: 'error'
          })
        }
      } finally {
        generating.value = false
      }
    }
    
    // 数据加载回调
    const onDataLoaded = (data) => {
      console.log('词云数据加载成功', data.length)
    }
    
    // 数据加载错误回调
    const onDataError = (error) => {
      console.error('词云数据加载失败', error)
    }
    
    // 调整词云高度
    const adjustHeight = () => {
      const windowHeight = window.innerHeight
      cloudHeight.value = Math.max(400, windowHeight - 250) // 减去页面其他部分的高度
    }
    
    // 组件挂载
    onMounted(() => {
      adjustHeight()
      window.addEventListener('resize', adjustHeight)
      fetchConversations()
    })
    
    return {
      wordCloudRef,
      cloudHeight,
      wordLimit,
      generating,
      showConfig,
      configForm,
      customConfig,
      selectedConversation,
      conversations,
      generateNewData,
      applyConfig,
      onDataLoaded,
      onDataError,
      onConversationChange,
      fetchConversations
    }
  }
}
</script>

<style scoped>
.wordcloud-page {
  padding: 20px;
}

.page-header {
  margin-bottom: 20px;
}

.page-header h1 {
  margin: 0;
  font-size: 24px;
  color: #303133;
}

.description {
  color: #909399;
  margin-top: 8px;
}

.wordcloud-card {
  margin-bottom: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.header-actions {
  display: flex;
  gap: 10px;
  align-items: center;
}

.conversation-select {
  min-width: 180px;
}

.wordcloud-wrapper {
  width: 100%;
  position: relative;
  transition: height 0.3s;
}
</style> 