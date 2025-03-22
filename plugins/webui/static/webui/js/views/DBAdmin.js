const DBAdmin = {
  template: `
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
  `,
  components: {
    SqlEditor,
    DataTable,
    TableStructure
  },
  setup() {
    const activeTab = Vue.ref('query');
    const loading = Vue.ref(false);
    const tables = Vue.ref([]);
    const tableStructure = Vue.ref(null);
    const queryResult = Vue.ref({ columns: [], rows: [] });
    
    // 获取数据库表列表
    const fetchTables = () => {
      loading.value = true;
      axios.get('/db/tables')
        .then(response => {
          tables.value = response.data.tables;
        })
        .catch(error => {
          ElementPlus.ElMessage.error('获取表列表失败: ' + error.message);
        })
        .finally(() => {
          loading.value = false;
        });
    };
    
    // 刷新表列表
    const refreshTables = () => {
      fetchTables();
    };
    
    // 获取表结构
    const fetchTableStructure = (tableName) => {
      loading.value = true;
      axios.get(`/db/table/${tableName}`)
        .then(response => {
          tableStructure.value = response.data;
        })
        .catch(error => {
          ElementPlus.ElMessage.error('获取表结构失败: ' + error.message);
        })
        .finally(() => {
          loading.value = false;
        });
    };
    
    // 处理表选择
    const handleTableSelect = (tableName) => {
      fetchTableStructure(tableName);
    };
    
    // 处理查询结果
    const handleQueryResult = (result) => {
      queryResult.value = result;
    };
    
    // 初始化时获取表列表
    Vue.onMounted(() => {
      fetchTables();
    });
    
    return {
      activeTab,
      loading,
      tables,
      tableStructure,
      queryResult,
      refreshTables,
      handleTableSelect,
      handleQueryResult
    };
  }
}; 