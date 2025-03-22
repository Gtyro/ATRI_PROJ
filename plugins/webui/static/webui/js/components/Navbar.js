const Navbar = {
  template: `
    <div class="header">
      <div class="logo">
        <h1>数据库管理面板</h1>
      </div>
      <div class="user-info" v-if="auth.state.user">
        <el-dropdown @command="handleCommand">
          <span class="el-dropdown-link">
            {{ auth.state.user.username }}
            <el-icon class="el-icon--right"><arrow-down /></el-icon>
          </span>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="logout">退出登录</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </div>
    </div>
  `,
  setup() {
    const handleCommand = (command) => {
      if (command === 'logout') {
        auth.logout();
      }
    };

    return {
      auth,
      handleCommand
    };
  }
}; 