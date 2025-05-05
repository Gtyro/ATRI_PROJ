<template>
  <div class="table-manager">
    <el-form>
      <el-form-item label="选择表">
        <el-select v-model="selectedTable" placeholder="请选择表" @change="handleTableChange">
          <el-option
            v-for="table in tables"
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
        <el-button type="info" @click="showGeneratedSql = true">查看SQL</el-button>
        <el-button type="success" @click="showAddForm = true">添加记录</el-button>
      </el-form-item>
    </el-form>

    <!-- 数据结果表格 -->
    <div class="result-table" v-if="resultData.columns.length">
      <h3>查询结果 ({{ resultData.rows.length }} 行)</h3>
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

      <div class="pagination" v-if="resultData.rows.length > 10">
        <el-pagination
          layout="total, sizes, prev, pager, next"
          :total="resultData.rows.length"
          :page-size="pageSize"
          @size-change="handleSizeChange"
          @current-change="handleCurrentChange"
        ></el-pagination>
      </div>
    </div>

    <!-- 生成SQL对话框 -->
    <el-dialog title="生成的SQL查询" v-model="showGeneratedSql" width="60%">
      <pre class="sql-preview">{{ generatedSql }}</pre>
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
import axios from 'axios'
import { Delete } from '@element-plus/icons-vue'
import { addRecord, updateRecord, deleteRecord } from '@/api/db'

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

const selectedTable = ref('')
const tableColumns = ref([])
const selectedColumns = ref([])
const conditions = ref([])
const limit = ref(100)
const loading = ref(false)
const showGeneratedSql = ref(false)
const generatedSql = computed(() => buildQuery())

