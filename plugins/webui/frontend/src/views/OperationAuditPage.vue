<template>
  <div class="operation-audit-page" data-testid="operation-audit-page">
    <el-card class="box-card" shadow="never">
      <template #header>
        <div class="header-row">
          <h3>操作审计日志</h3>
          <div class="header-actions">
            <el-input-number
              v-model="retentionDays"
              :min="1"
              :max="3650"
              size="small"
              controls-position="right"
              class="retention-input"
            />
            <el-button
              type="warning"
              :loading="cleanupLoading"
              @click="onCleanupLogs"
            >
              清理过期日志
            </el-button>
            <el-button type="primary" :loading="loading" @click="refreshLogs">
              刷新
            </el-button>
          </div>
        </div>
      </template>

      <div class="filters">
        <el-input
          v-model="filters.username"
          clearable
          placeholder="操作者"
          class="filter-item"
          @keyup.enter="onSearch"
        />
        <el-select
          v-model="filters.action"
          clearable
          filterable
          placeholder="动作"
          class="filter-item"
        >
          <el-option
            v-for="action in actionOptions"
            :key="action"
            :label="action"
            :value="action"
          />
        </el-select>
        <el-select
          v-model="filters.targetType"
          clearable
          filterable
          placeholder="资源类型"
          class="filter-item"
        >
          <el-option
            v-for="targetType in targetTypeOptions"
            :key="targetType"
            :label="targetType"
            :value="targetType"
          />
        </el-select>
        <el-select
          v-model="filters.success"
          placeholder="结果"
          class="filter-item"
          clearable
        >
          <el-option label="全部" value="" />
          <el-option label="成功" value="true" />
          <el-option label="失败" value="false" />
        </el-select>
        <el-button type="primary" @click="onSearch">查询</el-button>
      </div>

      <el-table v-loading="loading" :data="rows" border style="width: 100%">
        <el-table-column label="时间" min-width="170">
          <template #default="scope">
            {{ formatTime(scope.row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column prop="username" label="操作者" min-width="100" />
        <el-table-column prop="action" label="动作" min-width="180" />
        <el-table-column label="目标" min-width="220">
          <template #default="scope">
            {{ formatTarget(scope.row) }}
          </template>
        </el-table-column>
        <el-table-column label="结果" width="90">
          <template #default="scope">
            <el-tag
              :type="scope.row.success ? 'success' : 'danger'"
              size="small"
            >
              {{ scope.row.success ? "成功" : "失败" }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="请求" min-width="210">
          <template #default="scope">
            {{ formatRequest(scope.row) }}
          </template>
        </el-table-column>
        <el-table-column label="详情" min-width="260">
          <template #default="scope">
            <el-popover placement="left-start" width="480" trigger="hover">
              <template #reference>
                <span class="detail-preview">{{
                  previewDetail(scope.row.detail)
                }}</span>
              </template>
              <pre class="detail-content">{{
                stringifyDetail(scope.row.detail)
              }}</pre>
            </el-popover>
          </template>
        </el-table-column>
      </el-table>

      <div class="pagination-wrapper">
        <el-pagination
          v-model:current-page="page"
          v-model:page-size="pageSize"
          :total="total"
          :page-sizes="[20, 50, 100]"
          background
          layout="total, sizes, prev, pager, next"
          @size-change="onPageSizeChange"
          @current-change="loadLogs"
        />
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import {
  cleanupOperationAuditLogs,
  fetchOperationAuditLogs,
  fetchOperationAuditMeta,
} from "@/api/audit";

const loading = ref(false);
const cleanupLoading = ref(false);
const rows = ref([]);
const total = ref(0);
const page = ref(1);
const pageSize = ref(50);
const actionOptions = ref([]);
const targetTypeOptions = ref([]);
const retentionDays = ref(90);
const filters = reactive({
  username: "",
  action: "",
  targetType: "",
  success: "",
});

const loadMeta = async () => {
  try {
    const { data } = await fetchOperationAuditMeta();
    actionOptions.value = Array.isArray(data.actions) ? data.actions : [];
    targetTypeOptions.value = Array.isArray(data.target_types)
      ? data.target_types
      : [];
    retentionDays.value = Number(
      data.default_retention_days || retentionDays.value,
    );
  } catch (error) {
    console.error("加载审计元信息失败:", error);
  }
};

const loadLogs = async () => {
  loading.value = true;
  try {
    const params = {
      limit: pageSize.value,
      offset: (page.value - 1) * pageSize.value,
    };

    if (filters.username.trim()) {
      params.username = filters.username.trim();
    }
    if (filters.action.trim()) {
      params.action = filters.action.trim();
    }
    if (filters.targetType.trim()) {
      params.target_type = filters.targetType.trim();
    }
    if (filters.success === "true") {
      params.success = true;
    } else if (filters.success === "false") {
      params.success = false;
    }

    const { data } = await fetchOperationAuditLogs(params);
    rows.value = Array.isArray(data.items) ? data.items : [];
    total.value = Number(data.total || 0);
  } catch (error) {
    console.error("加载操作审计日志失败:", error);
    ElMessage.error("加载操作审计日志失败");
  } finally {
    loading.value = false;
  }
};

const onSearch = () => {
  page.value = 1;
  void loadLogs();
};

const refreshLogs = () => {
  void loadLogs();
};

const onCleanupLogs = async () => {
  try {
    await ElMessageBox.confirm(
      `将删除创建时间早于 ${retentionDays.value} 天前的审计日志，是否继续？`,
      "确认清理",
      {
        type: "warning",
        confirmButtonText: "继续",
        cancelButtonText: "取消",
      },
    );
  } catch (error) {
    return;
  }

  cleanupLoading.value = true;
  try {
    const { data } = await cleanupOperationAuditLogs(retentionDays.value);
    ElMessage.success(`清理完成，删除 ${data.deleted} 条日志`);
    page.value = 1;
    await loadLogs();
  } catch (error) {
    console.error("清理操作审计日志失败:", error);
    ElMessage.error("清理操作审计日志失败");
  } finally {
    cleanupLoading.value = false;
  }
};

const onPageSizeChange = () => {
  page.value = 1;
  void loadLogs();
};

const formatTime = (value) => {
  if (!value) {
    return "-";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return String(value);
  }
  return date.toLocaleString();
};

const formatTarget = (row) => {
  if (!row?.target_type) {
    return "-";
  }
  return row.target_id
    ? `${row.target_type}:${row.target_id}`
    : row.target_type;
};

const formatRequest = (row) => {
  const method = row?.request_method || "";
  const path = row?.request_path || "";
  const value = `${method} ${path}`.trim();
  return value || "-";
};

const stringifyDetail = (detail) => {
  if (detail === null || detail === undefined) {
    return "-";
  }
  if (typeof detail === "string") {
    return detail;
  }
  try {
    return JSON.stringify(detail, null, 2);
  } catch (error) {
    return String(detail);
  }
};

const previewDetail = (detail) => {
  const text = stringifyDetail(detail);
  if (text.length <= 90) {
    return text;
  }
  return `${text.slice(0, 90)}...`;
};

onMounted(() => {
  void loadMeta();
  void loadLogs();
});
</script>

<style scoped>
.operation-audit-page {
  height: 100%;
}

.header-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
}

.header-row h3 {
  margin: 0;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.retention-input {
  width: 150px;
}

.filters {
  display: flex;
  gap: 10px;
  margin-bottom: 12px;
  flex-wrap: wrap;
}

.filter-item {
  width: 220px;
}

.detail-preview {
  display: inline-block;
  max-width: 100%;
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
  color: #606266;
}

.detail-content {
  margin: 0;
  white-space: pre-wrap;
  word-break: break-word;
  font-size: 12px;
  line-height: 1.5;
}

.pagination-wrapper {
  margin-top: 12px;
  display: flex;
  justify-content: flex-end;
}

@media (max-width: 768px) {
  .header-row {
    align-items: flex-start;
    flex-direction: column;
  }

  .header-actions {
    width: 100%;
  }

  .retention-input {
    width: 100%;
  }

  .filter-item {
    width: 100%;
  }

  .pagination-wrapper {
    justify-content: flex-start;
  }
}
</style>
