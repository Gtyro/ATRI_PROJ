const TableStructure = {
  template: `
    <div class="table-structure">
      <el-alert
        title="表结构信息"
        type="info"
        :closable="false"
        v-if="structureData"
      >
        正在显示 <strong>{{ structureData.table_name }}</strong> 表的结构
      </el-alert>
      
      <el-table
        :data="columns"
        border
        style="width: 100%; margin-top: 15px;"
        v-if="columns.length"
      >
        <el-table-column prop="cid" label="序号" width="70"></el-table-column>
        <el-table-column prop="name" label="列名"></el-table-column>
        <el-table-column prop="type" label="类型"></el-table-column>
        <el-table-column prop="notnull" label="非空">
          <template #default="scope">
            {{ scope.row.notnull ? '是' : '否' }}
          </template>
        </el-table-column>
        <el-table-column prop="default_value" label="默认值">
          <template #default="scope">
            {{ scope.row.default_value || '-' }}
          </template>
        </el-table-column>
        <el-table-column prop="pk" label="主键">
          <template #default="scope">
            {{ scope.row.pk ? '是' : '否' }}
          </template>
        </el-table-column>
      </el-table>
      
      <el-empty description="请选择一个表查看结构" v-else></el-empty>
    </div>
  `,
  props: {
    structureData: {
      type: Object,
      default: null
    }
  },
  setup(props) {
    const columns = Vue.computed(() => {
      return props.structureData?.columns || [];
    });
    
    return {
      columns
    };
  }
}; 