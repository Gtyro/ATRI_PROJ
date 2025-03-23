<template>
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
</template>

<script setup>
import { computed, ref, watch } from 'vue'

const props = defineProps({
  data: {
    type: Object,
    default: () => ({ columns: [], rows: [] })
  },
  loading: {
    type: Boolean,
    default: false
  }
})

const columns = computed(() => props.data.columns || [])
const rows = computed(() => props.data.rows || [])
const pageSize = ref(10)
const currentPage = ref(1)
const hasQueried = ref(false)

watch(() => props.data, () => {
  if (props.data.columns?.length || props.data.rows?.length) {
    hasQueried.value = true
  }
}, { deep: true })

const handleSizeChange = (val) => {
  pageSize.value = val
}

const handleCurrentChange = (val) => {
  currentPage.value = val
}
</script>

<style scoped>
/* 如果需要组件特定样式可以在这里添加 */
</style> 