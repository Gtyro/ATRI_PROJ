// 认证状态管理
const auth = {
  // 状态
  state: Vue.reactive({
    token: localStorage.getItem('token') || null,
    user: JSON.parse(localStorage.getItem('user')) || null,
    isAuthenticated: !!localStorage.getItem('token')
  }),

  // 方法
  login(username, password) {
    return new Promise((resolve, reject) => {
      // 使用FormData格式，这是OAuth2规范需要的
      const formData = new FormData();
      formData.append('username', username);
      formData.append('password', password);

      axios.post('/auth/token', formData)
        .then(response => {
          const token = response.data.access_token;
          this.setToken(token);
          this.fetchUserInfo();
          resolve(response);
        })
        .catch(error => {
          this.clearAuth();
          reject(error);
        });
    });
  },

  setToken(token) {
    this.state.token = token;
    this.state.isAuthenticated = true;
    localStorage.setItem('token', token);
    // 设置axios默认请求头
    axios.defaults.headers.common['Authorization'] = `Bearer ${token}`;
  },

  fetchUserInfo() {
    return axios.get('/auth/users/me')
      .then(response => {
        const user = response.data;
        this.state.user = user;
        localStorage.setItem('user', JSON.stringify(user));
        return user;
      });
  },

  logout() {
    this.clearAuth();
    router.push('/login');
  },

  clearAuth() {
    this.state.token = null;
    this.state.user = null;
    this.state.isAuthenticated = false;
    localStorage.removeItem('token');
    localStorage.removeItem('user');
    delete axios.defaults.headers.common['Authorization'];
  },

  // 初始化
  init() {
    if (this.state.token) {
      axios.defaults.headers.common['Authorization'] = `Bearer ${this.state.token}`;
      // 验证token有效性
      this.fetchUserInfo().catch(() => {
        this.clearAuth();
        router.push('/login');
      });
    }
  }
};

// 初始化认证
auth.init(); 