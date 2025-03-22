const SqlEditor = {
  template: `
    <div class="sql-editor">
      <el-form>
        <el-form-item label="SQL查询">
          <el-input
            type="textarea"
            v-model="sql"
            :rows="5"
            placeholder="输入SELECT SQL查询语句..."
          ></el-input>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="executeQuery" :loading="loading">执行查询</el-button>
          <el-button @click="clearQuery">清空</el-button>
        </el-form-item>
      </el-form>
    </div>
  `,
  props: {
    onResult: {
      type: Function,
      required: true
    }
  },
  setup(props) {
    const sql = Vue.ref('');
    const loading = Vue.ref(false);
    
    const executeQuery = () => {
      if (!sql.value.trim()) {
        ElementPlus.ElMessage.warning('请输入SQL查询语句');
        return;
      }
      
      if (!sql.value.toLowerCase().trim().startsWith('select')) {
        ElementPlus.ElMessage.warning('只支持SELECT查询语句');
        return;
      }
      
      loading.value = true;
      
      axios.post('/db/query', { query: sql.value })
        .then(response => {
          props.onResult(response.data);
          ElementPlus.ElMessage.success('查询执行成功');
        })
        .catch(error => {
          ElementPlus.ElMessage.error('查询执行失败: ' + (error.response?.data?.detail || error.message));
        })
        .finally(() => {
          loading.value = false;
        });
    };
    
    const clearQuery = () => {
      sql.value = '';
    };
    
    return {
      sql,
      loading,
      executeQuery,
      clearQuery
    };
  }
}; 