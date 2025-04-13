<template>
  <div class="db-admin">
    <el-card class="box-card">
      <template #header>
        <div class="card-header">
          <h3>数据库管理</h3>
        </div>
      </template>
      
      <el-tabs v-model="activeTab">
        <el-tab-pane label="数据浏览器" name="browser">
          <el-row :gutter="20">
            <el-col :span="5">
              <el-card shadow="never" class="tables-list">
                <template #header>
                  <div class="card-header">
                    <h4>数据库表</h4>
                    <el-button type="primary" size="small" @click="refreshTables">
                      刷新
                    </el-button>
                  </div>
                </template>
                
                <el-input
                  v-model="tableFilter"
                  placeholder="搜索表"
                  clearable
                  style="margin-bottom: 10px"
                />
                
                <el-menu @select="handleTableSelect">
                  <el-menu-item v-for="table in filteredTables" :key="table" :index="table">
                    {{ table }}
                  </el-menu-item>
                </el-menu>
              </el-card>
            </el-col>
            
            <el-col :span="19">
              <el-tabs v-model="dataViewTab" v-if="selectedTable">
                <el-tab-pane label="表数据" name="data">
                  <TableViewer 
                    :tableName="selectedTable" 
                    :onResult="handleQueryResult" 
                  />
                </el-tab-pane>
                <el-tab-pane label="表结构" name="structure">
                  <TableStructure :structureData="tableStructure" />
                </el-tab-pane>
              </el-tabs>
              <el-empty description="请选择一个表" v-else></el-empty>
            </el-col>
          </el-row>
        </el-tab-pane>
        
        <el-tab-pane label="SQL查询" name="query">
          <SqlEditor :onResult="handleQueryResult" />
          <DataTable :data="queryResult" :loading="loading" />
        </el-tab-pane>
        
        <el-tab-pane label="图形化查询" name="builder">
          <QueryBuilder 
            :tables="tables" 
            :onResult="handleQueryResult" 
          />
          <DataTable :data="queryResult" :loading="loading" />
        </el-tab-pane>
        
        <el-tab-pane label="常用查询" name="presets">
          <el-card>
            <template #header>
              <div class="card-header">
                <h4>常用查询</h4>
              </div>
            </template>
            
            <el-collapse>
              <el-collapse-item 
                v-for="(group, groupName) in presetQueries" 
                :key="groupName" 
                :title="group.name"
              >
                <el-descriptions border>
                  <el-descriptions-item v-for="(preset, index) in group.presets" :key="index" :label="preset.name">
                    <p>{{ preset.description }}</p>
                    <el-button type="primary" size="small" @click="runPresetQuery(preset.query)">
                      执行
                    </el-button>
                    <el-button type="info" size="small" @click="showPresetSQL(preset.query)">
                      查看SQL
                    </el-button>
                  </el-descriptions-item>
                </el-descriptions>
              </el-collapse-item>
            </el-collapse>
            
            <DataTable :data="queryResult" :loading="loading" style="margin-top: 20px" />
          </el-card>
        </el-tab-pane>
      </el-tabs>
    </el-card>
    
    <el-dialog title="SQL查询预览" v-model="showSqlPreview" width="60%">
      <pre class="sql-preview">{{ sqlPreview }}</pre>
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="showSqlPreview = false">关闭</el-button>
          <el-button type="primary" @click="copyToClipboard">复制到剪贴板</el-button>
          <el-button type="success" @click="executePreviewSQL">执行查询</el-button>
        </span>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import axios from 'axios'
import SqlEditor from '@/components/SqlEditor.vue'
import DataTable from '@/components/DataTable.vue'
import TableStructure from '@/components/TableStructure.vue'
import TableViewer from '@/components/TableViewer.vue'
import QueryBuilder from '@/components/QueryBuilder.vue'

const activeTab = ref('browser')
const dataViewTab = ref('data')
const loading = ref(false)
const tables = ref([])
const tableFilter = ref('')
const selectedTable = ref('')
const tableStructure = ref(null)
const queryResult = ref({ columns: [], rows: [] })
const showSqlPreview = ref(false)
const sqlPreview = ref('')

