const DataTable = {
  template: `
    <div class="result-table" v-if="columns.length">
      <h3>查询结果 ({{ rows.length }} 行)</h3>
      <el-table
        :data="rows"
        border
        style="width: 100%"
        v-loading="loading"
        max-height="500"
      >
        <el-table-column
          v-for="column in columns"
          :key="column"
          :prop="column"
          :label="column"
        ></el-table-column>
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
    </div>
    <div v-else-if="!loading" class="empty-result">
      <el-empty description="无查询结果" v-if="hasQueried"></el-empty>
      <el-empty description="请执行查询" v-else></el-empty>
    </div>
  `,
  props: {
    data: {
      type: Object,
      default: () => ({ columns: [], rows: [] })
    },
    loading: {
      type: Boolean,
      default: false
    }
  },
  setup(props) {
    const columns = Vue.computed(() => props.data.columns || []);
    const rows = Vue.computed(() => props.data.rows || []);
    const pageSize = Vue.ref(10);
    const currentPage = Vue.ref(1);
    const hasQueried = Vue.ref(false);
    
    Vue.watch(() => props.data, () => {
      if (props.data.columns?.length || props.data.rows?.length) {
        hasQueried.value = true;
      }
    });
    
    const handleSizeChange = (val) => {
      pageSize.value = val;
    };
    
    const handleCurrentChange = (val) => {
      currentPage.value = val;
    };
    
    return {
      columns,
      rows,
      pageSize,
      currentPage,
      hasQueried,
      handleSizeChange,
      handleCurrentChange
    };
  }
}; 