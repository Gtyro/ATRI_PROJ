<template>
  <div class="table-viewer">
    <el-space class="table-actions" wrap>
      <el-button type="primary" @click="fetchTableData">刷新</el-button>
      <el-button @click="showGeneratedSql = true">查看SQL</el-button>
      <el-button v-if="isFiltered" @click="clearFilters" type="warning">清除筛选</el-button>
      <el-input
        v-model="searchKeyword"
        placeholder="全局搜索"
        clearable
        style="width: 220px"
        @input="handleSearch"
      >
        <template #suffix>
          <el-icon class="el-input__icon"><search /></el-icon>
        </template>
      </el-input>
      <el-switch
        v-model="limitResults"
        active-text="限制结果"
        inactive-text="显示全部"
      />
      <el-input-number 
        v-model="rowLimit" 
        :min="10" 
        :max="1000"
        :step="10"
        v-if="limitResults"
        style="width: 140px"
      />
    </el-space>
    
    <h3>{{ tableName }} 表数据 <small v-if="rows.length">({{ rows.length }} 行)</small></h3>
    
    <el-table 
      :data="rows" 
      border 
      style="width: 100%" 
      v-loading="loading"
      max-height="500"
      @sort-change="handleSortChange"
    >
      <el-table-column
        v-for="column in columns"
        :key="column"
        :prop="column"
        :label="column"
        sortable="custom"
      >
        <template #header="scope">
          <div class="column-header">
            <span>{{ scope.column.label }}</span>
            <el-popover placement="bottom" :width="220" trigger="click">
              <template #reference>
                <el-button size="small" circle><el-icon><filter /></el-icon></el-button>
              </template>
              <div class="column-filter">
                <el-input 
                  v-model="columnFilters[scope.column.property]" 
                  placeholder="筛选值" 
                  size="small"
                  clearable
                  @input="applyFilters"
                ></el-input>
              </div>
            </el-popover>
          </div>
        </template>
      </el-table-column>
    </el-table>
    
    <div class="pagination" v-if="rows.length > 10">
      <el-pagination
        layout="total, sizes, prev, pager, next"
        :total="rows.length"
        :page-size="pageSize"
        @size-change="handleSizeChange"
        @current-change="handleCurrentChange"
      ></el-pagination>
    </div>
    
    <el-dialog title="生成的SQL查询" v-model="showGeneratedSql" width="60%">
      <pre class="sql-preview">{{ generatedSql }}</pre>
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="showGeneratedSql = false">关闭</el-button>
          <el-button type="primary" @click="copyToClipboard">复制到剪贴板</el-button>
        </span>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { ElMessage } from 'element-plus'
import axios from 'axios'

const props = defineProps({
  tableName: {
    type: String,
    required: true
  },
  onResult: {
    type: Function,
    required: true
  }
})

const columns = ref([])
const allRows = ref([])
const rows = ref([])
const loading = ref(false)
const pageSize = ref(10)
const currentPage = ref(1)
const showGeneratedSql = ref(false)
const generatedSql = ref('')
const searchKeyword = ref('')
const columnFilters = ref({})
const limitResults = ref(true)
const rowLimit = ref(100)
const sortConfig = ref({ prop: '', order: '' })

const isFiltered = computed(() => {
  return searchKeyword.value !== '' || 
    Object.values(columnFilters.value).some(value => value !== '')
})

// 监听表名变化，自动加载数据
watch(() => props.tableName, (newVal) => {
  if (newVal) {
    fetchTableData()
  }
}, { immediate: true })

// 监听行数限制变化
watch([limitResults, rowLimit], () => {
  if (props.tableName) {
    fetchTableData()
  }
})

// 获取表数据
const fetchTableData = () => {
  if (!props.tableName) return
  
  loading.value = true
  
  // 构建SQL查询
  const limitClause = limitResults.value ? ` LIMIT ${rowLimit.value}` : ''
  const orderClause = sortConfig.value.prop 
    ? ` ORDER BY ${sortConfig.value.prop} ${sortConfig.value.order === 'ascending' ? 'ASC' : 'DESC'}` 
    : ''
  const sql = `SELECT * FROM ${props.tableName}${orderClause}${limitClause}`
  
  generatedSql.value = sql
  
  axios.post('/db/query', { query: sql })
    .then(response => {
      columns.value = response.data.columns || []
      allRows.value = response.data.rows || []
      rows.value = [...allRows.value]
      
      // 初始化列筛选
      if (columns.value.length > 0) {
        const newFilters = {}
        columns.value.forEach(col => {
          if (!columnFilters.value[col]) {
            newFilters[col] = ''
          }
        })
        columnFilters.value = { ...columnFilters.value, ...newFilters }
      }
      
      // 将数据传递给父组件
      props.onResult(response.data)
      
      ElMessage.success(`成功加载 ${props.tableName} 表数据`)
    })
    .catch(error => {
      ElMessage.error('获取表数据失败: ' + (error.response?.data?.detail || error.message))
    })
    .finally(() => {
      loading.value = false
    })
}

// 处理排序
const handleSortChange = ({ prop, order }) => {
  sortConfig.value = { prop, order }
  fetchTableData()
}

// 应用筛选条件
const applyFilters = () => {
  if (!allRows.value.length) return
  
  let filteredRows = [...allRows.value]
  
  // 应用全局搜索
  if (searchKeyword.value) {
    const keyword = searchKeyword.value.toLowerCase()
    filteredRows = filteredRows.filter(row => {
      return Object.values(row).some(value => {
        return value?.toString().toLowerCase().includes(keyword)
      })
    })
  }
  
  // 应用列筛选
  Object.entries(columnFilters.value).forEach(([column, filter]) => {
    if (filter) {
      filteredRows = filteredRows.filter(row => {
        const cellValue = row[column]?.toString().toLowerCase() || ''
        return cellValue.includes(filter.toLowerCase())
      })
    }
  })
  
  rows.value = filteredRows
}

// 全局搜索
const handleSearch = () => {
  applyFilters()
}

// 清除所有筛选
const clearFilters = () => {
  searchKeyword.value = ''
  Object.keys(columnFilters.value).forEach(key => {
    columnFilters.value[key] = ''
  })
  rows.value = [...allRows.value]
}

// 分页器处理
const handleSizeChange = (val) => {
  pageSize.value = val
}

const handleCurrentChange = (val) => {
  currentPage.value = val
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
</script>

<style scoped>
.table-viewer {
  margin-bottom: 20px;
}

.table-actions {
  margin-bottom: 15px;
}

.column-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.column-filter {
  padding: 10px;
}

.sql-preview {
  background-color: #f5f7fa;
  padding: 10px;
  border-radius: 4px;
  white-space: pre-wrap;
  word-break: break-all;
}
</style> 