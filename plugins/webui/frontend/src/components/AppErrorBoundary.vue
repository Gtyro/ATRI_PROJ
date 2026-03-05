<template>
  <div v-if="hasError" class="app-error-boundary">
    <el-result
      icon="error"
      title="页面渲染异常"
      :sub-title="errorMessage || '页面渲染失败，请稍后重试'"
    >
      <template #extra>
        <el-button type="primary" @click="resetError">重试渲染</el-button>
      </template>
    </el-result>
  </div>
  <slot v-else />
</template>

<script setup lang="ts">
import { computed, onErrorCaptured, ref } from "vue";

const capturedError = ref<unknown>(null);
const errorMessage = ref("");

const hasError = computed(() => capturedError.value != null);

const resetError = (): void => {
  capturedError.value = null;
  errorMessage.value = "";
};

onErrorCaptured((error, _instance, info) => {
  capturedError.value = error;

  const normalized =
    error instanceof Error ? error.message : String(error || "未知错误");
  errorMessage.value = info ? `${normalized}（${info}）` : normalized;

  console.error("ATRI WebUI 渲染异常:", error, info);
  return false;
});
</script>

<style scoped>
.app-error-boundary {
  width: 100%;
  padding-top: 24px;
}
</style>
