<template>
  <div class="async-state-block" :style="blockStyle">
    <template v-if="loading">
      <div class="state-panel">
        <el-skeleton :rows="skeletonRows" animated />
        <p v-if="loadingText" class="state-text">{{ loadingText }}</p>
      </div>
    </template>

    <template v-else-if="hasError">
      <el-result
        icon="error"
        :title="errorTitle"
        :sub-title="normalizedErrorText || errorFallbackText"
      >
        <template #extra>
          <el-button
            v-if="retryable"
            type="primary"
            @click="$emit('retry')"
            data-testid="async-state-retry"
          >
            {{ retryText }}
          </el-button>
        </template>
      </el-result>
    </template>

    <template v-else-if="empty">
      <el-empty :description="emptyText" :image-size="56" />
    </template>

    <slot v-else />
  </div>
</template>

<script setup lang="ts">
import { computed } from "vue";

const props = withDefaults(
  defineProps<{
    loading?: boolean;
    errorText?: string | null;
    empty?: boolean;
    emptyText?: string;
    loadingText?: string;
    errorTitle?: string;
    errorFallbackText?: string;
    retryable?: boolean;
    retryText?: string;
    minHeight?: number;
    skeletonRows?: number;
  }>(),
  {
    loading: false,
    errorText: "",
    empty: false,
    emptyText: "暂无数据",
    loadingText: "加载中...",
    errorTitle: "加载失败",
    errorFallbackText: "数据加载失败，请稍后重试",
    retryable: true,
    retryText: "重试",
    minHeight: 180,
    skeletonRows: 4,
  },
);

defineEmits<{
  (event: "retry"): void;
}>();

const normalizedErrorText = computed(() =>
  String(props.errorText || "").trim(),
);
const hasError = computed(() => normalizedErrorText.value.length > 0);
const blockStyle = computed(() => ({ minHeight: `${props.minHeight}px` }));
</script>

<style scoped>
.async-state-block {
  width: 100%;
}

.state-panel {
  border: 1px solid #ebeef5;
  border-radius: 8px;
  padding: 14px;
  background: #fff;
}

.state-text {
  margin: 12px 0 0;
  font-size: 12px;
  color: #909399;
}
</style>
