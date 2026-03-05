<script setup lang="ts">
import { computed } from "vue";
import { RouterView, useRoute } from "vue-router";

import AppErrorBoundary from "@/components/AppErrorBoundary.vue";

const route = useRoute();
const isLoginPage = computed(() => route.path === "/login");
</script>

<template>
  <div class="app-container">
    <header v-if="isLoginPage" class="app-header">
      <h1>ATRI WebUI</h1>
    </header>

    <main class="app-main">
      <AppErrorBoundary>
        <RouterView v-slot="{ Component }">
          <Suspense>
            <component :is="Component" />
            <template #fallback>
              <div class="route-loading">
                <el-skeleton :rows="6" animated />
              </div>
            </template>
          </Suspense>
        </RouterView>
      </AppErrorBoundary>
    </main>
  </div>
</template>

<style scoped>
.app-container {
  width: 100%;
  margin: 0 auto;
  padding: 0;
}

.app-header {
  padding-bottom: 1rem;
  margin-bottom: 2rem;
  border-bottom: 1px solid #eaeaea;
}

.app-main {
  width: 100%;
}

.route-loading {
  padding: 16px;
  border: 1px solid #ebeef5;
  border-radius: 8px;
  background: #fff;
}
</style>
