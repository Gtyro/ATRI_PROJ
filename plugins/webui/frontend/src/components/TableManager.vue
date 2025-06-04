<template>
  <div class="table-manager">
    <el-form>
      <el-form-item label="数据源">
        <el-radio-group v-model="dataSource" @change="handleDataSourceChange">
          <el-radio :value="'sql'">SQL/ORM</el-radio>
          <el-radio :value="'neo4j'">Neo4j/OGM</el-radio>
        </el-radio-group>
      </el-form-item>

      <el-form-item label="选择表">
        <el-select v-model="selectedTable" placeholder="请选择表" @change="handleTableChange">
          <el-option
            v-for="table in availableTables"
            :key="table"
            :label="table"
            :value="table"
          ></el-option>
        </el-select>
      </el-form-item>

      <el-form-item label="选择列" v-if="selectedTable">
        <el-checkbox-group v-model="selectedColumns">
          <el-checkbox
            v-for="column in tableColumns"
            :key="column.name"
            :label="column.name"
          >
            {{ column.name }} ({{ column.type }})
          </el-checkbox>
        </el-checkbox-group>
      </el-form-item>

      <el-form-item label="过滤条件" v-if="selectedTable">
        <el-button type="primary" size="small" @click="addCondition">添加条件</el-button>

        <div v-for="(condition, index) in conditions" :key="index" class="condition-row">
          <el-select v-model="condition.column" placeholder="选择列" style="width: 160px">
            <el-option
              v-for="column in tableColumns"
              :key="column.name"
              :label="column.name"
              :value="column.name"
            ></el-option>
          </el-select>

          <el-select v-model="condition.operator" placeholder="条件" style="width: 120px">
            <el-option label="等于" value="="></el-option>
            <el-option label="不等于" value="!="></el-option>
            <el-option label="大于" value=">"></el-option>
            <el-option label="小于" value="<"></el-option>
            <el-option label="包含" value="LIKE"></el-option>
          </el-select>

          <el-input v-model="condition.value" placeholder="值" style="width: 160px"></el-input>

          <el-button type="danger" circle size="small" @click="removeCondition(index)">
            <el-icon><Delete /></el-icon>
          </el-button>
        </div>
      </el-form-item>

      <el-form-item label="限制结果数">
        <el-input-number v-model="limit" :min="1" :max="1000" :step="10"></el-input-number>
      </el-form-item>

      <el-form-item>
        <el-button type="primary" @click="buildAndExecuteQuery" :loading="loading">执行查询</el-button>
        <el-button @click="clearBuilder">重置</el-button>
        <el-button type="info" @click="showQueryPreview">查看查询</el-button>
        <el-button type="success" @click="showAddForm = true">添加记录</el-button>
      </el-form-item>
    </el-form>

    <!-- 数据结果表格 -->
    <div class="result-table" v-if="resultData.columns && resultData.columns.length">
      <h3>查询结果 ({{ resultData.rows ? resultData.rows.length : 0 }} 行)</h3>
      <el-table
        :data="displayedRows"
        border
        style="width: 100%"
        v-loading="loading"
        max-height="500"
        @sort-change="handleSortChange"
      >
        <el-table-column
          v-for="column in resultData.columns"
          :key="column"
          :prop="column"
          :label="column"
          sortable="custom"
        ></el-table-column>
        <el-table-column label="操作" width="160" fixed="right">
          <template #default="scope">
            <el-button size="small" @click="handleEdit(scope.row)">编辑</el-button>
            <el-popconfirm
              title="确定删除这条记录吗？"
              @confirm="handleDelete(scope.row)"
            >
              <template #reference>
                <el-button size="small" type="danger">删除</el-button>
              </template>
            </el-popconfirm>
          </template>
        </el-table-column>
      </el-table>

      <div class="pagination" v-if="resultData.rows && resultData.rows.length > 10">
        <el-pagination
          layout="total, sizes, prev, pager, next"
          :total="resultData.rows ? resultData.rows.length : 0"
          :page-size="pageSize"
          @size-change="handleSizeChange"
          @current-change="handleCurrentChange"
        ></el-pagination>
      </div>
    </div>

    <!-- 生成查询对话框 -->
    <el-dialog :title="queryDialogTitle" v-model="showGeneratedSql" width="60%">
      <pre class="sql-preview">{{ generatedQuery }}</pre>
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="showGeneratedSql = false">关闭</el-button>
          <el-button type="primary" @click="copyToClipboard">复制到剪贴板</el-button>
        </span>
      </template>
    </el-dialog>

    <!-- 添加记录对话框 -->
    <el-dialog title="添加记录" v-model="showAddForm" width="50%">
      <el-form :model="formData" label-width="120px">
        <el-form-item
          v-for="col in tableColumns"
          :key="col.name"
          :label="col.name"
          :prop="col.name"
        >
          <el-input v-model="formData[col.name]" v-if="!isPrimaryKey(col.name)"></el-input>
          <el-tag v-else>自动生成</el-tag>
        </el-form-item>
      </el-form>
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="showAddForm = false">取消</el-button>
          <el-button type="primary" @click="handleAdd">提交</el-button>
        </span>
      </template>
    </el-dialog>

    <!-- 编辑记录对话框 -->
    <el-dialog title="编辑记录" v-model="showEditForm" width="50%">
      <el-form :model="formData" label-width="120px">
        <el-form-item
          v-for="col in tableColumns"
          :key="col.name"
          :label="col.name"
          :prop="col.name"
        >
          <el-input v-model="formData[col.name]" v-if="!isPrimaryKey(col.name)"></el-input>
          <el-tag v-else>{{ formData[col.name] }}</el-tag>
        </el-form-item>
      </el-form>
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="showEditForm = false">取消</el-button>
          <el-button type="primary" @click="handleUpdate">提交</el-button>
        </span>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { request } from '@/api'
