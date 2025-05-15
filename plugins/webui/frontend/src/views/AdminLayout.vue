<template>
  <div class="admin-layout-container">
    <div class="sidebar">
      <el-menu
        default-active="1"
        class="sidebar-menu"
        router
      >
        <el-menu-item index="/dashboard/db-admin">
          <el-icon><Menu /></el-icon>
          <span>数据库管理</span>
        </el-menu-item>
        <el-menu-item index="/dashboard/memory-admin">
          <el-icon><Document /></el-icon>
          <span>记忆管理</span>
        </el-menu-item>
      </el-menu>
    </div>

    <div class="right-panel">
      <Navbar />
      <div class="main-content">
        <router-view></router-view>
      </div>
    </div>
  </div>
</template>

<script setup>
import { onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { Menu, Document } from '@element-plus/icons-vue'
import Navbar from '@/components/NavbarHeader.vue'

const router = useRouter()
const authStore = useAuthStore()

onMounted(() => {
  // 检查用户是否已登录
  if (!authStore.isAuthenticated) {
    router.push('/login')
  }
})
</script>

<style scoped>
.admin-layout-container {
  display: flex;
  min-height: 100vh;
}

.right-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
}

.sidebar {
  width: 20%;
  background-color: #304156;
  color: #fff;
  padding: 20px 0;
}

.main-content {
  flex: 1;
  padding: 20px;
  overflow-x: auto;
}

/* 可以添加其他特定于AdminLayout组件的样式 */

@media (max-width: 768px) {
  .admin-layout-container {
    flex-direction: column;
  }

  .sidebar {
    width: 100%;
    padding: 10px;
  }
}
</style>