// 路由配置
const routes = [
  { 
    path: '/',
    redirect: '/dashboard'
  },
  {
    path: '/login',
    component: Login,
    meta: { requiresAuth: false }
  },
  {
    path: '/dashboard',
    component: Dashboard,
    meta: { requiresAuth: true },
    children: [
      {
        path: '',
        redirect: '/dashboard/db-admin'
      },
      {
        path: 'db-admin',
        component: DBAdmin,
        meta: { requiresAuth: true }
      },
      {
        path: 'memory-admin',
        component: MemoryAdmin,
        meta: { requiresAuth: true }
      }
    ]
  }
];

const router = VueRouter.createRouter({
  history: VueRouter.createWebHashHistory(),
  routes
});

// 全局前置守卫
router.beforeEach((to, from, next) => {
  const requiresAuth = to.matched.some(record => record.meta.requiresAuth);
  const isAuthenticated = !!localStorage.getItem('token');

  if (requiresAuth && !isAuthenticated) {
    // 需要认证但未登录，重定向到登录页
    next('/login');
  } else if (to.path === '/login' && isAuthenticated) {
    // 已登录但尝试访问登录页，重定向到首页
    next('/dashboard');
  } else {
    // 其他情况正常通过
    next();
  }
}); 