import { Delete } from '@element-plus/icons-vue'
import {
  addRecord, updateRecord, deleteRecord,
  executeQuery, executeCypherQuery,
  getTables, getNodeLabels,
  createCognitiveNode, updateCognitiveNode, deleteCognitiveNode
} from '@/api/db'
import { useDbStore } from '@/stores/db'

// 使用Store
const dbStore = useDbStore()

const props = defineProps({
  tables: {
    type: Array,
    default: () => []
  },
  onResult: {
    type: Function,
    required: true
  },
  initialTable: {
    type: String,
    default: ''
  }
})

// 数据源相关状态
const dataSource = ref('sql') // 默认为SQL
const sqlTables = ref([])
const neo4jLabels = ref([])
const availableTables = computed(() => {
  return dataSource.value === 'sql' ? sqlTables.value : neo4jLabels.value
})

const selectedTable = ref('')
const tableColumns = ref([])
const selectedColumns = ref([])
const conditions = ref([])
const limit = ref(100)
const loading = ref(false)
const showGeneratedSql = ref(false)
const generatedQuery = computed(() => {
  return dataSource.value === 'sql' ? buildSqlQuery() : buildCypherQuery()
})
const queryDialogTitle = computed(() => {
  return dataSource.value === 'sql' ? '生成的SQL查询' : '生成的Cypher查询'
})

// 数据表格相关状态
const resultData = ref({ columns: [], rows: [] })
const pageSize = ref(10)
const currentPage = ref(1)
const displayedRows = computed(() => {
  if (!resultData.value.rows) return []
  const start = (currentPage.value - 1) * pageSize.value
  const end = start + pageSize.value
  return resultData.value.rows.slice(start, end)
})
const sortConfig = ref({ prop: '', order: '' })

// 表单相关状态
const showAddForm = ref(false)
const showEditForm = ref(false)
const formData = ref({})
const editingId = ref(null)

// 监听初始表名
watch(() => props.initialTable, (newVal) => {
  if (newVal && newVal !== selectedTable.value) {
    selectedTable.value = newVal
    handleTableChange(newVal)
  }
}, { immediate: true })

// 监听props中的tables变化
watch(() => props.tables, (newTables) => {
  if (newTables && newTables.length > 0) {
    sqlTables.value = newTables
  }
}, { immediate: true })

// 初始化时获取数据源
onMounted(async () => {
  await fetchDataSources()
})

// 获取所有数据源
const fetchDataSources = async () => {
  try {
    // 获取SQL表
    const tablesResp = await getTables()
    sqlTables.value = tablesResp.data.tables || []

    // 获取Neo4j标签
    try {
      const response = await getNodeLabels()
      let labels = []

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

      // 确保预定义的模型始终可见
      const predefinedModels = ['CognitiveNode', 'Memory', 'NodeAssociation']
      predefinedModels.forEach(model => {
        if (!labels.includes(model)) {
          labels.push(model)
        }
      })

      neo4jLabels.value = labels
    } catch (error) {
      console.error('Neo4j标签获取失败:', error)
      neo4jLabels.value = ['CognitiveNode', 'Memory', 'NodeAssociation'] // 使用默认值
    }
  } catch (error) {
    ElMessage.error('获取数据源失败')
    console.error(error)
  }
}