// 数据表格相关状态
const resultData = ref({ columns: [], rows: [] })
const pageSize = ref(10)
const currentPage = ref(1)
const displayedRows = computed(() => {
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

// 当表选择改变时获取列信息
const handleTableChange = (tableName) => {
  if (!tableName) return
  loading.value = true

  axios.get(`/db/table/${tableName}`)
    .then(response => {
      tableColumns.value = response.data.columns
      selectedColumns.value = tableColumns.value.map(col => col.name)
      // 清空之前的结果
      resultData.value = { columns: [], rows: [] }
      // 自动执行查询
      buildAndExecuteQuery()
    })
    .catch(error => {
      console.error('获取表结构失败:', error);
      let errorMessage = '获取表结构失败';

      if (error.response) {
        const detail = error.response.data?.detail;
        if (detail) {
          errorMessage += ': ' + (typeof detail === 'object' ? JSON.stringify(detail) : detail);
        } else {
          errorMessage += ': ' + error.response.status;
        }
      } else if (error.message) {
        errorMessage += ': ' + error.message;
      }

      ElMessage.error(errorMessage);
    })
    .finally(() => {
      loading.value = false
    })
}

// 添加条件
const addCondition = () => {
  conditions.value.push({
    column: '',
    operator: '=',
    value: ''
  })
}

// 移除条件
const removeCondition = (index) => {
  conditions.value.splice(index, 1)
}

// 处理分页大小变化
const handleSizeChange = (val) => {
  pageSize.value = val
  currentPage.value = 1 // 重置为第一页
}

// 处理当前页变化
const handleCurrentChange = (val) => {
  currentPage.value = val
}

// 处理排序变化
const handleSortChange = ({ prop, order }) => {
  sortConfig.value = { prop, order }
  buildAndExecuteQuery()
}

// 构建SQL查询
const buildQuery = () => {
  if (!selectedTable.value) return ''

  // 构建列部分
  const columnsStr = selectedColumns.value.length > 0
    ? selectedColumns.value.join(', ')
    : '*'

  // 构建基础查询
  let sql = `SELECT ${columnsStr} FROM ${selectedTable.value}`

  // 添加WHERE条件
  if (conditions.value.length > 0) {
    const whereConditions = conditions.value
      .filter(c => c.column && c.value)
      .map(c => {
        if (c.operator === 'LIKE') {
          return `${c.column} LIKE '%${c.value}%'`
        }
        return `${c.column} ${c.operator} '${c.value}'`
      })

    if (whereConditions.length > 0) {
      sql += ` WHERE ${whereConditions.join(' AND ')}`
    }
  }

  // 添加排序
  if (sortConfig.value.prop) {
    const direction = sortConfig.value.order === 'ascending' ? 'ASC' : 'DESC'
    sql += ` ORDER BY ${sortConfig.value.prop} ${direction}`
  }

  // 添加限制
  if (limit.value > 0) {
    sql += ` LIMIT ${limit.value}`
  }

  return sql
}

// 构建并执行查询
const buildAndExecuteQuery = () => {
  const sql = buildQuery()
  if (!sql) {
    ElMessage.warning('请先选择表')
    return
  }

  loading.value = true

  axios.post('/db/query', { query: sql })
    .then(response => {
      resultData.value = response.data
      props.onResult(response.data)
      ElMessage.success('查询执行成功')
    })
    .catch(error => {
      console.error('查询执行失败:', error);
      let errorMessage = '查询执行失败';

      if (error.response) {
        const detail = error.response.data?.detail;
        if (detail) {
          errorMessage += ': ' + (typeof detail === 'object' ? JSON.stringify(detail) : detail);
        } else {
          errorMessage += ': ' + error.response.status;
        }
      } else if (error.message) {
        errorMessage += ': ' + error.message;
      }

      ElMessage.error(errorMessage);
    })
    .finally(() => {
      loading.value = false
    })
}

// 重置查询构建器
const clearBuilder = () => {
  selectedColumns.value = tableColumns.value.map(col => col.name)
  conditions.value = []
  sortConfig.value = { prop: '', order: '' }
  limit.value = 100
  buildAndExecuteQuery() // 重新执行查询
}

// 复制SQL到剪贴板
const copyToClipboard = () => {
  navigator.clipboard.writeText(generatedSql.value)
    .then(() => {
      ElMessage.success('SQL已复制到剪贴板')
      showGeneratedSql.value = false
    })
    .catch(() => {
      ElMessage.error('复制失败')
    })
}

// 判断字段是否为主键
const isPrimaryKey = (columnName) => {
  const column = tableColumns.value.find(col => col.name === columnName)
  return column && column.pk === 1
}

// 获取主键名
const getPrimaryKey = () => {
  const pkColumn = tableColumns.value.find(col => col.pk === 1)
  return pkColumn ? pkColumn.name : 'id'
}

// 获取行的主键值
const getRowPrimaryKeyValue = (row) => {
  const pkName = getPrimaryKey()
  return row[pkName]
}

// 处理添加记录
const handleAdd = () => {
  // 过滤掉主键字段
  const primaryKey = getPrimaryKey()
  const data = { ...formData.value }
  if (primaryKey in data) {
    delete data[primaryKey]
  }

  addRecord(selectedTable.value, data)
    .then(response => {
      ElMessage.success(response.data.message || '添加成功')
      showAddForm.value = false
      buildAndExecuteQuery() // 刷新数据
      formData.value = {} // 清空表单
    })
    .catch(error => {
      console.error('添加记录失败:', error);
      let errorMessage = '添加记录失败';

      if (error.response) {
        const detail = error.response.data?.detail;
        if (detail) {
          errorMessage += ': ' + (typeof detail === 'object' ? JSON.stringify(detail) : detail);
        } else {
          errorMessage += ': ' + error.response.status;
        }
      } else if (error.message) {
        errorMessage += ': ' + error.message;
      }

      ElMessage.error(errorMessage);
    })
}

// 处理编辑记录
const handleEdit = (row) => {
  formData.value = { ...row }
  editingId.value = getRowPrimaryKeyValue(row)
  showEditForm.value = true
}

// 处理更新记录
const handleUpdate = () => {
  const primaryKey = getPrimaryKey()
  const id = editingId.value
  const data = { ...formData.value }

  // 移除主键字段
  if (primaryKey in data) {
    delete data[primaryKey]
  }

  updateRecord(selectedTable.value, id, data)
    .then(response => {
      ElMessage.success(response.data.message || '更新成功')
      showEditForm.value = false
      buildAndExecuteQuery() // 刷新数据
    })
    .catch(error => {
      console.error('更新记录失败:', error);
      let errorMessage = '更新记录失败';

      if (error.response) {
        const detail = error.response.data?.detail;
        if (detail) {
          errorMessage += ': ' + (typeof detail === 'object' ? JSON.stringify(detail) : detail);
        } else {
          errorMessage += ': ' + error.response.status;
        }
      } else if (error.message) {
        errorMessage += ': ' + error.message;
      }

      ElMessage.error(errorMessage);
    })
}

// 处理删除记录
const handleDelete = (row) => {
  const id = getRowPrimaryKeyValue(row)

  if (id === undefined) {
    ElMessage.error('无法获取记录ID')
    return
  }

  deleteRecord(selectedTable.value, id)
    .then(response => {
      ElMessage.success(response.data.message || '删除成功')
      buildAndExecuteQuery() // 刷新数据
    })
    .catch(error => {
      console.error('删除错误详情:', error);
      let errorMessage = '删除记录失败';

      if (error.response) {
        const detail = error.response.data?.detail;
        if (detail) {
          errorMessage += ': ' + (typeof detail === 'object' ? JSON.stringify(detail) : detail);
        } else {
          errorMessage += ': ' + error.response.status;
        }
      } else if (error.message) {
        errorMessage += ': ' + error.message;
      }

      ElMessage.error(errorMessage);
    })
}

// 组件挂载时，如果有初始表格，自动加载
onMounted(() => {
  if (props.initialTable) {
    selectedTable.value = props.initialTable
    handleTableChange(props.initialTable)
  }
})
</script>

<style scoped>
.table-manager {
  margin-bottom: 20px;
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
  text-align: right;
}

.sql-preview {
  background-color: #f5f7fa;
  padding: 10px;
  border-radius: 4px;
  white-space: pre-wrap;
  word-break: break-all;
}
</style> 