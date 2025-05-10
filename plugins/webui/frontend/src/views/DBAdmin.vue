<template>
  <div class="db-admin">
    <el-card class="box-card">
      <template #header>
        <div class="card-header">
          <h3>数据库管理</h3>
          <el-select 
            v-model="dataSource" 
            placeholder="选择数据源" 
            style="width: 150px"
            @change="handleDataSourceChange"
          >
            <el-option label="SQL/ORM" value="sql"></el-option>
            <el-option label="Neo4j/OGM" value="neo4j"></el-option>
          </el-select>
        </div>
      </template>

      <el-tabs v-model="activeTab">
        <el-tab-pane label="数据管理" name="manager">
          <TableManager
            :tables="currentTables"
            :onResult="handleQueryResult"
          />
        </el-tab-pane>

        <el-tab-pane label="数据查询" name="query">
          <div v-if="dataSource === 'sql'">
            <SqlEditor :onResult="handleQueryResult" />
          </div>
          <div v-else-if="dataSource === 'neo4j'">
            <CypherEditor :onResult="handleQueryResult" />
          </div>
          <DataTable :data="queryResult" :loading="loading" />
        </el-tab-pane>

        <el-tab-pane label="常用查询" name="presets">
          <el-card>
            <template #header>
              <div class="card-header">
                <h4>常用查询</h4>
              </div>
            </template>

            <!-- SQL 常用查询 -->
            <el-collapse v-if="dataSource === 'sql'">
              <el-collapse-item
                v-for="(group, groupName) in sqlPresetQueries"
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

            <!-- Neo4j 常用查询 -->
            <el-collapse v-else-if="dataSource === 'neo4j'">
              <el-collapse-item
                v-for="(group, groupName) in neo4jPresetQueries"
                :key="groupName"
                :title="group.name"
              >
                <el-descriptions border>
                  <el-descriptions-item v-for="(preset, index) in group.presets" :key="index" :label="preset.name">
                    <p>{{ preset.description }}</p>
                    <el-button type="primary" size="small" @click="runPresetCypher(preset.query)">
                      执行
                    </el-button>
                    <el-button type="info" size="small" @click="showPresetCypher(preset.query)">
                      查看Cypher
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

    <el-dialog :title="queryDialogTitle" v-model="showQueryPreview" width="60%">
      <pre class="query-preview">{{ queryPreview }}</pre>
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="showQueryPreview = false">关闭</el-button>
          <el-button type="primary" @click="copyToClipboard">复制到剪贴板</el-button>
          <el-button type="success" @click="executePreviewQuery">执行查询</el-button>
        </span>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { ElMessage } from 'element-plus'
import SqlEditor from '@/components/SqlEditor.vue'
import DataTable from '@/components/DataTable.vue'
import TableManager from '@/components/TableManager.vue'
import { executeQuery, executeCypherQuery, getTables, getNodeLabels } from '@/api/db'
import { useDbStore } from '@/stores/db'

// 使用 store
const dbStore = useDbStore()

// 页面状态
const activeTab = ref('manager')
const loading = ref(false)
const dataSource = ref('sql') // 默认为SQL
const currentTables = ref([])
const queryResult = ref({ columns: [], rows: [] })
const showQueryPreview = ref(false)
const queryPreview = ref('')

// 计算属性
const queryDialogTitle = computed(() => {
  return dataSource.value === 'sql' ? 'SQL查询预览' : 'Cypher查询预览'
})

// SQL 常用查询预设
const sqlPresetQueries = ref({
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
  messages: {
    name: '消息队列',
    presets: [
      {
        name: '最近消息',
        description: '显示最近50条消息',
        query: `SELECT * FROM message_queue ORDER BY created_at DESC LIMIT 50`
      },
      {
        name: '用户消息统计',
        description: '按用户统计消息数量',
        query: `SELECT user_name, COUNT(*) as message_count FROM message_queue 
                GROUP BY user_name ORDER BY message_count DESC LIMIT 20`
      }
    ]
  }
})