// 当数据源变更时
const handleDataSourceChange = async () => {
  // 清空当前选中的表和列
  selectedTable.value = ''
  tableColumns.value = []
  selectedColumns.value = []
  resultData.value = { columns: [], rows: [] }

  // 重新设置store中的数据源
  dbStore.setDataSource(dataSource.value)
}

// 当表选择改变时获取列信息
const handleTableChange = async (tableName) => {
  if (!tableName) return
  loading.value = true

  try {
    if (dataSource.value === 'sql') {
      // SQL表结构获取
      const response = await request.get(`/db/table/${tableName}`)
      tableColumns.value = response.data.columns
      selectedColumns.value = tableColumns.value.map(col => col.name)
    } else {
      // Neo4j节点属性获取 (使用示例查询获取一个节点的所有属性)
      const query = `MATCH (n:${tableName}) RETURN n LIMIT 1`
      const response = await executeCypherQuery(query)

      if (response.data && response.data.results && response.data.results.length > 0) {
        const nodeProps = []
        // 处理结果，提取节点属性
        const node = response.data.results[0][0]
        if (node) {
          // 从Neo4j结果中提取属性
          const properties = Object.keys(node.properties || {})
          properties.forEach(prop => {
            nodeProps.push({ name: prop, type: typeof node.properties[prop] })
          })
          // 添加ID属性
          nodeProps.push({ name: 'id', type: 'string' })
        }

        tableColumns.value = nodeProps
        selectedColumns.value = tableColumns.value.map(col => col.name)
      } else {
        // 如果没有结果，使用默认属性
        const defaultProps = dataSource.value === 'neo4j' && tableName === 'CognitiveNode'
          ? [
              { name: 'uid', type: 'string' },
              { name: 'name', type: 'string' },
              { name: 'conv_id', type: 'string' },
              { name: 'act_lv', type: 'number' },
              { name: 'created_at', type: 'datetime' },
              { name: 'last_accessed', type: 'datetime' },
              { name: 'is_permanent', type: 'boolean' }
            ]
          : [{ name: 'id', type: 'string' }]

        tableColumns.value = defaultProps
        selectedColumns.value = tableColumns.value.map(col => col.name)
      }
    }

    // 自动执行查询
    buildAndExecuteQuery()
  } catch (error) {
    console.error('获取表结构失败:', error)
    let errorMessage = '获取表结构失败'

    if (error.response) {
      const detail = error.response.data?.detail
      if (detail) {
        errorMessage += ': ' + (typeof detail === 'object' ? JSON.stringify(detail) : detail)
      } else {
        errorMessage += ': ' + error.response.status
      }
    } else if (error.message) {
      errorMessage += ': ' + error.message
    }

    ElMessage.error(errorMessage)
  } finally {
    loading.value = false
  }
}

// 添加条件
const addCondition = () => {
  conditions.value.push({
    column: tableColumns.value.length ? tableColumns.value[0].name : '',
    operator: '=',
    value: ''
  })
}

// 移除条件
const removeCondition = (index) => {
  conditions.value.splice(index, 1)
}

// 构建SQL查询
const buildSqlQuery = () => {
  if (!selectedTable.value) return ''

  let query = 'SELECT '

  // 处理选择的列
  if (selectedColumns.value.length === 0) {
    query += '* '
  } else {
    query += selectedColumns.value.join(', ')
  }

  query += ` FROM ${selectedTable.value}`

  // 处理条件
  if (conditions.value.length > 0) {
    query += ' WHERE '
    query += conditions.value
      .filter(c => c.column && c.operator && c.value !== '')
      .map(c => {
        if (c.operator === 'LIKE') {
          return `${c.column} LIKE '%${c.value}%'`
        }
        return `${c.column} ${c.operator} '${c.value}'`
      })
      .join(' AND ')
  }

  // 添加排序
  if (sortConfig.value.prop && sortConfig.value.order) {
    query += ` ORDER BY ${sortConfig.value.prop} ${sortConfig.value.order === 'ascending' ? 'ASC' : 'DESC'}`
  }

  // 添加限制
  if (limit.value) {
    query += ` LIMIT ${limit.value}`
  }

  return query
}

