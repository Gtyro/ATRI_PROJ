<template>
  <div class="db-admin">
    <el-card class="box-card">
      <template #header>
        <div class="card-header">
          <h3>数据库管理</h3>
        </div>
      </template>
      
      <el-tabs v-model="activeTab">
        <el-tab-pane label="SQL查询" name="query">
          <SqlEditor :onResult="handleQueryResult" />
          <DataTable :data="queryResult" :loading="loading" />
        </el-tab-pane>
        
        <el-tab-pane label="表结构" name="tables">
          <el-row :gutter="20">
            <el-col :span="6">
              <el-card shadow="never" class="tables-list">
                <template #header>
                  <div class="card-header">
                    <h4>数据库表</h4>
                    <el-button type="primary" size="small" @click="refreshTables">
                      刷新
                    </el-button>
                  </div>
                </template>
                
                <el-menu @select="handleTableSelect">
                  <el-menu-item v-for="table in tables" :key="table" :index="table">
                    {{ table }}
                  </el-menu-item>
                </el-menu>
              </el-card>
            </el-col>
            
            <el-col :span="18">
              <TableStructure :structureData="tableStructure" />
            </el-col>
          </el-row>
        </el-tab-pane>
      </el-tabs>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import axios from 'axios'
import SqlEditor from '@/components/SqlEditor.vue'
import DataTable from '@/components/DataTable.vue'
import TableStructure from '@/components/TableStructure.vue'

const activeTab = ref('query')
const loading = ref(false)
const tables = ref([])
const tableStructure = ref(null)
const queryResult = ref({ columns: [], rows: [] })

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
  fetchTableStructure(tableName)
}

// 处理查询结果
const handleQueryResult = (result) => {
  queryResult.value = result
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
</style>