// Neo4j 常用查询预设
const neo4jPresetQueries = ref({
  memory: {
    name: '记忆节点',
    presets: [
      {
        name: '活跃节点',
        description: '显示最活跃的30个认知节点',
        query: `MATCH (n:CognitiveNode) 
                RETURN n.uid as id, n.name, n.conv_id, n.act_lv, n.created_at 
                ORDER BY n.act_lv DESC LIMIT 30`
      },
      {
        name: '会话统计',
        description: '按会话ID统计节点数量',
        query: `MATCH (n:CognitiveNode) 
                RETURN n.conv_id as conversation_id, COUNT(n) as node_count 
                ORDER BY node_count DESC`
      }
    ]
  },
  associations: {
    name: '节点关联',
    presets: [
      {
        name: '强关联',
        description: '显示关联强度最高的30个关系',
        query: `MATCH (n:CognitiveNode)-[r:ASSOCIATED_WITH]->(m:CognitiveNode) 
                RETURN n.name as source, m.name as target, r.strength as strength 
                ORDER BY r.strength DESC LIMIT 30`
      },
      {
        name: '关系最多的节点',
        description: '显示拥有最多关系的10个节点',
        query: `MATCH (n:CognitiveNode)-[r:ASSOCIATED_WITH]->() 
                RETURN n.name as node_name, COUNT(r) as relationship_count 
                ORDER BY relationship_count DESC LIMIT 10`
      }
    ]
  }
})

// 监听数据源变化
watch(() => dataSource.value, async (newValue) => {
  dbStore.setDataSource(newValue)
  await fetchDataSources()
})

// 获取数据源数据
const fetchDataSources = async () => {
  loading.value = true
  try {
    if (dataSource.value === 'sql') {
      // 获取SQL表
      const response = await getTables()
      currentTables.value = response.data.tables || []
    } else {
      // 获取Neo4j标签
      try {
        const response = await getNodeLabels()
        const labels = []
        
        if (response.data && response.data.results) {
          response.data.results.forEach(row => {
            if (row[0] && Array.isArray(row[0])) {
              row[0].forEach(label => {
                if (!labels.includes(label)) {
                  labels.push(label)
                }
              })
            }
          })
        }
        
        currentTables.value = labels
      } catch (e) {
        console.error('获取Neo4j标签失败:', e)
        currentTables.value = ['CognitiveNode', 'Memory'] // 使用默认值
      }
    }
  } catch (error) {
    ElMessage.error('获取数据源失败: ' + error.message)
  } finally {
    loading.value = false
  }
}

// 处理数据源变更
const handleDataSourceChange = () => {
  // 重置当前结果
  queryResult.value = { columns: [], rows: [] }
}

// 处理查询结果
const handleQueryResult = (result) => {
  queryResult.value = result
}

// 运行预设SQL查询
const runPresetQuery = (query) => {
  loading.value = true

  executeQuery(query)
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

// 运行预设Cypher查询
const runPresetCypher = (query) => {
  loading.value = true

  executeCypherQuery(query)
    .then(response => {
      // 处理Neo4j查询结果
      if (response.data && response.data.results) {
        const rows = []
        const columns = new Set()
        
        // 处理返回特定属性的查询结果
        response.data.metadata.forEach(meta => {
          if (meta && meta.name) {
            columns.add(meta.name)
          }
        })
        
        response.data.results.forEach(row => {
          const rowData = {}
          row.forEach((value, index) => {
            if (response.data.metadata[index] && response.data.metadata[index].name) {
              rowData[response.data.metadata[index].name] = value
            }
          })
          rows.push(rowData)
        })
        
        queryResult.value = {
          columns: Array.from(columns),
          rows: rows
        }
      }
      
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
  queryPreview.value = query
  showQueryPreview.value = true
}

// 显示预设Cypher
const showPresetCypher = (query) => {
  queryPreview.value = query
  showQueryPreview.value = true
}

// 执行预览查询
const executePreviewQuery = () => {
  if (dataSource.value === 'sql') {
    runPresetQuery(queryPreview.value)
  } else {
    runPresetCypher(queryPreview.value)
  }
  showQueryPreview.value = false
}

// 复制到剪贴板
const copyToClipboard = () => {
  navigator.clipboard.writeText(queryPreview.value)
    .then(() => {
      ElMessage.success('查询已复制到剪贴板')
    })
    .catch(() => {
      ElMessage.error('复制失败')
    })
}

// 初始化时获取表列表
onMounted(async () => {
  await fetchDataSources()
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

.query-preview {
  background-color: #f5f7fa;
  padding: 10px;
  border-radius: 4px;
  white-space: pre-wrap;
  word-break: break-all;
}
</style>