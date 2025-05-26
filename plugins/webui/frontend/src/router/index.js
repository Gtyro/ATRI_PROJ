import { createRouter, createWebHashHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

// 懒加载路由组件
const Login = () => import('@/views/LoginPage.vue')
const AdminLayout = () => import('@/views/AdminLayout.vue')
const DBAdmin = () => import('@/views/DBAdmin.vue')
const MemoryAdmin = () => import('@/views/MemoryAdmin.vue')
const DashboardOverview = () => import('@/views/dashboard/DashboardOverview.vue')
const WordCloudPage = () => import('@/views/wordcloud/WordCloudPage.vue')

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
    component: AdminLayout,
    meta: { requiresAuth: true },
    children: [
      {
        path: '',
        redirect: '/dashboard/overview'
      },
      {
        path: 'overview',
        component: DashboardOverview,
        meta: { requiresAuth: true }
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
      },
      {
        path: 'wordcloud',
        component: WordCloudPage,
        meta: { requiresAuth: true }
      }
    ]
  }
];

const router = createRouter({
  history: createWebHashHistory(),
  routes
});

// 全局前置守卫
router.beforeEach((to, from, next) => {
  const authStore = useAuthStore()
  const requiresAuth = to.matched.some(record => record.meta.requiresAuth)
  const isAuthenticated = authStore.isAuthenticated

  if (requiresAuth && !isAuthenticated) {
    // 需要认证但未登录，重定向到登录页
    next('/login')
  } else if (to.path === '/login' && isAuthenticated) {
    // 已登录但尝试访问登录页，重定向到首页
    next('/dashboard')
  } else {
    // 其他情况正常通过
    next()
  }
});

export default router 