// 构建Cypher查询
const buildCypherQuery = () => {
  if (!selectedTable.value) return ''

  let query = `MATCH (n:${selectedTable.value}) `

  // 处理条件
  if (conditions.value.length > 0) {
    query += 'WHERE '
    query += conditions.value
      .filter(c => c.column && c.operator && c.value !== '')
      .map(c => {
        if (c.operator === 'LIKE') {
          return `n.${c.column} =~ '.*${c.value}.*'`
        }
        return `n.${c.column} ${c.operator} '${c.value}'`
      })
      .join(' AND ')
  }

  // 返回选择的属性
  if (selectedColumns.value.length === 0) {
    query += 'RETURN n'
  } else {
    // 对于特殊的id列，需要使用节点的id
    const returnParts = selectedColumns.value.map(col => {
      if (col.toLowerCase() === 'id' || col.toLowerCase() === 'uid') {
        return 'n.uid as id'
      }
      return `n.${col} as ${col}`
    })
    query += `RETURN ${returnParts.join(', ')}`
  }

  // 添加排序
  if (sortConfig.value.prop && sortConfig.value.order) {
    const prop = sortConfig.value.prop
    const direction = sortConfig.value.order === 'ascending' ? 'ASC' : 'DESC'
    query += ` ORDER BY n.${prop} ${direction}`
  }

  // 添加限制
  if (limit.value) {
    query += ` LIMIT ${limit.value}`
  }

  return query
}

// 显示查询预览
const showQueryPreview = () => {
  showGeneratedSql.value = true
}

// 构建并执行查询
const buildAndExecuteQuery = async () => {
  if (!selectedTable.value) return

  loading.value = true
  try {
    if (dataSource.value === 'sql') {
      const query = buildSqlQuery()
      const response = await executeQuery(query)
      resultData.value = response.data
    } else {
      const query = buildCypherQuery()
      const response = await executeCypherQuery(query)

      // 处理Neo4j查询结果
      if (response.data && response.data.results) {
        const rows = []
        const columns = new Set()

        // 如果是返回整个节点的查询
        if (response.data.results.length > 0 && response.data.results[0].length === 1 && typeof response.data.results[0][0] === 'object') {
          response.data.results.forEach(row => {
            if (row[0] && row[0].properties) {
              const nodeData = { ...row[0].properties, id: row[0].identity.toString() }

              // 收集所有可能的列
              Object.keys(nodeData).forEach(key => columns.add(key))

              rows.push(nodeData)
            }
          })
        } else {
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
        }

        resultData.value = {
          columns: Array.from(columns),
          rows: rows
        }
      } else {
        resultData.value = { columns: [], rows: [] }
      }
    }

    // 重置分页
    currentPage.value = 1

    // 回调返回结果
    props.onResult(resultData.value)
  } catch (error) {
    console.error('查询执行失败:', error)
    let errorMessage = '查询执行失败'

    if (error.response) {
      const detail = error.response.data?.detail
      if (detail) {
        errorMessage += ': ' + (typeof detail === 'object' ? JSON.stringify(detail) : detail)
      }
    } else if (error.message) {
      errorMessage += ': ' + error.message
    }

    ElMessage.error(errorMessage)
  } finally {
    loading.value = false
  }
}

// 清空查询构建器
const clearBuilder = () => {
  selectedColumns.value = tableColumns.value.map(col => col.name)
  conditions.value = []
  sortConfig.value = { prop: '', order: '' }
  currentPage.value = 1
}

// 复制到剪贴板
const copyToClipboard = () => {
  navigator.clipboard.writeText(generatedQuery.value)
    .then(() => {
      ElMessage.success('查询已复制到剪贴板')
    })
    .catch(() => {
      ElMessage.error('复制失败')
    })
}

// 处理排序变化
const handleSortChange = ({ prop, order }) => {
  sortConfig.value = { prop, order }
  buildAndExecuteQuery()
}

// 处理分页尺寸变化
const handleSizeChange = (size) => {
  pageSize.value = size
  currentPage.value = 1
}

// 处理页码变化
const handleCurrentChange = (page) => {
  currentPage.value = page
}

// 判断是否为主键
const isPrimaryKey = (columnName) => {
  const column = tableColumns.value.find(col => col.name === columnName)
  return column && (column.pk === 1 || columnName.toLowerCase() === 'id' || columnName.toLowerCase() === 'uid')
}

// 获取主键字段名和值
const getPrimaryKeyInfo = (row) => {
  // 寻找主键字段
  let pkColumn = tableColumns.value.find(col => col.pk === 1)

  // 如果没有明确的主键，尝试使用id或uid字段
  if (!pkColumn) {
    pkColumn = tableColumns.value.find(col =>
      col.name.toLowerCase() === 'id' || col.name.toLowerCase() === 'uid'
    )
  }

  if (!pkColumn) {
    return { name: 'id', value: row.id || null }
  }

  return { name: pkColumn.name, value: row[pkColumn.name] }
}

