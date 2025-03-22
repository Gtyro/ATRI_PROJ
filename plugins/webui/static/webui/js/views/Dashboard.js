const Dashboard = {
  template: `
    <div class="dashboard-container">
      <div class="sidebar">
        <el-menu
          default-active="1"
          class="sidebar-menu"
          router
        >
          <el-menu-item index="/dashboard/db-admin">
            <i class="el-icon-menu"></i>
            <span>数据库管理</span>
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
  `,
  setup() {
    // 检查用户是否已登录
    if (!auth.state.isAuthenticated) {
      router.push('/login');
    }
    
    return {};
  }
}; 