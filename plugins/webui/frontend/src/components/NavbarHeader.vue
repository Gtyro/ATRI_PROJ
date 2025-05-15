<template>
  <div class="header">
    <div class="user-info" v-if="authStore.user">
      <el-dropdown @command="handleCommand">
        <span class="el-dropdown-link">
          {{ authStore.user.username }}
          <el-icon class="el-icon--right"><ArrowDown /></el-icon>
        </span>
        <template #dropdown>
          <el-dropdown-menu>
            <el-dropdown-item command="logout">退出登录</el-dropdown-item>
          </el-dropdown-menu>
        </template>
      </el-dropdown>
    </div>
  </div>
</template>

<script setup>
import { ArrowDown } from '@element-plus/icons-vue'
import { useAuthStore } from '@/stores/auth'

const authStore = useAuthStore()

const handleCommand = (command) => {
  if (command === 'logout') {
    authStore.logout()
  }
}
</script>

<style scoped>
.el-dropdown {
  display: flex;
  justify-content: flex-end; /* 使下拉菜单靠右显示 */
}
</style> 