// 常用查询预设
const presetQueries = ref({
  system: {
    name: '系统信息',
    presets: [
      {
        name: '数据库统计',
        description: '显示所有表及其行数',
        query: `SELECT name, 
                (SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%') as total_tables,
                (SELECT COUNT(*) FROM sqlite_master WHERE type='index') as total_indexes 
                FROM sqlite_master WHERE type='table' AND name='sqlite_schema'`
      }
    ]
  },
  logs: {
    name: '日志查询',
    presets: [
      {
        name: '最近错误日志',
        description: '显示最近20条错误日志',
        query: `SELECT * FROM logs WHERE level = 'ERROR' ORDER BY timestamp DESC LIMIT 20`
      },
      {
        name: '今日日志汇总',
        description: '按类型统计今日日志',
        query: `SELECT level, COUNT(*) as count FROM logs 
                WHERE date(timestamp) = date('now', 'localtime') 
                GROUP BY level ORDER BY count DESC`
      }
    ]
  },
  users: {
    name: '用户数据',
    presets: [
      {
        name: '新增用户',
        description: '最近30天新增用户',
        query: `SELECT * FROM users WHERE created_at >= date('now', '-30 days') ORDER BY created_at DESC`
      }
    ]
  }
})

// 筛选表
const filteredTables = computed(() => {
  if (!tableFilter.value) return tables.value
  return tables.value.filter(table => 
    table.toLowerCase().includes(tableFilter.value.toLowerCase())
  )
})

// 获取数据库表列表
const fetchTables = () => {
  loading.value = true
  axios.get('/db/tables')
    .then(response => {
      tables.value = response.data.tables
    })
    .catch(error => {
      ElMessage.error('获取表列表失败: ' + error.message)
    })
    .finally(() => {
      loading.value = false
    })
}

// 刷新表列表
const refreshTables = () => {
  fetchTables()
}

// 获取表结构
const fetchTableStructure = (tableName) => {
  loading.value = true
  axios.get(`/db/table/${tableName}`)
    .then(response => {
      tableStructure.value = response.data
    })
    .catch(error => {
      ElMessage.error('获取表结构失败: ' + error.message)
    })
    .finally(() => {
      loading.value = false
    })
}

// 处理表选择
const handleTableSelect = (tableName) => {
  selectedTable.value = tableName
  fetchTableStructure(tableName)
}

// 处理查询结果
const handleQueryResult = (result) => {
  queryResult.value = result
}

// 运行预设查询
const runPresetQuery = (query) => {
  loading.value = true
  
  axios.post('/db/query', { query })
    .then(response => {
      queryResult.value = response.data
      ElMessage.success('查询执行成功')
    })
    .catch(error => {
      ElMessage.error('查询执行失败: ' + (error.response?.data?.detail || error.message))
    })
    .finally(() => {
      loading.value = false
    })
}

// 显示预设SQL
const showPresetSQL = (query) => {
  sqlPreview.value = query
  showSqlPreview.value = true
}

// 执行预览SQL
const executePreviewSQL = () => {
  runPresetQuery(sqlPreview.value)
  showSqlPreview.value = false
}

// 复制SQL到剪贴板
const copyToClipboard = () => {
  navigator.clipboard.writeText(sqlPreview.value)
    .then(() => {
      ElMessage.success('SQL已复制到剪贴板')
    })
    .catch(() => {
      ElMessage.error('复制失败')
    })
}

// 初始化时获取表列表
onMounted(() => {
  fetchTables()
})
</script>

<style scoped>
.db-admin {
  width: 100%;
}

.box-card {
  margin-bottom: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.tables-list {
  max-height: 600px;
  overflow-y: auto;
}

.tables-list .el-menu {
  border-right: none;
}

.sql-preview {
  background-color: #f5f7fa;
  padding: 10px;
  border-radius: 4px;
  white-space: pre-wrap;
  word-break: break-all;
}
</style>