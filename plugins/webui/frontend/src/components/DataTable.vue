<template>
  <AsyncStateBlock
    :loading="loading"
    :empty="!hasColumns"
    :empty-text="hasQueried ? '无查询结果' : '请执行查询'"
    loading-text="正在加载查询结果..."
    :retryable="false"
    :min-height="160"
  >
    <div class="result-table">
      <div class="table-head">
        <h3>查询结果 ({{ rows.length }} 行)</h3>
        <el-tag v-if="useVirtualTable" type="info" effect="plain">
          虚拟滚动
        </el-tag>
      </div>

      <div
        v-if="useVirtualTable"
        class="virtual-table-shell"
        :style="{ height: `${virtualTableHeight}px` }"
      >
        <el-auto-resizer>
          <template #default="{ width, height }">
            <el-table-v2
              :columns="virtualColumns"
              :data="virtualRows"
              :width="Math.max(Number(width), minVirtualTableWidth)"
              :height="Math.max(Number(height), 220)"
              :row-height="40"
              row-key="__row_key"
              fixed
            />
          </template>
        </el-auto-resizer>
      </div>

      <el-table
        v-else
        :data="displayedRows"
        border
        stripe
        style="width: 100%"
        max-height="500"
      >
        <el-table-column
          v-for="column in columns"
          :key="column"
          :prop="column"
          :label="column"
          show-overflow-tooltip
        />
      </el-table>

      <div class="pagination" v-if="!useVirtualTable && rows.length > 10">
        <el-pagination
          layout="total, sizes, prev, pager, next"
          :total="rows.length"
          :page-size="pageSize"
          @size-change="handleSizeChange"
          @current-change="handleCurrentChange"
        />
      </div>
    </div>
  </AsyncStateBlock>
</template>

<script setup lang="ts">
import { computed, ref, watch } from "vue";

import AsyncStateBlock from "@/components/AsyncStateBlock.vue";

const VIRTUAL_TABLE_ROW_THRESHOLD = 200;
const VIRTUAL_TABLE_COLUMN_THRESHOLD = 12;

interface QueryResultPayload {
  columns?: unknown[];
  rows?: unknown[];
}

const props = withDefaults(
  defineProps<{
    data?: QueryResultPayload;
    loading?: boolean;
  }>(),
  {
    data: () => ({ columns: [], rows: [] }),
    loading: false,
  },
);

const pageSize = ref(10);
const currentPage = ref(1);
const hasQueried = ref(false);

const columns = computed<string[]>(() => {
  return Array.isArray(props.data?.columns)
    ? props.data.columns.map((column) => String(column))
    : [];
});

const normalizeRow = (
  row: unknown,
  rowIndex: number,
): Record<string, unknown> => {
  if (Array.isArray(row)) {
    const mapped: Record<string, unknown> = {};
    row.forEach((value, index) => {
      const key = columns.value[index] || `col_${index + 1}`;
      mapped[key] = value;
    });
    return mapped;
  }

  if (row && typeof row === "object") {
    return { ...(row as Record<string, unknown>) };
  }

  return { value: row, row_index: rowIndex };
};

const rows = computed<Record<string, unknown>[]>(() => {
  if (!Array.isArray(props.data?.rows)) {
    return [];
  }
  return props.data.rows.map((row, index) => normalizeRow(row, index));
});

const hasColumns = computed(() => columns.value.length > 0);

const displayedRows = computed<Record<string, unknown>[]>(() => {
  const start = (currentPage.value - 1) * pageSize.value;
  const end = start + pageSize.value;
  return rows.value.slice(start, end);
});

const useVirtualTable = computed(() => {
  return (
    rows.value.length >= VIRTUAL_TABLE_ROW_THRESHOLD ||
    columns.value.length >= VIRTUAL_TABLE_COLUMN_THRESHOLD
  );
});

const virtualRows = computed<Record<string, unknown>[]>(() => {
  return rows.value.map((row, index) => ({
    ...row,
    __row_key: index,
  }));
});

const formatCellValue = (value: unknown): string => {
  if (value == null || value === "") {
    return "-";
  }
  if (typeof value === "object") {
    try {
      return JSON.stringify(value);
    } catch (_error) {
      return "[object]";
    }
  }
  return String(value);
};

const getColumnWidth = (column: string): number => {
  const length = column.length;
  if (length >= 20) {
    return 240;
  }
  if (length >= 12) {
    return 180;
  }
  return 140;
};

const virtualColumns = computed(() => {
  return columns.value.map((column) => ({
    key: column,
    dataKey: column,
    title: column,
    width: getColumnWidth(column),
    cellRenderer: ({ rowData }: { rowData: Record<string, unknown> }) =>
      formatCellValue(rowData?.[column]),
  }));
});

const minVirtualTableWidth = computed(() => {
  const width = virtualColumns.value.reduce(
    (sum, column) => sum + Number(column.width || 140),
    0,
  );
  return Math.max(width, 640);
});

const virtualTableHeight = computed(() => {
  const visibleRows = Math.max(8, Math.min(14, rows.value.length));
  return visibleRows * 42 + 56;
});

watch(
  () => props.data,
  () => {
    if (columns.value.length > 0 || rows.value.length > 0) {
      hasQueried.value = true;
      currentPage.value = 1;
    }
  },
  { deep: true },
);

const handleSizeChange = (value: number): void => {
  pageSize.value = value;
  currentPage.value = 1;
};

const handleCurrentChange = (value: number): void => {
  currentPage.value = value;
};
</script>

<style scoped>
.result-table {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.table-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
}

.table-head h3 {
  margin: 0;
}

.virtual-table-shell {
  width: 100%;
  border: 1px solid #ebeef5;
  border-radius: 8px;
  overflow: hidden;
}

@media (max-width: 768px) {
  .table-head {
    flex-direction: column;
    align-items: flex-start;
  }
}
</style>
