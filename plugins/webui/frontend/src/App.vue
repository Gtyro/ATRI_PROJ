<script setup>
import { RouterView, useRoute } from 'vue-router'
import { computed } from 'vue'

const route = useRoute()
const isLoginPage = computed(() => route.name === 'login')
</script>

<template>
  <div class="app-container">
    <header v-if="isLoginPage" class="app-header">
      <h1>ATRI WebUI</h1>
    </header>
    <main>
      <RouterView />
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
</style>
