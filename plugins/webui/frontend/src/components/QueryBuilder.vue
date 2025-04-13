<template>
  <div class="query-builder">
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
          
          <el-button type="danger" icon="el-icon-delete" circle size="small" @click="removeCondition(index)"></el-button>
        </div>
      </el-form-item>
      
      <el-form-item label="排序" v-if="selectedTable">
        <el-select v-model="orderBy.column" placeholder="排序列" style="width: 160px" clearable>
          <el-option
            v-for="column in tableColumns"
            :key="column.name"
            :label="column.name"
            :value="column.name"
          ></el-option>
        </el-select>
        
        <el-select v-model="orderBy.direction" placeholder="方向" style="width: 120px" v-if="orderBy.column">
          <el-option label="升序" value="ASC"></el-option>
          <el-option label="降序" value="DESC"></el-option>
        </el-select>
      </el-form-item>
      
      <el-form-item label="限制结果数">
        <el-input-number v-model="limit" :min="1" :max="1000"></el-input-number>
      </el-form-item>
      
      <el-form-item>
        <el-button type="primary" @click="buildAndExecuteQuery" :loading="loading">执行查询</el-button>
        <el-button @click="clearBuilder">重置</el-button>
        <el-button type="info" @click="showGeneratedSql = true">查看SQL</el-button>
      </el-form-item>
    </el-form>
    
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
import { ref, computed } from 'vue'
import { ElMessage } from 'element-plus'
import axios from 'axios'

const props = defineProps({
  tables: {
    type: Array,
    default: () => []
  },
  onResult: {
    type: Function,
    required: true
  }
})

const selectedTable = ref('')
const tableColumns = ref([])
const selectedColumns = ref([])
const conditions = ref([])
const orderBy = ref({ column: '', direction: 'ASC' })
const limit = ref(100)
const loading = ref(false)
const showGeneratedSql = ref(false)
const generatedSql = computed(() => buildQuery())

// 当表选择改变时获取列信息
const handleTableChange = (tableName) => {
  if (!tableName) return
  loading.value = true
  
  axios.get(`/db/table/${tableName}`)
    .then(response => {
      tableColumns.value = response.data.columns
      selectedColumns.value = tableColumns.value.map(col => col.name)
    })
    .catch(error => {
      ElMessage.error('获取表结构失败: ' + error.message)
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
  if (orderBy.value.column) {
    sql += ` ORDER BY ${orderBy.value.column} ${orderBy.value.direction}`
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
      props.onResult(response.data)
      ElMessage.success('查询执行成功')
    })
    .catch(error => {
      ElMessage.error('查询执行失败: ' + (error.response?.data?.detail || error.message))
    })
    .finally(() => {
      loading.value = false
    })
}

// 重置查询构建器
const clearBuilder = () => {
  selectedTable.value = ''
  tableColumns.value = []
  selectedColumns.value = []
  conditions.value = []
  orderBy.value = { column: '', direction: 'ASC' }
  limit.value = 100
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
.query-builder {
  margin-bottom: 20px;
}

.condition-row {
  display: flex;
  align-items: center;
  margin-bottom: 10px;
  gap: 10px;
}

.sql-preview {
  background-color: #f5f7fa;
  padding: 10px;
  border-radius: 4px;
  white-space: pre-wrap;
  word-break: break-all;
}
</style> 