// 处理添加记录
const handleAdd = async () => {
  if (!selectedTable.value) return

  try {
    loading.value = true
    let response

    if (dataSource.value === 'sql') {
      response = await addRecord(selectedTable.value, formData.value)
    } else {
      // 针对Neo4j的CognitiveNode特殊处理
      if (selectedTable.value === 'CognitiveNode') {
        response = await createCognitiveNode(formData.value)
      } else {
        // 通用Neo4j创建 - 构建Cypher查询
        const properties = Object.entries(formData.value)
          .filter(([k, v]) => v !== null && v !== undefined && k !== 'id' && k !== 'uid')
          .map(([k, v]) => `${k}: ${typeof v === 'string' ? `'${v}'` : v}`)
          .join(', ')

        const query = `CREATE (n:${selectedTable.value} {${properties}}) RETURN n`
        response = await executeCypherQuery(query)
      }
    }

    ElMessage.success('添加成功')
    showAddForm.value = false
    formData.value = {}

    // 刷新数据
    buildAndExecuteQuery()
  } catch (error) {
    console.error('添加失败:', error)
    ElMessage.error('添加失败: ' + (error.response?.data?.detail || error.message))
  } finally {
    loading.value = false
  }
}

// 处理编辑操作
const handleEdit = (row) => {
  // 复制行数据到表单
  formData.value = { ...row }

  // 获取主键信息
  const pkInfo = getPrimaryKeyInfo(row)
  editingId.value = pkInfo.value

  showEditForm.value = true
}

// 处理更新记录
const handleUpdate = async () => {
  if (!selectedTable.value || !editingId.value) return

  try {
    loading.value = true

    if (dataSource.value === 'sql') {
      await updateRecord(selectedTable.value, editingId.value, formData.value)
    } else {
      // 针对Neo4j的CognitiveNode特殊处理
      if (selectedTable.value === 'CognitiveNode') {
        await updateCognitiveNode(editingId.value, formData.value)
      } else {
        // 通用Neo4j更新 - 构建Cypher查询
        const properties = Object.entries(formData.value)
          .filter(([k, v]) => v !== null && v !== undefined && k !== 'id' && k !== 'uid')
          .map(([k, v]) => `n.${k} = ${typeof v === 'string' ? `'${v}'` : v}`)
          .join(', ')

        const query = `MATCH (n:${selectedTable.value}) WHERE n.uid = '${editingId.value}' SET ${properties} RETURN n`
        await executeCypherQuery(query)
      }
    }

    ElMessage.success('更新成功')
    showEditForm.value = false
    formData.value = {}
    editingId.value = null

    // 刷新数据
    buildAndExecuteQuery()
  } catch (error) {
    console.error('更新失败:', error)
    ElMessage.error('更新失败: ' + (error.response?.data?.detail || error.message))
  } finally {
    loading.value = false
  }
}

// 处理删除操作
const handleDelete = async (row) => {
  if (!selectedTable.value) return

  // 获取主键信息
  const pkInfo = getPrimaryKeyInfo(row)
  if (!pkInfo.value) {
    ElMessage.error('无法确定要删除的记录ID')
    return
  }

  try {
    loading.value = true

    if (dataSource.value === 'sql') {
      await deleteRecord(selectedTable.value, pkInfo.value)
    } else {
      // 针对Neo4j的CognitiveNode特殊处理
      if (selectedTable.value === 'CognitiveNode') {
        await deleteCognitiveNode(pkInfo.value)
      } else {
        // 通用Neo4j删除 - 构建Cypher查询
        const query = `MATCH (n:${selectedTable.value}) WHERE n.uid = '${pkInfo.value}' DELETE n`
        await executeCypherQuery(query)
      }
    }

    ElMessage.success('删除成功')

    // 刷新数据
    buildAndExecuteQuery()
  } catch (error) {
    console.error('删除失败:', error)
    ElMessage.error('删除失败: ' + (error.response?.data?.detail || error.message))
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.table-manager {
  width: 100%;
}

.condition-row {
  display: flex;
  align-items: center;
  margin-bottom: 10px;
  gap: 10px;
}

.result-table {
  margin-top: 20px;
}

.pagination {
  margin-top: 15px;
  display: flex;
  justify-content: flex-end;
}

.sql-preview {
  background-color: #f5f7fa;
  padding: 10px;
  border-radius: 4px;
  white-space: pre-wrap;
  word-break: break-all;
}
</style> 